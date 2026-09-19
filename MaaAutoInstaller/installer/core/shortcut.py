"""Windows 快捷方式创建与删除（基于 pywin32）。"""

import os
from pathlib import Path
from typing import Optional


def _shell():
    import pythoncom
    import win32com.client
    # 确保 COM 已初始化
    pythoncom.CoInitialize()
    return win32com.client.Dispatch("WScript.Shell")


def _co_uninit():
    try:
        import pythoncom
        pythoncom.CoUninitialize()
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# 创建
# --------------------------------------------------------------------------- #
def create_desktop_shortcut(target_exe: Path,
                            work_dir: Path,
                            name: str = "MaaAuto",
                            icon: Optional[Path] = None) -> Optional[Path]:
    target_exe = Path(target_exe).resolve()
    work_dir = Path(work_dir).resolve()

    try:
        desktop = Path(os.path.join(os.environ["USERPROFILE"], "Desktop"))
    except KeyError:
        return None

    lnk = desktop / f"{name}.lnk"
    try:
        sh = _shell()
        sc = sh.CreateShortCut(str(lnk))
        sc.TargetPath = str(target_exe)
        sc.WorkingDirectory = str(work_dir)
        sc.Description = name
        sc.WindowStyle = 1
        if icon and Path(icon).exists():
            sc.IconLocation = f"{icon},0"
        else:
            sc.IconLocation = f"{target_exe},0"
        sc.Save()
        return lnk
    except Exception:
        return None
    finally:
        _co_uninit()


def create_startmenu_shortcut(target_exe: Path,
                              work_dir: Path,
                              name: str = "MaaAuto",
                              icon: Optional[Path] = None) -> Optional[Path]:
    target_exe = Path(target_exe).resolve()
    work_dir = Path(work_dir).resolve()

    try:
        appdata = Path(os.environ["APPDATA"])
    except KeyError:
        return None

    start_menu = appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    folder = start_menu / name
    folder.mkdir(parents=True, exist_ok=True)

    lnk = folder / f"{name}.lnk"
    try:
        sh = _shell()
        sc = sh.CreateShortCut(str(lnk))
        sc.TargetPath = str(target_exe)
        sc.WorkingDirectory = str(work_dir)
        sc.Description = name
        sc.WindowStyle = 1
        if icon and Path(icon).exists():
            sc.IconLocation = f"{icon},0"
        else:
            sc.IconLocation = f"{target_exe},0"
        sc.Save()
        return lnk
    except Exception:
        return None
    finally:
        _co_uninit()


# --------------------------------------------------------------------------- #
# 删除
# --------------------------------------------------------------------------- #
def remove_desktop_shortcut(name: str = "MaaAuto") -> bool:
    try:
        desktop = Path(os.path.join(os.environ["USERPROFILE"], "Desktop"))
    except KeyError:
        return False
    lnk = desktop / f"{name}.lnk"
    if lnk.exists():
        try:
            lnk.unlink()
            return True
        except Exception:
            return False
    return False


def remove_startmenu_shortcut(name: str = "MaaAuto") -> bool:
    try:
        appdata = Path(os.environ["APPDATA"])
    except KeyError:
        return False
    folder = appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / name
    if folder.exists():
        try:
            import shutil
            shutil.rmtree(folder, ignore_errors=True)
            return True
        except Exception:
            return False
    return False