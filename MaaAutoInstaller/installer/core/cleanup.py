"""
临时文件清理：
  - remove_work_dir：删除整个临时工作目录（Python + 源码 + dist）
  - clean_pip_cache：清理用户全局 pip 缓存（可选，节省磁盘）
  - clean_system_temp：清理系统临时目录里我们产生的文件
"""

import os
import shutil
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
    """
    if not work_dir:
        return False
    work_dir = Path(work_dir)
    if not work_dir.exists():
        return False

    _log(log, f"删除临时工作目录: {work_dir}")
    try:
        shutil.rmtree(work_dir, ignore_errors=False)
        _log(log, "已删除")
        return True
    except Exception as e:
        # 有些文件可能被占用，退化为忽略错误重试
        _log(log, f"部分文件删除失败（重试）: {e}")
        shutil.rmtree(work_dir, ignore_errors=True)
        return not work_dir.exists()


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

    # 1) 让 pip 自己清
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

    # 2) 直接删目录
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
def clean_system_temp(pattern_prefixes=("MaaAuto_", "maaauto_"),
                     log: Optional[Callable[[str], None]] = None) -> int:
    """
    删除 %TEMP% 下以 MaaAuto_ / maaauto_ 开头的文件/目录。
    （比如 PyInstaller onefile 的解压目录、日志等）
    """
    import tempfile
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
                shutil.rmtree(item, ignore_errors=True)
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