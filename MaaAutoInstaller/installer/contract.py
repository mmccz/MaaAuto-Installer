"""安装器与主程序 ``MaaAutoProject/app_info.py`` 的冻结契约。

这里的值会写入安装目录的 ``.maaauto.json`` 的 ``extra``，升级器之后只读它。
协议约定（2026-09 冻结，2026-10-17 复核）：

* ``APP_UPDATE_API``       == ``extra.update_api``
* ``APP_SOURCE_ASSET``     == ``extra.source_asset_name``
* ``APP_MIN_INSTALLER_VERSION`` == ``extra.min_installer_version``

修改任一值等于协议变更，必须双方同时发版；构建期由
``build_installer.py::check_app_info_contract()`` 做强校验。
"""

from typing import Dict


def default_manifest_extra() -> Dict[str, object]:
    """返回一份全新的 ``Manifest.extra`` 默认值（调用方可安全修改）。"""
    return {
        "github_url": "https://github.com/mmccz/MaaAuto-Tool-works",
        "update_api": "https://api.github.com/repos/mmccz/MaaAuto-Tool-works/releases/latest",
        "release_channel": "stable",
        "launch_args": [],
        "source_asset_name": "MaaAuto_Source.zip",
        "online_asset_pattern": "MaaAuto_Online_*-Windows-x64.exe",
        "min_installer_version": "1.0.0",
    }


# extra 键 → app_info.py 常量名（构建期断言用）
APP_INFO_CONSTANTS = {
    "update_api": "APP_UPDATE_API",
    "source_asset_name": "APP_SOURCE_ASSET",
    "min_installer_version": "APP_MIN_INSTALLER_VERSION",
}
