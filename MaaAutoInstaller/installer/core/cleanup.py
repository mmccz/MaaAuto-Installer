"""
临时文件清理：
  - remove_work_dir：删除整个临时工作目录（Python + 源码 + dist）
  - clean_pip_cache：清理用户全局 pip 缓存（可选，节省磁盘）
  - clean_system_temp：清理系统临时目录里我们产生的文件

清理失败的兜底策略（重要）：
  ① 直接 shutil.rmtree
  ② 等 1.5 秒再试（杀软/子进程可能刚释放句柄）
  ③ cmd /c rmdir /s /q 强删
  ④ 写 VBS 到 %TEMP%，3 秒后隐藏执行强删（最可靠的最后手段）
"""

import os
import sys
import time
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Callable, Optional


def _log(logger, msg):
    if logger:
        try:
            logger(msg)
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# 删除整个工作目录
# --------------------------------------------------------------------------- #
def remove_work_dir(work_dir: Path,
                    log: Optional[Callable[[str], None]] = None) -> bool:
    """
    删除整个临时工作目录。这是安装成功后的核心清理动作。
    包含：Python 环境、源码、pip 装的所有依赖、dist 产物。

    :return: True 表示本次已删除；False 表示安排了延迟清理（或彻底失败）
    """
    if not work_dir:
        return False
    work_dir = Path(work_dir)
    if not work_dir.exists():
        return False

    _log(log, f"删除临时工作目录: {work_dir}")

    # ---- ① 直接删 ----
    try:
        shutil.rmtree(work_dir, ignore_errors=False)
        _log(log, "已删除")
        return True
    except Exception as e:
        _log(log, f"直接删除失败: {e}")

    # ---- ② 等一会儿再试（杀软 / 子进程可能刚释放句柄） ----
    time.sleep(1.5)
    try:
        shutil.rmtree(work_dir, ignore_errors=False)
        _log(log, "重试删除成功")
        return True
    except Exception:
        pass

    # ---- ③ cmd rmdir 强删 ----
    try:
        subprocess.run(
            ["cmd", "/c", "rmdir", "/s", "/q", str(work_dir)],
            creationflags=0x08000000 if os.name == "nt" else 0,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
        if not work_dir.exists():
            _log(log, "已通过 cmd 强删")
            return True
    except Exception:
        pass

    # ---- ④ VBS 延迟删除（最后的兜底） ----
    try:
        vbs = _schedule_vbs_delete(work_dir)
        _log(log, f"部分文件被占用，已安排延迟清理: {vbs.name}")
        return False
    except Exception as e:
        _log(log, f"延迟清理安排失败: {e}")
        return False


# --------------------------------------------------------------------------- #
# VBS 延迟删除
# --------------------------------------------------------------------------- #
def _schedule_vbs_delete(target: Path) -> Path:
    """
    写一个 VBS 到 %TEMP%，隐藏执行，等 3 秒后强删 target 目录，再自删。
    （wscript.exe 从 XP 起就自带，绝对可靠）
    """
    target = Path(target).resolve()
    ts = int(time.time())
    vbs_path = Path(tempfile.gettempdir()) / f"MaaAuto_cleanup_{ts}.vbs"

    content = f'''Option Explicit
Dim fso, target
Set fso = CreateObject("Scripting.FileSystemObject")
target = "{target}"

WScript.Sleep 3000

On Error Resume Next
If fso.FolderExists(target) Then
    fso.DeleteFolder target, True
End If
On Error Goto 0

On Error Resume Next
fso.DeleteFile WScript.ScriptFullName, True
On Error Goto 0
'''
    # 中文系统按 ANSI(GBK) 解码，用 GBK 写
    try:
        vbs_path.write_text(content, encoding="gbk", errors="replace")
    except Exception:
        vbs_path.write_text(content, encoding="utf-8-sig")

    FLAGS = 0x08000000 | 0x00000008   # CREATE_NO_WINDOW | DETACHED_PROCESS
    for exe in ("wscript.exe", "cscript.exe"):
        try:
            subprocess.Popen(
                [exe, "//B", "//Nologo", str(vbs_path)],
                creationflags=FLAGS,
                close_fds=True,
                cwd=str(Path(tempfile.gettempdir())),
            )
            return vbs_path
        except FileNotFoundError:
            continue
    raise RuntimeError("系统缺少 wscript.exe / cscript.exe")


# --------------------------------------------------------------------------- #
# 清理 pip 缓存（用户全局）
# --------------------------------------------------------------------------- #
def clean_pip_cache(python_exe: Optional[Path] = None,
                    log: Optional[Callable[[str], None]] = None) -> int:
    """
    清理 pip 缓存（位于 %LOCALAPPDATA%\\pip\\cache）。
    注意：这是用户全局缓存，会加速用户的其他 pip 项目——除非用户勾选清理，
    否则建议不主动调用。
    """
    removed = 0

    if python_exe and Path(python_exe).exists():
        try:
            subprocess.run(
                [str(python_exe), "-m", "pip", "cache", "purge"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=0x08000000 if os.name == "nt" else 0,
                timeout=30,
            )
            removed += 1
        except Exception:
            pass

    try:
        local = os.environ.get("LOCALAPPDATA")
        if local:
            cache = Path(local) / "pip" / "cache"
            if cache.exists():
                shutil.rmtree(cache, ignore_errors=True)
                removed += 1
                _log(log, f"已清理 pip 缓存: {cache}")
    except Exception:
        pass

    return removed


# --------------------------------------------------------------------------- #
# 清理系统临时目录里我们产生的文件
# --------------------------------------------------------------------------- #
def clean_system_temp(pattern_prefixes=("MaaAuto_", "maaauto_", ".MaaAuto_"),
                     log: Optional[Callable[[str], None]] = None) -> int:
    """
    删除 %TEMP% 下以 MaaAuto_ / maaauto_ / .MaaAuto_ 开头的文件/目录。
    包含：PyInstaller onefile 解压目录、我们写的清理 VBS、日志等。
    """
    temp = Path(tempfile.gettempdir())
    if not temp.exists():
        return 0

    removed = 0
    for item in temp.iterdir():
        name = item.name.lower()
        if not any(name.startswith(p.lower()) for p in pattern_prefixes):
            continue
        try:
            if item.is_dir():
                # 目录也可能被占用，用同一套兜底逻辑
                if not _rmtree_with_fallback(item):
                    continue
            else:
                item.unlink(missing_ok=True)
            removed += 1
        except Exception:
            pass

    if removed and log:
        try:
            log(f"清理系统临时文件: {removed} 项")
        except Exception:
            pass
    return removed


def _rmtree_with_fallback(path: Path) -> bool:
    """内部使用的轻量兜底删除。不写 VBS，避免无限套娃。"""
    try:
        shutil.rmtree(path, ignore_errors=False)
        return True
    except Exception:
        pass
    time.sleep(0.3)
    try:
        shutil.rmtree(path, ignore_errors=False)
        return True
    except Exception:
        pass
    try:
        subprocess.run(
            ["cmd", "/c", "rmdir", "/s", "/q", str(path)],
            creationflags=0x08000000 if os.name == "nt" else 0,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=15,
        )
        return not path.exists()
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# 一站式（可选）
# --------------------------------------------------------------------------- #
def full_cleanup(work_dir: Optional[Path] = None,
                 python_exe: Optional[Path] = None,
                 clean_pip: bool = False,
                 clean_temp: bool = True,
                 log: Optional[Callable[[str], None]] = None):
    """安装完成后的完整清理。"""
    if work_dir:
        remove_work_dir(work_dir, log=log)
    if clean_pip:
        clean_pip_cache(python_exe, log=log)
    if clean_temp:
        clean_system_temp(log=log)