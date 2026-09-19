"""
MaaAuto 卸载器 stub（VBS 后端版）。
PyInstaller 打包 → tools/_out/uninstall.exe
安装时被释放到 <install>/uninstall.exe。

为什么用 VBS 而不是 bat：
  - bat 的 `tasklist | find` 在某些系统上会卡住（等待 stdin）
  - bat 编码坑（GBK/UTF-8-SIG）
  - wscript.exe 从 XP 起就自带，绝对可靠
  - VBS 的 FileSystemObject 删除目录比 rmdir 更稳
"""

import os
import sys
import json
import time
import subprocess
import tempfile
from pathlib import Path

import ctypes
import winreg


MB_OK = 0x0
MB_YESNO = 0x4
MB_ICONQUESTION = 0x20
MB_ICONINFORMATION = 0x40
MB_ICONERROR = 0x10
MB_DEFBUTTON2 = 0x100
IDYES = 6
_UNINSTALL_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\MaaAuto"
_APP_PATH_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\MaaAuto.exe"
_APPCOMPAT_KEY = (r"Software\Microsoft\Windows NT\CurrentVersion"
                  r"\AppCompatFlags\Layers")


def msg(title, text, flags=MB_OK | MB_ICONINFORMATION) -> int:
    try:
        return ctypes.windll.user32.MessageBoxW(0, str(text), str(title), flags)
    except Exception:
        return 0


def get_install_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def read_manifest(install_dir: Path) -> dict:
    p = install_dir / ".maaauto.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def remove_shortcuts():
    try:
        desktop = Path(os.path.join(os.environ["USERPROFILE"], "Desktop"))
        lnk = desktop / "MaaAuto.lnk"
        if lnk.exists():
            lnk.unlink()
    except Exception:
        pass
    try:
        appdata = Path(os.environ["APPDATA"])
        folder = (appdata / "Microsoft" / "Windows" / "Start Menu"
                  / "Programs" / "MaaAuto")
        if folder.exists():
            import shutil
            shutil.rmtree(folder, ignore_errors=True)
    except Exception:
        pass

def remove_registry(install_dir: Path):
    """删除所有注册表项。全部静默处理失败。"""
    # 卸载项
    try:
        winreg.DeleteKeyEx(winreg.HKEY_LOCAL_MACHINE, _UNINSTALL_KEY,
                           winreg.KEY_WOW64_64KEY, 0)
    except Exception:
        pass
    # App Paths
    try:
        winreg.DeleteKeyEx(winreg.HKEY_LOCAL_MACHINE, _APP_PATH_KEY,
                           winreg.KEY_WOW64_64KEY, 0)
    except Exception:
        pass
    # 管理员运行标志
    try:
        exe = str((Path(install_dir) / "MaaAuto.exe").resolve())
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _APPCOMPAT_KEY,
                            0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, exe)
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# VBS 生成
# --------------------------------------------------------------------------- #
def build_vbs(install_dir: Path, keep_user_data: bool) -> str:
    """生成 VBS 脚本。纯英文，避免编码问题。"""
    target = str(install_dir)

    if keep_user_data:
        cleanup = '''
' 保留 config/ 和 logs/，删其他
Dim keepList
keepList = Array("config", "logs")
Dim sf
For Each sf In fso.GetFolder(target).SubFolders
    Dim isKeep
    isKeep = False
    Dim k
    For Each k In keepList
        If LCase(sf.Name) = k Then isKeep = True
    Next
    If Not isKeep Then
        On Error Resume Next
        sf.Delete True
        On Error Goto 0
    End If
Next
Dim fl
For Each fl In fso.GetFolder(target).Files
    On Error Resume Next
    fl.Delete True
    On Error Goto 0
Next
'''
    else:
        cleanup = '''
' 全删
On Error Resume Next
fso.DeleteFolder target, True
On Error Goto 0
'''

    vbs = f'''Option Explicit
Dim fso, shell, target
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

target = "{target}"

' 1) 等卸载器进程退出
WScript.Sleep 2500

' 2) 杀主程序（若在运行）
On Error Resume Next
shell.Run "taskkill /F /IM MaaAuto.exe", 0, True
On Error Goto 0
WScript.Sleep 800

' 3) 清理目录
If fso.FolderExists(target) Then
{cleanup}
End If

' 4) 自删除
On Error Resume Next
fso.DeleteFile WScript.ScriptFullName, True
On Error Goto 0
'''
    return vbs


def launch_vbs(install_dir: Path, keep_user_data: bool) -> bool:
    content = build_vbs(install_dir, keep_user_data)
    vbs_path = Path(tempfile.gettempdir()) / f"MaaAuto_uninstall_{int(time.time())}.vbs"

    # 用 GBK 写（中文 Windows 上的 ANSI 编码），wscript 按 ANSI 解码
    try:
        vbs_path.write_text(content, encoding="gbk", errors="replace")
    except Exception:
        try:
            vbs_path.write_text(content, encoding="utf-8-sig")
        except Exception:
            msg("卸载失败", f"无法写 VBS：\n{vbs_path}", MB_OK | MB_ICONERROR)
            return False

    # 优先 wscript.exe，退化到 cscript.exe
    FLAGS = 0x08000000 | 0x00000008   # CREATE_NO_WINDOW | DETACHED_PROCESS
    for exe in ("wscript.exe", "cscript.exe"):
        try:
            subprocess.Popen(
                [exe, "//B", "//Nologo", str(vbs_path)],
                creationflags=FLAGS,
                close_fds=True,
                cwd=str(Path(tempfile.gettempdir())),
            )
            return True
        except FileNotFoundError:
            continue
        except Exception as e:
            msg("卸载失败", f"启动 {exe} 失败：\n\n{e}", MB_OK | MB_ICONERROR)
            return False

    msg("卸载失败",
        "系统缺少 wscript.exe 和 cscript.exe，无法自动清理。\n\n"
        f"请手动删除：{install_dir}",
        MB_OK | MB_ICONERROR)
    return False


# --------------------------------------------------------------------------- #
def main() -> int:
    install_dir = get_install_dir()
    manifest = read_manifest(install_dir)
    version = manifest.get("version", "")

    title = "MaaAuto 卸载程序"
    text = f"将从以下位置删除 MaaAuto：\n\n{install_dir}\n"
    if version:
        text += f"\n版本：{version}\n"
    text += "\n是否继续？\n\n（桌面 / 开始菜单快捷方式也会一并删除）"

    if msg(title, text, MB_YESNO | MB_ICONQUESTION | MB_DEFBUTTON2) != IDYES:
        return 0

    r2 = msg(
        "保留用户数据",
        "是否保留用户配置 (config\\) 和日志 (logs\\)？\n\n"
        "  「是」→ 保留，方便以后重装恢复\n"
        "  「否」→ 全部删除（推荐）",
        MB_YESNO | MB_ICONQUESTION | MB_DEFBUTTON2,
    )
    keep_user_data = (r2 == IDYES)
    remove_registry(install_dir)
    remove_shortcuts()

    if launch_vbs(install_dir, keep_user_data):
        msg("卸载中",
            "MaaAuto 正在被删除...\n\n"
            "几秒后安装目录会被清理干净。\n"
            "如仍有残留，可手动删除该目录。",
            MB_OK | MB_ICONINFORMATION)
    return 0


if __name__ == "__main__":
    sys.exit(main())