"""
独立 Python 环境准备：
  下载 embeddable Python 3.11.9 → 解压到临时工作目录。
（新方案不再支持使用系统 Python）
"""

import os
import zipfile
import subprocess
from pathlib import Path
from typing import Callable, Optional, Tuple

from installer.core.downloader import download_file


PYTHON_VERSION = "3.11.9"
PYTHON_SHORT = "311"            # → python311._pth / python311.zip


# --------------------------------------------------------------------------- #
# 下载 + 解压
# --------------------------------------------------------------------------- #
def install_embedded_python(target_dir: Path,
                            mirror_url: str,
                            log: Optional[Callable[[str], None]] = None,
                            progress: Optional[Callable[[int, int], None]] = None,
                            temp_dir: Optional[Path] = None) -> Tuple[Path, Path, Path]:
    """
    下载 + 解压 embeddable Python 到 target_dir。

    :return: (python_exe, pythonw_exe, python_dir)
    """
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    if temp_dir is None:
        temp_dir = target_dir.parent / "_dl"
    temp_dir = Path(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    def _log(msg):
        if log:
            try:
                log(msg)
            except Exception:
                pass

    zip_path = temp_dir / f"python-{PYTHON_VERSION}-embed-amd64.zip"

    if not zip_path.exists():
        _log(f"从镜像下载 Python {PYTHON_VERSION} ...")
        download_file(mirror_url, zip_path, log=log, progress=progress)
    else:
        _log(f"复用已下载的 Python 包: {zip_path.name}")

    _log(f"解压到 {target_dir} ...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(target_dir)

    python_exe = target_dir / "python.exe"
    pythonw_exe = target_dir / "pythonw.exe"
    if not python_exe.exists():
        raise RuntimeError(f"解压后未找到 python.exe: {target_dir}")

    _patch_pth_file(target_dir, log=_log)

    return python_exe, pythonw_exe, target_dir


def _patch_pth_file(python_dir: Path, log=None):
    """
    修改 python311._pth 启用 site-packages：
        默认：
            python311.zip
            .
            #import site
        改为：
            python311.zip
            .
            Lib\\site-packages
            import site
    """
    pth = python_dir / f"python{PYTHON_SHORT}._pth"
    if not pth.exists():
        candidates = list(python_dir.glob("python*._pth"))
        if not candidates:
            if log:
                log("未找到 ._pth 文件，跳过 site-packages 配置")
            return
        pth = candidates[0]

    content = pth.read_text(encoding="utf-8", errors="ignore")
    lines = [ln.rstrip("\r\n") for ln in content.splitlines()]
    lines = [ln for ln in lines if ln.strip().lstrip("#").strip() != "import site"]

    if not any("site-packages" in ln for ln in lines):
        lines.append(r"Lib\site-packages")
    lines.append("import site")

    pth.write_text("\n".join(lines) + "\n", encoding="utf-8")

    sp = python_dir / "Lib" / "site-packages"
    sp.mkdir(parents=True, exist_ok=True)
    if log:
        log(f"已启用 site-packages: {sp}")


# --------------------------------------------------------------------------- #
# 验证
# --------------------------------------------------------------------------- #
def verify_python(python_exe: Path) -> bool:
    """确认 Python 能跑，且版本是 3.11。"""
    try:
        out = subprocess.check_output(
            [str(python_exe), "-c", "import sys; print(sys.version_info[:2])"],
            stderr=subprocess.DEVNULL, timeout=8,
            creationflags=0x08000000 if os.name == "nt" else 0,
        ).decode("utf-8", errors="ignore")
        return "3, 11" in out
    except Exception:
        return False


def get_python_version(python_exe: Path) -> str:
    """返回 "3.11.9" 这样的完整版本号。"""
    try:
        out = subprocess.check_output(
            [str(python_exe), "-c",
             "import sys; print('.'.join(map(str, sys.version_info[:3])))"],
            stderr=subprocess.DEVNULL, timeout=8,
            creationflags=0x08000000 if os.name == "nt" else 0,
        ).decode("utf-8", errors="ignore").strip()
        return out
    except Exception:
        return ""