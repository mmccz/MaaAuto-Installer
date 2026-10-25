"""安装「外壳集成」的备份 / 还原 / 修复。

为什么要这个东西（1.4.2 的教训）
--------------------------------
Inno 安装包有三样东西是**按 AppId 全局共享**的，跟装在哪个目录无关：

* ``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{AppId}_is1``
  （「设置 → 应用」里那条记录，Windows 靠它找卸载器）
* 开始菜单组 ``%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\MaaAuto``
* 桌面 ``MaaAuto.lnk``

本地发布校验脚本（``tools/verify_release.py``、``tools/smoke_install.py``）会
「装一份 → 跑测试 → 卸载」。它们装在 ``%LOCALAPPDATA%\\Programs\\MaaAuto``，
而用户可能把正式版装在 ``D:\\MaaAuto`` 之类的自定义目录——**AppId 相同**，
于是校验脚本的卸载会把用户那份的注册表项和开始菜单组一起删掉：

* 「设置 → 应用」里的 MaaAuto 变成「系统找不到应用」（UninstallString 指向已删除的 exe）
* 开始菜单 / 桌面快捷方式消失

程序文件其实没被动过（自动升级只替换文件），坏掉的只是这些**登记信息**。

所以校验脚本现在必须：

1. 装到**独立目录**（``MaaAuto_verify``），不碰用户目录；
2. 开跑前 ``snapshot()`` 备份注册表项 + 快捷方式，结束后 ``restore()`` 还原。

``repair_integration()`` 用来给已经被误删的机器重建这些登记信息。
"""

import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 与 packaging/installer.iss 的 AppId 保持一致（改这里必须同步 .iss）
APP_ID = "{6F3A2C1E-8B4D-4E7A-9C15-3D02A7B9E4C1}"
APP_NAME = "MaaAuto"
UNINSTALL_KEY = f"{APP_ID}_is1"
UNINSTALL_ROOT = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
ICON_GROUP = "MaaAuto"
MAIN_EXE = "MaaAuto.exe"
UNINSTALLER_EXE = "unins000.exe"


# --------------------------------------------------------------------------- #
# 路径
# --------------------------------------------------------------------------- #
def uninstall_key_path() -> str:
    return f"{UNINSTALL_ROOT}\\{UNINSTALL_KEY}"


def start_menu_group() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return (Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            / ICON_GROUP)


def desktop_lnk() -> Path:
    # Inno 的 {autodesktop} 在 per-user 安装下就是当前用户桌面
    desktop = Path(os.environ.get("USERPROFILE") or str(Path.home())) / "Desktop"
    return desktop / f"{APP_NAME}.lnk"


# --------------------------------------------------------------------------- #
# 注册表：整个键读成 (name, value, type) 三元组，方便原样写回
# --------------------------------------------------------------------------- #
def read_uninstall_key() -> Optional[List[Tuple[str, object, int]]]:
    """读当前用户的 MaaAuto 卸载项；不存在返回 None。"""
    try:
        import winreg
    except Exception:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, uninstall_key_path()) as k:
            items = []
            i = 0
            while True:
                try:
                    name, value, kind = winreg.EnumValue(k, i)
                except OSError:
                    break
                i += 1
                items.append((name, value, kind))
            return items
    except OSError:
        return None


def write_uninstall_key(items: List[Tuple[str, object, int]]) -> None:
    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, uninstall_key_path(), 0,
                            winreg.KEY_WRITE) as k:
        for name, value, kind in items:
            winreg.SetValueEx(k, name, 0, kind, value)


def delete_uninstall_key() -> None:
    import winreg
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, uninstall_key_path())
    except OSError:
        pass


def installed_location() -> Optional[Path]:
    """注册表里登记的安装目录（没有就 None）。"""
    items = read_uninstall_key() or []
    for name, value, _kind in items:
        if name.lower() in ("installlocation", "inno setup: app path"):
            text = str(value).strip().rstrip("\\")
            if text:
                return Path(text)
    return None


def foreign_install(target_dir: Path) -> Optional[Path]:
    """注册表里登记的是「另一份安装」时返回那个目录。

    校验脚本用它提醒：接下来动的是共享的注册表项和快捷方式。
    """
    loc = installed_location()
    try:
        target = Path(target_dir).resolve()
    except OSError:
        target = Path(target_dir)
    if loc is None:
        return None
    try:
        if loc.resolve() == target:
            return None
    except OSError:
        pass
    return loc


# --------------------------------------------------------------------------- #
# 快照 / 还原
# --------------------------------------------------------------------------- #
@dataclass
class IntegrationSnapshot:
    """外壳集成状态快照（注册表值 + 快捷方式原始字节）。"""
    key_items: Optional[List[Tuple[str, object, int]]] = None
    group_files: Dict[str, bytes] = field(default_factory=dict)
    desktop_link: Optional[bytes] = None
    # 备份的临时目录（复制快捷方式用，必须在 restore 里清掉）
    _tmp: Optional[Path] = None

    def summary(self) -> str:
        parts = []
        if self.key_items is not None:
            parts.append(f"注册表项 {len(self.key_items)} 个值")
        if self.group_files:
            parts.append(f"开始菜单 {len(self.group_files)} 个文件")
        if self.desktop_link:
            parts.append("桌面快捷方式")
        return "、".join(parts) if parts else "（无）"


def snapshot() -> IntegrationSnapshot:
    snap = IntegrationSnapshot(key_items=read_uninstall_key())
    group = start_menu_group()
    if group.is_dir():
        for p in group.rglob("*"):
            if p.is_file():
                rel = p.relative_to(group).as_posix()
                try:
                    snap.group_files[rel] = p.read_bytes()
                except OSError:
                    pass
    lnk = desktop_lnk()
    if lnk.is_file():
        try:
            snap.desktop_link = lnk.read_bytes()
        except OSError:
            pass
    return snap


def restore(snap: IntegrationSnapshot) -> str:
    """把快照写回去；返回人类可读的还原摘要。"""
    actions = []

    # 注册表
    if snap.key_items is None:
        delete_uninstall_key()
        actions.append("已清掉本次校验写入的注册表项")
    else:
        write_uninstall_key(snap.key_items)
        actions.append(f"还原注册表项（{len(snap.key_items)} 个值）")

    # 开始菜单：先删掉校验过程留下的，再按快照重建
    group = start_menu_group()
    if group.exists():
        shutil.rmtree(group, ignore_errors=True)
    if snap.group_files:
        group.mkdir(parents=True, exist_ok=True)
        for rel, data in snap.group_files.items():
            target = group / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        actions.append(f"还原开始菜单（{len(snap.group_files)} 个文件）")

    # 桌面
    lnk = desktop_lnk()
    if snap.desktop_link:
        lnk.parent.mkdir(parents=True, exist_ok=True)
        lnk.write_bytes(snap.desktop_link)
        actions.append("还原桌面快捷方式")
    elif lnk.exists():
        try:
            lnk.unlink()
            actions.append("清掉本次校验新建的桌面快捷方式")
        except OSError:
            pass

    return "；".join(actions)


# --------------------------------------------------------------------------- #
# 修复（给被误删登记的机器用）
# --------------------------------------------------------------------------- #
def _write_lnk(path: Path, target: Path, workdir: Path, description: str = "") -> bool:
    """用 WScript.Shell 建 .lnk（pywin32 不在装机依赖里，这里按需导入）。"""
    try:
        import win32com.client
    except Exception:
        return False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        sh = win32com.client.Dispatch("WScript.Shell")
        lnk = sh.CreateShortCut(str(path))
        lnk.TargetPath = str(target)
        lnk.WorkingDirectory = str(workdir)
        lnk.IconLocation = str(target)
        lnk.Description = description
        lnk.Save()
        return path.exists()
    except Exception:
        return False


def _dir_size_kb(root: Path) -> int:
    total = 0
    for p in Path(root).rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            pass
    return total // 1024


def repair_integration(install_dir: Path, version: str = "") -> Dict[str, bool]:
    """为 ``install_dir`` 重建卸载注册表项、开始菜单组与桌面快捷方式。

    只补齐/覆盖，不删除任何程序文件；用于修复「升级后图标和『应用』条目消失」。
    """
    import time

    install_dir = Path(install_dir)
    exe = install_dir / MAIN_EXE
    uninst = install_dir / UNINSTALLER_EXE
    if not exe.exists():
        raise FileNotFoundError(f"{exe} 不存在，先确认安装目录")

    result = {}

    group = start_menu_group()
    result["start_menu"] = _write_lnk(group / f"{APP_NAME}.lnk", exe, install_dir,
                                      APP_NAME)
    result["start_menu_uninstall"] = _write_lnk(
        group / f"卸载 {APP_NAME}.lnk", uninst, install_dir, f"卸载 {APP_NAME}")
    result["desktop"] = _write_lnk(desktop_lnk(), exe, install_dir, APP_NAME)

    items: List[Tuple[str, object, int]] = [
        ("DisplayName", APP_NAME, 1),
        ("DisplayVersion", version or "", 1),
        ("DisplayIcon", str(exe), 1),
        ("UninstallString", f'"{uninst}"', 1),
        ("QuietUninstallString", f'"{uninst}" /SILENT', 1),
        ("InstallLocation", str(install_dir) + "\\", 1),
        ("Publisher", "mmccz", 1),
        ("URLInfoAbout", "https://github.com/mmccz/MaaAuto-Tool-works", 1),
        ("HelpLink", "https://github.com/mmccz/MaaAuto-Tool-works/issues", 1),
        ("URLUpdateInfo", "https://github.com/mmccz/MaaAuto-Tool-works/releases", 1),
        ("NoModify", 1, 4),
        ("NoRepair", 1, 4),
        ("InstallDate", time.strftime("%Y%m%d"), 1),
        ("EstimatedSize", _dir_size_kb(install_dir), 4),
        ("Inno Setup: App Path", str(install_dir), 1),
        ("Inno Setup: Icon Group", ICON_GROUP, 1),
        ("Inno Setup: Language", "cn", 1),
        ("Inno Setup: Selected Tasks", "startmenuicon,desktopicon", 1),
        ("Inno Setup: User", os.environ.get("USERNAME", ""), 1),
    ]
    if version:
        parts = version.split(".")
        try:
            items.append(("VersionMajor", int(parts[0]), 4))
            items.append(("VersionMinor", int(parts[1]), 4))
        except (IndexError, ValueError):
            pass
    write_uninstall_key(items)
    result["registry"] = True
    return result
