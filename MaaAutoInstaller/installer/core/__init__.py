"""core：安装器的全部业务逻辑。

所有模块不依赖 GUI，可在 QThread 中调用。
将来更新器可直接复用。
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

# ---- 卸载 / 升级 ----
from installer.core.uninstall import (deploy_uninstaller,
                                      is_uninstall_mode,
                                      find_install_dir_from_exe)
from installer.core.upgrade import deploy_upgrader

# ---- 清理 ----
from installer.core.cleanup import (remove_work_dir,
                                    clean_pip_cache,
                                    clean_system_temp,
                                    full_cleanup)

# ---- 快捷方式 ----
from installer.core.shortcut import (create_desktop_shortcut,
                                     create_startmenu_shortcut,
                                     remove_desktop_shortcut,
                                     remove_startmenu_shortcut)


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
    # uninstall / upgrade
    "deploy_uninstaller", "is_uninstall_mode", "find_install_dir_from_exe",
    "deploy_upgrader",
    # cleanup
    "remove_work_dir", "clean_pip_cache", "clean_system_temp", "full_cleanup",
    # shortcut
    "create_desktop_shortcut", "create_startmenu_shortcut",
    "remove_desktop_shortcut", "remove_startmenu_shortcut",
]