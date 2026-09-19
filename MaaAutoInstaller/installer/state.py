"""
安装过程的共享状态。
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class InstallState:
    # ---- 用户选择 ----
    install_dir: Optional[Path] = None
    mirror: str = ""
    create_desktop_shortcut: bool = True
    create_startmenu_shortcut: bool = True
    cleanup_after_install: bool = True
    launch_after_install: bool = True

    # ---- 临时工作目录（安装成功后整体删除）----
    work_dir: Optional[Path] = None
    work_dir_cleaned: bool = False        # ★ 新增：是否已成功清理
    python_dir: Optional[Path] = None
    python_exe: Optional[Path] = None
    source_dir: Optional[Path] = None
    dist_app_dir: Optional[Path] = None

    # ---- 从源码读到的信息 ----
    app_version: str = ""
    requirements_hash: str = ""

    # ---- 结果 ----
    success: bool = False
    error: str = ""

    # ---- 运行时状态 ----
    stage: str = ""
    log_lines: list = field(default_factory=list)

    # ---- 兼容字段 ----
    python_exe_console: Optional[Path] = None
    python_version: str = ""
    python_source: str = "bundled"
    system_python_version: Optional[str] = None

    # ------------------------------------------------------------------ #
    def add_log(self, line: str):
        self.log_lines.append(line)

    def set_stage(self, key: str):
        self.stage = key