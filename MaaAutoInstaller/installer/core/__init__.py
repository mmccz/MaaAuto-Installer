"""core：安装器的全部业务逻辑。

所有模块不依赖 GUI，可在 QThread 中调用。
升级器（upgrade_stub.py）也直接复用这里的模块。
"""

# ---- manifest ----
from installer.core.manifest import (Manifest, read_manifest, write_manifest,
                                     MANIFEST_NAME, MANIFEST_VERSION)

# ---- mirror ----
from installer.core.mirror import (PYPI_MIRRORS, PYTHON_MIRRORS,
                                   resolve_pypi_mirror, resolve_python_mirror,
                                   detect_is_china)

# ---- downloader ----
from installer.core.downloader import (download_file, copy_with_progress,
                                       DownloadError)

# ---- source ----
from installer.core.source_deployer import unpack_source, hash_requirements

# ---- python env ----
from installer.core.python_env import (install_embedded_python,
                                       verify_python,
                                       get_python_version,
                                       PYTHON_VERSION)

# ---- pip ----
from installer.core.pip_installer import (ensure_pip,
                                           install_requirements,
                                           install_pyinstaller,
                                           has_pip)

# ---- pyinstaller 打包 ----
from installer.core.pyinstaller_builder import (build_main_program,
                                                copy_dist_to_install)

# ---- 卸载 / 升级（部署）----
from installer.core.uninstall import (deploy_uninstaller,
                                      is_uninstall_mode,
                                      find_install_dir_from_exe)
from installer.core.upgrade import deploy_upgrader

# ---- 清理 ----
from installer.core.cleanup import (remove_work_dir,
                                    clean_pip_cache,
                                    clean_system_temp,
                                    full_cleanup)

# ---- 注册表 ----
from installer.core.registry import (register_all, unregister_all,
                                     register_uninstall, unregister_uninstall,
                                     register_app_path, unregister_app_path,
                                     set_run_as_admin, clear_run_as_admin)
# ---- stub 本地打包 ----
from installer.core.stub_builder import (build_stub, build_all_stubs,
                                         unpack_stubs_source, STUB_NAMES)

# ---- 快捷方式 ----
from installer.core.shortcut import (create_desktop_shortcut,
                                     create_startmenu_shortcut,
                                     remove_desktop_shortcut,
                                     remove_startmenu_shortcut)

# ---- 升级引擎（必须在最后：它依赖上面所有模块）----
from installer.core.upgrade_engine import (
    # 数据类
    UpdateInfo, UpgradeResult,
    # 异常
    UpgradeCancelled,
    # 版本
    parse_version, compare_versions, check_installer_version,
    # 检查更新
    fetch_latest_release, check_update,
    # 下载
    sha256_of_file, download_source,
    # 主程序控制
    is_main_running, request_main_exit, clear_upgrading_flag,
    # 失败标记
    write_failure_flag, clear_failure_flag,
    # 备份 / 回滚
    backup_install, restore_backup, cleanup_backup,
    # 工作目录
    make_work_dir,
    # 版本号读取
    read_app_version,
    # 主流程
    perform_upgrade,
    # 常量
    MAIN_EXE_NAME, UPGRADE_FLAG_NAME, FAILURE_FLAG_NAME,
    DEFAULT_MIN_INSTALLER_VERSION, DEFAULT_EXIT_TIMEOUT,
)


__all__ = [
    # manifest
    "Manifest", "read_manifest", "write_manifest",
    "MANIFEST_NAME", "MANIFEST_VERSION",
    # mirror
    "PYPI_MIRRORS", "PYTHON_MIRRORS",
    "resolve_pypi_mirror", "resolve_python_mirror", "detect_is_china",
    # downloader
    "download_file", "copy_with_progress", "DownloadError",
    # source
    "unpack_source", "hash_requirements",
    # python env
    "install_embedded_python", "verify_python", "get_python_version",
    "PYTHON_VERSION",
    # pip
    "ensure_pip", "install_requirements", "install_pyinstaller", "has_pip",
    # pyinstaller
    "build_main_program", "copy_dist_to_install",
    # uninstall / upgrade（部署）
    "deploy_uninstaller", "is_uninstall_mode", "find_install_dir_from_exe",
    "deploy_upgrader",
    # cleanup
    "remove_work_dir", "clean_pip_cache", "clean_system_temp", "full_cleanup",
    # shortcut
    "create_desktop_shortcut", "create_startmenu_shortcut",
    "remove_desktop_shortcut", "remove_startmenu_shortcut",
    # upgrade engine
    "UpdateInfo", "UpgradeResult",
    "UpgradeCancelled",
    "parse_version", "compare_versions", "check_installer_version",
    "fetch_latest_release", "check_update",
    "sha256_of_file", "download_source",
    "is_main_running", "request_main_exit", "clear_upgrading_flag",
    "write_failure_flag", "clear_failure_flag",
    "backup_install", "restore_backup", "cleanup_backup",
    "make_work_dir",
    "read_app_version",
    "perform_upgrade",
    "MAIN_EXE_NAME", "UPGRADE_FLAG_NAME", "FAILURE_FLAG_NAME",
    "DEFAULT_MIN_INSTALLER_VERSION", "DEFAULT_EXIT_TIMEOUT",
    # stub 本地打包
    "build_stub", "build_all_stubs", "unpack_stubs_source", "STUB_NAMES",
    # registry
    "register_all", "unregister_all",
    "register_uninstall", "unregister_uninstall",
    "register_app_path", "unregister_app_path",
    "set_run_as_admin", "clear_run_as_admin",
]