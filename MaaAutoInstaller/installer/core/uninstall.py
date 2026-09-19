"""
卸载器部署：
  从内嵌 stub（PyInstaller 打包的 uninstall.exe）复制到安装目录。
  真正的卸载逻辑在 tools/uninstall_stub.py 里。
"""

import shutil
from pathlib import Path
from typing import Callable, Optional

from installer.core.manifest import read_manifest


def deploy_uninstaller(embedded_stub: Path,
                       install_dir: Path,
                       log: Optional[Callable[[str], None]] = None) -> Path:
    """
    把内嵌的 uninstall.exe stub 复制到 <install>/uninstall.exe。
    :return: 目标路径
    """
    def _log(msg):
        if log:
            try:
                log(msg)
            except Exception:
                pass

    src = Path(embedded_stub)
    install_dir = Path(install_dir)
    dst = install_dir / "uninstall.exe"

    if not src.exists():
        raise FileNotFoundError(f"内嵌 uninstall stub 不存在: {src}")

    install_dir.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        try:
            dst.unlink()
        except Exception:
            pass

    shutil.copy2(src, dst)
    _log(f"卸载器已就位: {dst.name}")
    return dst


def is_uninstall_mode(argv0: str) -> bool:
    """
    兼容旧代码：根据 exe 文件名判断。
    新方案下卸载器是独立 stub，不依赖此判断。
    """
    try:
        stem = Path(argv0).stem.lower()
        return stem == "uninstall"
    except Exception:
        return False


def find_install_dir_from_exe(exe_path: Path) -> Optional[Path]:
    """卸载器所在目录，优先信 .maaauto.json。"""
    exe_path = Path(exe_path).resolve()
    parent = exe_path.parent
    m = read_manifest(parent)
    if m and m.install_dir:
        return Path(m.install_dir)
    return parent