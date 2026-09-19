"""
Windows 注册表操作：
  - 卸载项（出现在"设置→应用"）
  - App Paths（Win+R 可直接启动）
  - 以管理员身份运行标志（属性页可见）

权限说明：
  - HKLM 需要管理员权限（安装器/卸载器已通过 --uac-admin 获得）
  - AppCompatFlags 必须写 HKCU（per-user 设置）
"""

import os
import winreg
from pathlib import Path
from typing import Callable, Optional


def _log(logger, msg):
    if logger:
        try:
            logger(msg)
        except Exception:
            pass


_UNINSTALL_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\MaaAuto"
_APP_PATH_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\MaaAuto.exe"
_APPCOMPAT_KEY = (r"Software\Microsoft\Windows NT\CurrentVersion"
                  r"\AppCompatFlags\Layers")


def _create_key_hklm(path: str):
    """HKLM 64 位视图键，避开 WOW6432Node 重定向。"""
    return winreg.CreateKeyEx(
        winreg.HKEY_LOCAL_MACHINE, path, 0,
        winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY,
    )


# --------------------------------------------------------------------------- #
# 卸载项
# --------------------------------------------------------------------------- #
def register_uninstall(install_dir: Path, version: str,
                       log: Optional[Callable[[str], None]] = None) -> bool:
    install_dir = Path(install_dir).resolve()
    exe = install_dir / "MaaAuto.exe"
    uninstaller = install_dir / "uninstall.exe"

    try:
        with _create_key_hklm(_UNINSTALL_KEY) as key:
            def sv(name, value, vtype=winreg.REG_SZ):
                winreg.SetValueEx(key, name, 0, vtype, value)

            sv("DisplayName", "MaaAuto")
            sv("DisplayVersion", version or "0.0.0")
            sv("Publisher", "MaaAuto")
            sv("InstallLocation", str(install_dir))
            sv("InstallDate", _today())
            sv("DisplayIcon", f"{exe},0")
            sv("UninstallString", f'"{uninstaller}"')
            sv("QuietUninstallString", f'"{uninstaller}" /S')
            size_kb = _dir_size_kb(install_dir)
            if size_kb > 0:
                sv("EstimatedSize", size_kb, winreg.REG_DWORD)
            sv("NoModify", 1, winreg.REG_DWORD)
            sv("NoRepair", 1, winreg.REG_DWORD)

        _log(log, "已注册卸载项")
        return True
    except Exception as e:
        _log(log, f"注册卸载项失败: {e}")
        return False


def unregister_uninstall(log=None) -> bool:
    try:
        winreg.DeleteKeyEx(winreg.HKEY_LOCAL_MACHINE, _UNINSTALL_KEY,
                           winreg.KEY_WOW64_64KEY, 0)
        _log(log, "已删除卸载项")
        return True
    except FileNotFoundError:
        return True
    except Exception as e:
        _log(log, f"删除卸载项失败: {e}")
        return False


# --------------------------------------------------------------------------- #
# App Paths
# --------------------------------------------------------------------------- #
def register_app_path(install_dir: Path,
                      log: Optional[Callable[[str], None]] = None) -> bool:
    install_dir = Path(install_dir).resolve()
    exe = install_dir / "MaaAuto.exe"

    try:
        with _create_key_hklm(_APP_PATH_KEY) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, str(exe))
            winreg.SetValueEx(key, "Path", 0, winreg.REG_SZ, str(install_dir))
        _log(log, "已注册 App Paths")
        return True
    except Exception as e:
        _log(log, f"注册 App Paths 失败: {e}")
        return False


def unregister_app_path(log=None) -> bool:
    try:
        winreg.DeleteKeyEx(winreg.HKEY_LOCAL_MACHINE, _APP_PATH_KEY,
                           winreg.KEY_WOW64_64KEY, 0)
        _log(log, "已删除 App Paths")
        return True
    except FileNotFoundError:
        return True
    except Exception as e:
        _log(log, f"删除 App Paths 失败: {e}")
        return False


# --------------------------------------------------------------------------- #
# 以管理员身份运行标志
# --------------------------------------------------------------------------- #
def set_run_as_admin(exe_path: Path,
                     log: Optional[Callable[[str], None]] = None) -> bool:
    """
    效果：右键 exe → 属性 → 兼容性 → "以管理员身份运行此程序" 被勾选。
    原理：HKCU\\...\\AppCompatFlags\\Layers 里加 "~ RUNASADMIN"。
    """
    exe_path = Path(exe_path).resolve()
    try:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, _APPCOMPAT_KEY, 0, winreg.KEY_WRITE
        ) as key:
            winreg.SetValueEx(key, str(exe_path), 0, winreg.REG_SZ,
                              "~ RUNASADMIN")
        _log(log, f"已设置以管理员身份运行: {exe_path.name}")
        return True
    except Exception as e:
        _log(log, f"设置管理员运行失败: {e}")
        return False


def clear_run_as_admin(exe_path: Path, log=None) -> bool:
    exe_path = Path(exe_path).resolve()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _APPCOMPAT_KEY,
                            0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, str(exe_path))
        _log(log, "已清除管理员运行标志")
        return True
    except FileNotFoundError:
        return True
    except Exception as e:
        _log(log, f"清除管理员运行标志失败: {e}")
        return False


# --------------------------------------------------------------------------- #
# 一站式
# --------------------------------------------------------------------------- #
def register_all(install_dir: Path, version: str,
                 set_admin: bool = True,
                 log: Optional[Callable[[str], None]] = None) -> bool:
    """安装完成后一次性写入所有注册表项。"""
    install_dir = Path(install_dir).resolve()
    exe = install_dir / "MaaAuto.exe"

    ok = True
    if not register_uninstall(install_dir, version, log=log):
        ok = False
    if not register_app_path(install_dir, log=log):
        ok = False
    if set_admin:
        if not set_run_as_admin(exe, log=log):
            _log(log, "（管理员运行标志写入失败，非致命）")
    return ok


def unregister_all(install_dir: Path,
                   log: Optional[Callable[[str], None]] = None) -> bool:
    """卸载时清理所有注册表项。"""
    install_dir = Path(install_dir).resolve()
    exe = install_dir / "MaaAuto.exe"
    unregister_uninstall(log=log)
    unregister_app_path(log=log)
    clear_run_as_admin(exe, log=log)
    return True


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #
def _today() -> str:
    import datetime
    return datetime.datetime.now().strftime("%Y%m%d")


def _dir_size_kb(path: Path) -> int:
    total = 0
    try:
        for root, _dirs, files in os.walk(path):
            for f in files:
                try:
                    total += (Path(root) / f).stat().st_size
                except Exception:
                    pass
    except Exception:
        return 0
    return total // 1024