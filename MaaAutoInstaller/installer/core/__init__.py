"""core：安装器/升级器的全部业务逻辑，不依赖 GUI。

3.0.0 起只剩三类能力：

* ``manifest``    —— ``.maaauto.json`` 读写
* ``payload``     —— 升级核心（查版本 / 下载 / 校验 / 替换 / 回滚）
* ``downloader``  —— 带进度的 HTTP 下载
"""

from installer.core.manifest import (Manifest, read_manifest, write_manifest,
                                     MANIFEST_NAME, MANIFEST_VERSION)
from installer.core.downloader import download_file, DownloadError
from installer.core.payload import (
    UpdateInfo, ApplyResult,
    parse_version, compare_versions, check_update, pick_payload_asset,
    sha256_of_file, is_main_running, request_main_exit,
    clear_upgrading_flag, write_failure_flag, clear_failure_flag,
    apply_payload, restart_main, read_launch_args,
    cleanup_old_exe, cleanup_backups,
    MAIN_EXE_NAME, UPGRADE_EXE_NAME, UPGRADE_FLAG_NAME, FAILURE_FLAG_NAME,
    DEFAULT_EXIT_TIMEOUT, DEFAULT_MIN_INSTALLER_VERSION,
)

__all__ = [
    "Manifest", "read_manifest", "write_manifest",
    "MANIFEST_NAME", "MANIFEST_VERSION",
    "download_file", "DownloadError",
    "UpdateInfo", "ApplyResult",
    "parse_version", "compare_versions", "check_update", "pick_payload_asset",
    "sha256_of_file", "is_main_running", "request_main_exit",
    "clear_upgrading_flag", "write_failure_flag", "clear_failure_flag",
    "apply_payload", "restart_main", "read_launch_args",
    "cleanup_old_exe", "cleanup_backups",
    "MAIN_EXE_NAME", "UPGRADE_EXE_NAME", "UPGRADE_FLAG_NAME", "FAILURE_FLAG_NAME",
    "DEFAULT_EXIT_TIMEOUT", "DEFAULT_MIN_INSTALLER_VERSION",
]
