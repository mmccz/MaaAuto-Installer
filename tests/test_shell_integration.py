"""外壳集成（卸载注册表项 / 开始菜单 / 桌面快捷方式）的备份还原测试。

背景（1.4.1 事故）：本地校验脚本用同一个 Inno AppId 装到
``%LOCALAPPDATA%\\Programs\\MaaAuto`` 再卸载，而 Inno 的卸载注册表项、开始菜单组、
桌面快捷方式都是**按 AppId 全局共享**的 —— 用户那份装在 ``D:\\MaaAuto`` 的登记被
一起删掉，Windows 里显示「系统找不到应用」，图标也没了。
"""

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "MaaAutoInstaller"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

from installer.core import shell_integration as shell  # noqa: E402


# --------------------------------------------------------------------------- #
# 常量必须和 Inno 脚本一致
# --------------------------------------------------------------------------- #
def test_app_id_matches_installer_iss():
    iss = (PKG / "packaging" / "installer.iss").read_text(encoding="utf-8")
    app_id_line = [l for l in iss.splitlines() if l.strip().startswith("AppId=")][0]
    # Inno 里 {{ 表示一个字面量 {，所以实际 AppId 是 {6F3A...}
    literal = app_id_line.split("=", 1)[1].strip().replace("{{", "{", 1)
    assert literal == shell.APP_ID
    assert shell.UNINSTALL_KEY == shell.APP_ID + "_is1"
    # 图标组名也要和 [Icons] 的 {group} 一致
    assert "DefaultGroupName=" + shell.ICON_GROUP in iss


# --------------------------------------------------------------------------- #
# 快照 / 还原（不碰真实注册表与真实快捷方式）
# --------------------------------------------------------------------------- #
@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """把三处全局路径都指到 tmp，注册表读写换成内存字典。"""
    group = tmp_path / "StartMenu" / "MaaAuto"
    desktop = tmp_path / "Desktop" / "MaaAuto.lnk"
    state = {"key": None}

    monkeypatch.setattr(shell, "start_menu_group", lambda: group)
    monkeypatch.setattr(shell, "desktop_lnk", lambda: desktop)
    monkeypatch.setattr(shell, "read_uninstall_key", lambda: state["key"])
    monkeypatch.setattr(shell, "write_uninstall_key",
                        lambda items: state.__setitem__("key", list(items)))
    monkeypatch.setattr(shell, "delete_uninstall_key",
                        lambda: state.__setitem__("key", None))
    return {"group": group, "desktop": desktop, "state": state}


def test_snapshot_captures_everything(sandbox):
    group, desktop, state = sandbox["group"], sandbox["desktop"], sandbox["state"]
    group.mkdir(parents=True)
    (group / "MaaAuto.lnk").write_bytes(b"LNK-APP")
    (group / "卸载 MaaAuto.lnk").write_bytes(b"LNK-UNINST")
    desktop.parent.mkdir(parents=True)
    desktop.write_bytes(b"LNK-DESKTOP")
    state["key"] = [("DisplayName", "MaaAuto", 1),
                    ("InstallLocation", r"D:\MaaAuto\\", 1)]

    snap = shell.snapshot()
    assert snap.key_items is not None and len(snap.key_items) == 2
    assert snap.group_files == {"MaaAuto.lnk": b"LNK-APP",
                                "卸载 MaaAuto.lnk": b"LNK-UNINST"}
    assert snap.desktop_link == b"LNK-DESKTOP"
    assert "注册表项" in snap.summary() and "开始菜单" in snap.summary()


def test_restore_puts_user_state_back(sandbox):
    """模拟校验脚本：注册表被改写、快捷方式被删/被换成校验版的 → 还原。"""
    group, desktop, state = sandbox["group"], sandbox["desktop"], sandbox["state"]
    group.mkdir(parents=True)
    (group / "MaaAuto.lnk").write_bytes(b"LNK-APP")
    desktop.parent.mkdir(parents=True)
    desktop.write_bytes(b"LNK-DESKTOP")
    state["key"] = [("InstallLocation", r"D:\MaaAuto\\", 1)]
    snap = shell.snapshot()

    # 校验脚本干的事：注册表指向校验目录、快捷方式清空
    state["key"] = [("InstallLocation", r"C:\verify\\", 1)]
    if group.exists():
        import shutil
        shutil.rmtree(group)
    desktop.unlink()

    msg = shell.restore(snap)
    assert "还原注册表项" in msg and "还原开始菜单" in msg and "还原桌面" in msg
    assert state["key"][0][1] == r"D:\MaaAuto\\"
    assert (group / "MaaAuto.lnk").read_bytes() == b"LNK-APP"
    assert desktop.read_bytes() == b"LNK-DESKTOP"


def test_restore_clears_entries_created_by_verify(sandbox):
    """原本没有登记（用户没装）→ 校验跑完不能留下残留。"""
    group, desktop, state = sandbox["group"], sandbox["desktop"], sandbox["state"]
    state["key"] = None
    snap = shell.snapshot()

    group.mkdir(parents=True)
    (group / "MaaAuto.lnk").write_bytes(b"VERIFY")
    desktop.parent.mkdir(parents=True)
    desktop.write_bytes(b"VERIFY")
    state["key"] = [("DisplayName", "MaaAuto", 1)]

    shell.restore(snap)
    assert state["key"] is None
    assert not group.exists()
    assert not desktop.exists()


# --------------------------------------------------------------------------- #
# 检测「本机另有一份安装」
# --------------------------------------------------------------------------- #
def test_foreign_install_detected(monkeypatch, tmp_path):
    monkeypatch.setattr(shell, "read_uninstall_key",
                        lambda: [("InstallLocation", r"D:\MaaAuto\\", 1)])
    assert shell.foreign_install(tmp_path / "other") == Path(r"D:\MaaAuto")


def test_foreign_install_none_when_same_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(shell, "read_uninstall_key",
                        lambda: [("InstallLocation", str(tmp_path) + "\\", 1)])
    assert shell.foreign_install(tmp_path) is None


def test_foreign_install_none_without_entry(monkeypatch, tmp_path):
    monkeypatch.setattr(shell, "read_uninstall_key", lambda: None)
    assert shell.foreign_install(tmp_path) is None


# --------------------------------------------------------------------------- #
# 修复受损机器
# --------------------------------------------------------------------------- #
def test_repair_requires_existing_exe(tmp_path):
    with pytest.raises(FileNotFoundError):
        shell.repair_integration(tmp_path, "1.4.2")


def test_repair_writes_registry_and_links(tmp_path, monkeypatch):
    install = tmp_path / "app"
    install.mkdir()
    (install / shell.MAIN_EXE).write_bytes(b"exe")
    (install / shell.UNINSTALLER_EXE).write_bytes(b"unins")
    written = {}
    monkeypatch.setattr(shell, "write_uninstall_key",
                        lambda items: written.setdefault("items", list(items)))
    monkeypatch.setattr(shell, "start_menu_group", lambda: tmp_path / "sm" / "MaaAuto")
    monkeypatch.setattr(shell, "desktop_lnk", lambda: tmp_path / "desk" / "MaaAuto.lnk")
    monkeypatch.setattr(shell, "_write_lnk", lambda *a, **k: True)

    result = shell.repair_integration(install, "1.4.2")
    assert result["registry"] and result["start_menu"] and result["desktop"]
    items = dict((n, v) for n, v, _k in written["items"])
    assert items["DisplayVersion"] == "1.4.2"
    assert items["InstallLocation"] == str(install) + "\\"
    assert str(install / shell.UNINSTALLER_EXE) in items["UninstallString"]
    assert items["DisplayIcon"] == str(install / shell.MAIN_EXE)
