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

import base64
import os
import shutil
import subprocess
import sys
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
# Microsoft Store 版 Python 的 MSIX 目录重定向
# --------------------------------------------------------------------------- #
def packaged_python() -> bool:
    """解释器是否来自 Microsoft Store（MSIX 打包应用）。

    MSIX 应用写 ``%APPDATA%`` 会被静默重定向到
    ``%LOCALAPPDATA%\\Packages\\<包>\\LocalCache\\Roaming``，Explorer / Inno 都看不到。
    于是「修复开始菜单」会报 OK、实际什么也没建出来（1.4.2 修复后复测踩到）。

    子进程（powershell.exe）不继承包身份，写的是真实路径，所以这类路径的
    读写统一交给 PowerShell 做。
    """
    prefix = str(getattr(sys, "prefix", "")).replace("/", "\\").lower()
    return "\\windowsapps\\" in prefix


def _ps_literal(text: object) -> str:
    """包成 PowerShell 单引号字符串（单引号自身翻倍）。"""
    return "'" + str(text).replace("'", "''") + "'"


def _ps(script: str) -> Optional[str]:
    """跑一段 PowerShell；成功返回 stdout，失败/不可用返回 None。"""
    if os.name != "nt":
        return None
    exe = shutil.which("powershell.exe") or shutil.which("powershell") or "powershell"
    try:
        proc = subprocess.run(
            [exe, "-NoProfile", "-NonInteractive", "-Command",
             "[Console]::OutputEncoding=[Text.Encoding]::UTF8;" + script],
            capture_output=True, timeout=60)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8-sig", "replace")


def _read_group_via_ps(group: Path) -> Dict[str, bytes]:
    root = _ps_literal(str(group))
    script = (
        f"$root = {root};"
        "if (-not (Test-Path -LiteralPath $root)) { exit 3 };"
        "$root = (Resolve-Path -LiteralPath $root).Path;"
        "Get-ChildItem -LiteralPath $root -Recurse -File | ForEach-Object {"
        "  $rel = $_.FullName.Substring($root.Length + 1).Replace('\\', '/');"
        "  $rel + [char]9 + [Convert]::ToBase64String([IO.File]::ReadAllBytes($_.FullName))"
        " }"
    )
    out = _ps(script)
    if not out:
        return {}
    files: Dict[str, bytes] = {}
    for line in out.splitlines():
        if "\t" not in line:
            continue
        rel, b64 = line.split("\t", 1)
        try:
            files[rel.strip()] = base64.b64decode(b64.strip())
        except Exception:
            continue
    return files


def _write_group_via_ps(group: Path, files: Dict[str, bytes]) -> bool:
    """用 PowerShell 重建开始菜单组（先整个删掉，再按字节写回）。"""
    parts = [
        f"$root = {_ps_literal(str(group))};",
        "if (Test-Path -LiteralPath $root) {"
        " Remove-Item -LiteralPath $root -Recurse -Force };",
    ]
    for rel, data in files.items():
        target = Path(str(group)) / rel
        b64 = base64.b64encode(data).decode("ascii")
        parts.append(f"$p = {_ps_literal(str(target))};")
        parts.append("New-Item -ItemType Directory -Path (Split-Path -Parent $p)"
                     " -Force | Out-Null;")
        parts.append(f"[IO.File]::WriteAllBytes($p,"
                     f" [Convert]::FromBase64String('{b64}'));")
    return _ps("".join(parts)) is not None


def start_menu_files() -> Dict[str, bytes]:
    """开始菜单组里的文件（相对路径 → 原始字节），空组/不存在返回 {}。"""
    if packaged_python():
        return _read_group_via_ps(start_menu_group())
    group = start_menu_group()
    files: Dict[str, bytes] = {}
    if group.is_dir():
        for p in group.rglob("*"):
            if p.is_file():
                try:
                    files[p.relative_to(group).as_posix()] = p.read_bytes()
                except OSError:
                    pass
    return files


def clear_start_menu_group() -> None:
    """删掉开始菜单组（真实路径；MSIX 下不能直接 rmtree）。"""
    group = start_menu_group()
    if packaged_python():
        _ps("if (Test-Path -LiteralPath %s) { Remove-Item -LiteralPath %s"
            " -Recurse -Force }" % (_ps_literal(group), _ps_literal(group)))
    else:
        shutil.rmtree(group, ignore_errors=True)




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
    # 开始菜单组用 start_menu_files()：MSIX Python 下必须走 PowerShell 才看得见真实目录
    snap.group_files = start_menu_files()
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
        # 快照时没有登记：正常情况下要删掉校验过程写进去的那条。
        # 但如果登记的安装目录还在（程序文件也在），说明这是用户的正式安装，
        # 宁可留一条多余登记也不能再删一次（1.4.1 事故就是这么来的）。
        loc = installed_location()
        if loc is not None and (loc / MAIN_EXE).exists():
            actions.append(f"保留现有登记（{loc} 仍在），未删除")
        else:
            delete_uninstall_key()
            actions.append("已清掉本次校验写入的注册表项")
    else:
        write_uninstall_key(snap.key_items)
        actions.append(f"还原注册表项（{len(snap.key_items)} 个值）")

    # 开始菜单：先删掉校验过程留下的，再按快照重建
    group = start_menu_group()
    if packaged_python():
        # MSIX 重定向会让 write_bytes 写进 LocalCache，必须借 PowerShell 落真实路径
        if _write_group_via_ps(group, snap.group_files):
            if snap.group_files:
                actions.append(f"还原开始菜单（{len(snap.group_files)} 个文件）")
        else:
            actions.append("开始菜单还原失败（PowerShell 不可用，请手动运行 "
                           "tools/repair_integration.py）")
    else:
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
def _write_lnk_via_ps(path: Path, target: Path, workdir: Path,
                      description: str = "") -> bool:
    """在**真实**路径建 .lnk（绕开 MSIX 的 %APPDATA% 重定向）。"""
    script = (
        "$sh = New-Object -ComObject WScript.Shell;"
        f"$lnk = $sh.CreateShortcut({_ps_literal(path)});"
        f"$lnk.TargetPath = {_ps_literal(target)};"
        f"$lnk.WorkingDirectory = {_ps_literal(workdir)};"
        f"$lnk.IconLocation = {_ps_literal(target)};"
        f"$lnk.Description = {_ps_literal(description)};"
        "$lnk.Save();"
        "if (-not (Test-Path -LiteralPath "
        f"{_ps_literal(path)})) {{ exit 5 }}"
    )
    dir_script = ("New-Item -ItemType Directory -Path (Split-Path -Parent "
                  f"{_ps_literal(path)}) -Force | Out-Null;")
    return _ps(dir_script + script) is not None


def _write_lnk(path: Path, target: Path, workdir: Path, description: str = "") -> bool:
    """用 WScript.Shell 建 .lnk（pywin32 不在装机依赖里，这里按需导入）。"""
    if packaged_python():
        return _write_lnk_via_ps(path, target, workdir, description)
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
