"""
打包 uninstall_stub.py 和 upgrade_stub.py → tools/_out/*.exe

用法：
    python tools/build_stubs.py
    python tools/build_stubs.py --debug      # 保留控制台
    python tools/build_stubs.py --only uninstall
    python tools/build_stubs.py --only upgrade
"""
import os
import sys
import shutil
import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = ROOT / "tools"
OUT_DIR = TOOLS_DIR / "_out"
ICON = ROOT / "resources" / "icon.ico"
VERSION_FILE = ROOT / "VERSION"


# 两个 stub 的打包配置
STUBS = {
    "uninstall": {
        "script": TOOLS_DIR / "uninstall_stub.py",
        "name": "uninstall",
        # ★ 卸载器专用图标
        "icon": ROOT / "resources" / "icon_uninstall.ico",
        # 只用标准库 + ctypes，排除所有重型依赖
        "excludes": [
            "PySide6", "PySide2", "PyQt5", "PyQt6",
            "matplotlib", "numpy", "scipy", "pandas",
            "PIL", "tkinter", "IPython", "jupyter", "notebook",
            "psutil", "pywin32", "win32com",
        ],
        "add_version": False,
        "extra_paths": [],
        "add_icon": True,
        "uac_admin": True,        # ★ 卸载需要管理员权限（删 HKLM 注册表）
    },
    "upgrade": {
        "script": TOOLS_DIR / "upgrade_stub.py",
        "name": "upgrade",
        # ★ 升级器专用图标
        "icon": ROOT / "resources" / "icon_upgrade.ico",
        # upgrade 需要 PySide6（交互进度窗），但不依赖其他重型库
        "excludes": [
            "matplotlib", "numpy", "scipy", "pandas",
            "PIL", "IPython", "jupyter", "notebook",
            "psutil", "pywin32", "win32com",
            # PySide6 里用不到的大模块
            "PySide6.QtWebEngineCore",
            "PySide6.QtWebEngineWidgets",
            "PySide6.Qt3DCore",
            "PySide6.QtMultimedia",
            "PySide6.QtQml",
            "PySide6.QtQuick",
            "PySide6.QtNetwork",
            "PySide6.QtSql",
            "PySide6.QtTest",
            "PySide6.QtOpenGL",
            "PySide6.QtOpenGLWidgets",
            "PySide6.QtSvg",
            "PySide6.QtSvgWidgets",
            "PySide6.QtPrintSupport",
            "PySide6.QtDBus",
        ],
        # upgrade stub 需要 import installer.core.*
        "extra_paths": [str(ROOT)],
        # 需要内嵌 VERSION 文件
        "add_version": True,
        "add_icon": True,
        "uac_admin": False,       # 升级不需要管理员权限
    },
}


def build_one(stub_key: str, debug: bool) -> Path:
    cfg = STUBS[stub_key]
    script = cfg["script"]
    name = cfg["name"]

    if not script.exists():
        raise FileNotFoundError(f"找不到 stub 脚本: {script}")

    work_dir = TOOLS_DIR / f"_work_{name}"
    if work_dir.exists():
        shutil.rmtree(work_dir, ignore_errors=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ★ 图标：把配置里指定的图标拷贝到工作目录并重命名为 icon.ico，
    #   这样 stub 源码里的 get_icon_path() 能在 _MEIPASS/resources/icon.ico 找到它
    icon_cfg = cfg.get("icon")
    icon_staged = work_dir / "icon.ico"
    if icon_cfg and Path(icon_cfg).exists():
        shutil.copy2(icon_cfg, icon_staged)
    elif ICON.exists():
        # 找不到专用图标时回退到通用图标
        print(f"[build_stubs] 警告：未找到 {icon_cfg}，使用默认 {ICON.name}")
        shutil.copy2(ICON, icon_staged)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--name", name,
        "--onefile",
        "--console" if debug else "--windowed",
    ]

    # ★ 管理员权限
    if cfg.get("uac_admin"):
        cmd += ["--uac-admin"]

    cmd += [
        "--distpath", str(OUT_DIR),
        "--workpath", str(work_dir / "build"),
        "--specpath", str(work_dir),
    ]

    # 外壳图标
    if icon_staged.exists() and cfg.get("add_icon"):
        cmd += ["--icon", str(icon_staged)]

    for m in cfg.get("excludes", []):
        cmd += ["--exclude-module", m]
    for p in cfg.get("extra_paths", []):
        cmd += ["--paths", p]

    if cfg.get("add_version") and VERSION_FILE.exists():
        cmd += ["--add-data", f"{VERSION_FILE}{os.pathsep}."]

    # ★ 内嵌 resources/icon.ico（供 Qt setWindowIcon 用）
    if cfg.get("add_icon") and icon_staged.exists():
        cmd += ["--add-data", f"{icon_staged}{os.pathsep}resources"]

    cmd.append(str(script))

    print(f"[build_stubs] 打包 {name} ...")
    print("[build_stubs] " + " ".join(
        f'"{x}"' if " " in x else x for x in cmd
    ))

    rc = subprocess.call(cmd, cwd=str(ROOT))
    if rc != 0:
        raise RuntimeError(f"{name} 打包失败（exit {rc}）")

    exe = OUT_DIR / f"{name}.exe"
    if not exe.exists():
        raise FileNotFoundError(f"未生成 {exe}")

    size_mb = exe.stat().st_size / (1024 * 1024)
    print(f"[build_stubs] {name}.exe 完成 ({size_mb:.1f} MB)")

    shutil.rmtree(work_dir, ignore_errors=True)
    return exe


def main():
    parser = argparse.ArgumentParser(description="打包 uninstall / upgrade stub")
    parser.add_argument("--debug", action="store_true",
                        help="保留控制台窗口（默认 windowed）")
    parser.add_argument("--only", choices=["uninstall", "upgrade"],
                        help="只打包其中一个")
    args = parser.parse_args()

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("请先安装 PyInstaller: pip install pyinstaller", file=sys.stderr)
        return 1

    keys = [args.only] if args.only else list(STUBS.keys())
    results = {}
    for k in keys:
        try:
            results[k] = build_one(k, args.debug)
        except Exception as e:
            print(f"[build_stubs] {k} 失败: {e}", file=sys.stderr)
            return 1

    print("[build_stubs] 全部完成 ✅")
    for k, p in results.items():
        print(f"  {k}: {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())