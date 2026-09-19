"""
MaaAuto 卸载器 stub。
PyInstaller 打包后 → tools/_out/uninstall.exe
安装时被释放到 <install>/uninstall.exe。

设计要点：
  - 用 ctypes 调 Win32 MessageBox，体积小
  - 生成 GBK 编码的后台 bat 完成删除（避免 utf-8-sig BOM 让 cmd 崩溃）
  - bat 内先 taskkill 主程序 → cd 到 %TEMP% → 循环重试 rmdir
  - 全程写日志到 %TEMP%\\MaaAuto_uninstall.log 方便排查
"""

import os
import sys
import json
import time
import subprocess
import tempfile
from pathlib import Path

import ctypes


# --- Win32 常量 ---
MB_OK = 0x0
MB_YESNO = 0x4
MB_ICONQUESTION = 0x20
MB_ICONINFORMATION = 0x40
MB_ICONERROR = 0x10
MB_DEFBUTTON2 = 0x100
IDYES = 6


def msg(title, text, flags=MB_OK | MB_ICONINFORMATION) -> int:
    try:
        return ctypes.windll.user32.MessageBoxW(0, str(text), str(title), flags)
    except Exception:
        return 0


# --------------------------------------------------------------------------- #
def get_install_dir() -> Path:
    """PyInstaller onefile：sys.executable 是 exe 本身。"""
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


# --------------------------------------------------------------------------- #
def build_bat_content(install_dir: Path, pid: int, keep_user_data: bool) -> str:
    """
    生成 bat 内容。
    注意：用英文写 + chcp 936，避免编码问题。
    """
    target = str(install_dir.resolve())
    # 反斜杠转义：bat 里用 \ 就行
    log_file = r"%TEMP%\MaaAuto_uninstall.log"

    if keep_user_data:
        # 保留 config/ 和 logs/：先把它们挪到 temp，删完目录再挪回来
        # （简化：只提示，不真的保留 —— 因为挪回来还要重建目录太麻烦）
        # 改方案：不删 config 和 logs 子目录，只删其他
        delete_block = f'''
echo [%DATE% %TIME%] Deleting files except config/ and logs/ >> "{log_file}"
for /D %%D in ("{target}\\*") do (
    if /I not "%%~nxD"=="config" if /I not "%%~nxD"=="logs" (
        echo   rmdir /S /Q "%%D" >> "{log_file}"
        rd /S /Q "%%D" 2>>"{log_file}"
    )
)
for %%F in ("{target}\\*") do (
    del /F /Q "%%F" 2>>"{log_file}"
)
'''
    else:
        # 全部删除
        delete_block = f'''
echo [%DATE% %TIME%] Removing entire directory >> "{log_file}"
:retry_del
rd /S /Q "{target}" 2>>"{log_file}"
if exist "{target}" (
    set /a _CNT+=1
    if !_CNT! LSS 15 (
        timeout /t 1 /nobreak > NUL
        goto retry_del
    )
)
'''

    content = f'''@echo off
chcp 936 > NUL
setlocal EnableDelayedExpansion
set "_CNT=0"

echo. > "{log_file}"
echo [%DATE% %TIME%] MaaAuto uninstaller start >> "{log_file}"
echo   TARGET = {target} >> "{log_file}"
echo   PID    = {pid} >> "{log_file}"
echo   KEEP   = {str(keep_user_data).lower()} >> "{log_file}"

rem ---- 1) 等卸载器进程退出 ----
:waitloop
tasklist /FI "PID eq {pid}" /NH 2>NUL | find "{pid}" >NUL
if not errorlevel 1 (
    timeout /t 1 /nobreak > NUL
    goto waitloop
)
echo [%DATE% %TIME%] Uninstaller process exited >> "{log_file}"

rem ---- 2) 杀掉主程序（避免文件占用） ----
echo [%DATE% %TIME%] Killing MaaAuto.exe >> "{log_file}"
taskkill /F /IM MaaAuto.exe >NUL 2>&1
taskkill /F /IM MaaAuto.exe >NUL 2>&1
timeout /t 1 /nobreak > NUL

rem ---- 3) 切到 TEMP（避免删自己工作目录） ----
cd /D "%TEMP%"
echo [%DATE% %TIME%] cwd = %CD% >> "{log_file}"
{delete_block}
echo [%DATE% %TIME%] Cleanup finished >> "{log_file}"

rem ---- 4) 自删除 ----
del "%~f0" >NUL 2>&1
'''
    return content


def launch_delete_bat(install_dir: Path, keep_user_data: bool) -> bool:
    current_pid = os.getpid()
    content = build_bat_content(install_dir, current_pid, keep_user_data)

    bat_path = Path(tempfile.gettempdir()) / f"MaaAuto_uninstall_{int(time.time())}.bat"

    # 用 GBK 写入（Windows 中文系统）——不要用 utf-8-sig！
    try:
        bat_path.write_text(content, encoding="gbk", errors="replace")
    except UnicodeEncodeError:
        # 极端情况路径含非 GBK 字符，退化为 ASCII
        bat_path.write_text(content, encoding="ascii", errors="replace")

    try:
        subprocess.Popen(
            ["cmd", "/c", str(bat_path)],
            creationflags=0x00000008 | 0x00000200,  # DETACHED_PROCESS | NEW_PROCESS_GROUP
            close_fds=True,
            cwd=str(Path(tempfile.gettempdir())),   # ← cwd 设为 TEMP
        )
        return True
    except Exception as e:
        msg("卸载失败",
            f"无法启动后台清理脚本：\n\n{e}\n\n"
            f"脚本路径：{bat_path}",
            MB_OK | MB_ICONERROR)
        return False


# --------------------------------------------------------------------------- #
def main() -> int:
    install_dir = get_install_dir()
    manifest = read_manifest(install_dir)
    version = manifest.get("version", "")

    # 1) 确认卸载
    title = "MaaAuto 卸载程序"
    text = f"将从以下位置删除 MaaAuto：\n\n{install_dir}\n"
    if version:
        text += f"\n版本：{version}\n"
    text += "\n是否继续？\n\n（桌面 / 开始菜单快捷方式也会一并删除）"

    r = msg(title, text, MB_YESNO | MB_ICONQUESTION | MB_DEFBUTTON2)
    if r != IDYES:
        return 0

    # 2) 是否保留用户数据
    r2 = msg(
        "保留用户数据",
        "是否保留用户配置 (config\\) 和日志 (logs\\)？\n\n"
        "  「是」→ 保留，方便以后重装恢复\n"
        "  「否」→ 全部删除（推荐）",
        MB_YESNO | MB_ICONQUESTION | MB_DEFBUTTON2,
    )
    keep_user_data = (r2 == IDYES)

    # 3) 立即删快捷方式
    remove_shortcuts()

    # 4) 后台清理
    ok = launch_delete_bat(install_dir, keep_user_data)
    if ok:
        msg("卸载中",
            "MaaAuto 正在被删除...\n\n"
            "几秒后安装目录会被清理干净。\n"
            "如仍有残留，可手动删除该目录。",
            MB_OK | MB_ICONINFORMATION)
    return 0


if __name__ == "__main__":
    sys.exit(main())