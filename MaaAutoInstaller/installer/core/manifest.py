"""
.mmaaauto.json 读写。
这个文件是安装器与未来更新器之间的契约。
"""

import json
import datetime
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional


MANIFEST_NAME = ".maaauto.json"
MANIFEST_VERSION = 2


@dataclass
class Manifest:
    # ---- 版本 ----
    version: str = "0.0.0"              # MaaAuto 版本
    installer_version: str = "0.0.0"    # 安装器版本
    manifest_version: int = MANIFEST_VERSION

    # ---- 路径 ----
    install_dir: str = ""
    app_exe: str = ""                   # <install>/MaaAuto.exe
    uninstall_exe: str = ""             # <install>/uninstall.exe
    upgrade_exe: str = ""               # <install>/upgrade.exe

    # ---- 依赖信息 ----
    requirements_hash: str = ""         # requirements.txt 的 sha256
    mirror: str = ""                    # 实际使用的 PyPI 镜像

    # ---- 时间 ----
    installed_at: str = ""
    updated_at: str = ""

    # ---- 预留 ----
    extra: dict = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    def write(self, install_dir: Path) -> Path:
        path = Path(install_dir) / MANIFEST_NAME
        path.write_text(self.to_json(), encoding="utf-8")
        return path

    @classmethod
    def from_dict(cls, data: dict) -> "Manifest":
        valid = set(cls.__dataclass_fields__.keys())
        filtered = {k: v for k, v in (data or {}).items() if k in valid}
        return cls(**filtered)


def read_manifest(install_dir: Path) -> Optional[Manifest]:
    path = Path(install_dir) / MANIFEST_NAME
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Manifest.from_dict(data)
    except Exception:
        return None


def write_manifest(install_dir: Path, manifest: Manifest) -> Path:
    now = datetime.datetime.now().isoformat(timespec="seconds")
    if not manifest.installed_at:
        manifest.installed_at = now
    manifest.updated_at = now
    return manifest.write(install_dir)