"""
打包 uninstall_stub.py 和 upgrade_stub.py → tools/_out/*.exe

用法：
    python tools/build_stubs.py
    python tools/build_stubs.py --debug      # 保留控制台
    python tools/build_stubs.py --only uninstall
    python tools/build_stubs.py --only upgrade
"""

import sys
import shutil
import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = ROOT / "tools"
OUT_DIR = TOOLS_DIR / "_out"
ICON = ROOT / "resources" / "icon.ico"


# 两个 stub 的打包配置
STUBS = {
    "uninstall": {
        "script": TOOLS_DIR / "uninstall_stub.py",
        "name": "uninstall",
        # 只用标准库 + ctypes，排除所有重型依赖
        "excludes": [
            "PySide6", "PySide2", "PyQt5", "PyQt6",
            "matplotlib", "numpy", "scipy", "pandas",
            "PIL", "tkinter", "IPython", "jupyter", "notebook",
            "psutil", "pywin32", "win32com",
        ],
    },
    "upgrade": {
        "script": TOOLS_DIR / "upgrade_stub.py",
        "name": "upgrade",
        "excludes": [
            "PySide6", "PySide2", "PyQt5", "PyQt6",
            "matplotlib", "numpy", "scipy", "pandas",
            "PIL", "tkinter", "IPython", "jupyter", "notebook",
            "psutil", "pywin32", "win32com",
        ],
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

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--name", name,
        "--onefile",
        "--console" if debug else "--windowed",
        "--distpath", str(OUT_DIR),
        "--workpath", str(work_dir / "build"),
        "--specpath", str(work_dir),
    ]
    if ICON.exists():
        cmd += ["--icon", str(ICON)]
    for m in cfg["excludes"]:
        cmd += ["--exclude-module", m]

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

    # 清理临时
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