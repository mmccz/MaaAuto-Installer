"""
源码解压：
  - 把 source.zip 解压到临时工作目录
  - 不再编译 .pyc（主程序由 PyInstaller 打包，会自己处理字节码）
  - 提供 requirements hash 工具
"""

import zipfile
import hashlib
import shutil
from pathlib import Path
from typing import Callable, Optional


def unpack_source(source_zip: Path,
                  target_dir: Path,
                  log: Optional[Callable[[str], None]] = None) -> Path:
    """
    解压 source.zip 到 target_dir。
    若 target_dir 已存在会先清空。
    """
    def _log(msg):
        if log:
            try:
                log(msg)
            except Exception:
                pass

    source_zip = Path(source_zip)
    target_dir = Path(target_dir)

    if not source_zip.exists():
        raise FileNotFoundError(f"source.zip 不存在: {source_zip}")

    if target_dir.exists():
        _log(f"清空旧目录: {target_dir}")
        shutil.rmtree(target_dir, ignore_errors=True)
    target_dir.mkdir(parents=True, exist_ok=True)

    size_kb = source_zip.stat().st_size / 1024
    _log(f"解压 source.zip ({size_kb:.0f} KB) ...")
    with zipfile.ZipFile(source_zip, "r") as zf:
        zf.extractall(target_dir)

    # 校验关键文件
    build_py = target_dir / "build.py"
    if not build_py.exists():
        raise RuntimeError(
            f"source.zip 里没有 build.py: {target_dir}\n"
            f"请确认打包时包含 build.py"
        )

    main_py = target_dir / "main.py"
    if not main_py.exists():
        raise RuntimeError(f"source.zip 里没有 main.py: {target_dir}")

    _log(f"源码已解压到 {target_dir}")
    return target_dir


def hash_requirements(requirements_file: Path) -> str:
    """sha256 摘要（用于更新器判断依赖是否变化）。"""
    p = Path(requirements_file)
    if not p.exists():
        return ""
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()