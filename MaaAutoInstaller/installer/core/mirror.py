"""
镜像源选择。
- PyPI：pip 安装依赖用
- Python：embeddable Python 下载用

"auto" 策略：中文系统 → 国内镜像；其他 → 官方。
"""

import ctypes


# --------------------------------------------------------------------------- #
# 镜像表
# --------------------------------------------------------------------------- #
PYPI_MIRRORS = {
    "auto":   "",
    "tuna":   "https://pypi.tuna.tsinghua.edu.cn/simple",
    "aliyun": "https://mirrors.aliyun.com/pypi/simple",
    "ustc":   "https://pypi.mirrors.ustc.edu.cn/simple",
    "pypi":   "https://pypi.org/simple",
}

PYTHON_MIRRORS = {
    "auto":     "",
    "huawei":   "https://mirrors.huaweicloud.com/python/{version}/python-{version}-embed-amd64.zip",
    "official": "https://www.python.org/ftp/python/{version}/python-{version}-embed-amd64.zip",
}


# --------------------------------------------------------------------------- #
# 地区检测
# --------------------------------------------------------------------------- #
_CHINA_LANG_IDS = {
    0x0804,  # zh-CN 简体
    0x0404,  # zh-TW 繁体
    0x0C04,  # zh-HK 香港
    0x1004,  # zh-SG 新加坡
    0x1404,  # zh-MO 澳门
}


def detect_is_china() -> bool:
    """根据 Windows UI 语言判断是否中国大陆用户。"""
    try:
        lid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return lid in _CHINA_LANG_IDS
    except Exception:
        # 非 Windows 或调用失败：默认按国内处理（目标是 Windows 用户）
        return True


# --------------------------------------------------------------------------- #
# 解析
# --------------------------------------------------------------------------- #
def resolve_pypi_mirror(key: str) -> str:
    """
    key ∈ {"auto","tuna","aliyun","ustc","pypi"} 或直接的 URL。
    返回实际 URL。
    """
    if not key:
        key = "auto"
    if key.startswith(("http://", "https://")):
        return key
    if key == "auto":
        return PYPI_MIRRORS["tuna"] if detect_is_china() else PYPI_MIRRORS["pypi"]
    return PYPI_MIRRORS.get(key, PYPI_MIRRORS["pypi"])


def resolve_python_mirror(key: str, version: str) -> str:
    """key ∈ {"auto","huawei","official"} 或直接 URL 模板。"""
    if not key:
        key = "auto"
    if key.startswith(("http://", "https://")):
        return key.replace("{version}", version)
    if key == "auto":
        tmpl = PYTHON_MIRRORS["huawei"] if detect_is_china() else PYTHON_MIRRORS["official"]
    else:
        tmpl = PYTHON_MIRRORS.get(key, PYTHON_MIRRORS["official"])
    return tmpl.format(version=version)