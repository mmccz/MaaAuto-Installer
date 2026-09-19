"""
MaaAuto 升级器 stub（占位版）。
PyInstaller 打包后 → tools/_out/upgrade.exe
安装时被释放到 <install>/upgrade.exe。

当前行为：显示提示，引导用户下载新版安装器。
未来对接：读取 .maaauto.json → 检查 GitHub Release → 下载新 source.zip → 本地重打包。
"""

import sys
import os
import json
from pathlib import Path

import ctypes


MB_OK = 0x0
MB_ICONINFORMATION = 0x40
MB_ICONWARNING = 0x30


def msg(title, text, flags=MB_OK | MB_ICONINFORMATION):
    try:
        return ctypes.windll.user32.MessageBoxW(0, str(text), str(title), flags)
    except Exception:
        return 0


def get_install_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def read_manifest(install_dir: Path) -> dict:
    p = install_dir / ".maaauto.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    install_dir = get_install_dir()
    manifest = read_manifest(install_dir)
    version = manifest.get("version", "未知")
    github = manifest.get("extra", {}).get("github", "")

    text = (
        f"当前版本：{version}\n\n"
        "升级功能正在开发中，敬请期待。\n\n"
        "目前如需升级，请访问 GitHub Release 页面\n"
        "下载最新版安装器，安装到同一目录即可覆盖。"
    )
    if github:
        text += f"\n\n{github}"

    msg("MaaAuto 升级程序", text, MB_OK | MB_ICONINFORMATION)

    # 尝试打开浏览器（可选）
    if github:
        try:
            os.startfile(github)
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())