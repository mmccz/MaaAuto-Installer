"""
升级器部署：
  从内嵌 stub（PyInstaller 打包的 upgrade.exe）复制到安装目录。
  真正的升级逻辑在 tools/upgrade_stub.py 里（目前是占位版）。
"""

import shutil
from pathlib import Path
from typing import Callable, Optional


def deploy_upgrader(embedded_stub: Path,
                    install_dir: Path,
                    log: Optional[Callable[[str], None]] = None) -> Path:
    """
    把内嵌的 upgrade.exe stub 复制到 <install>/upgrade.exe。
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
    dst = install_dir / "upgrade.exe"

    if not src.exists():
        raise FileNotFoundError(f"内嵌 upgrade stub 不存在: {src}")

    install_dir.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        try:
            dst.unlink()
        except Exception:
            pass

    shutil.copy2(src, dst)
    _log(f"升级器已就位: {dst.name}")
    return dst