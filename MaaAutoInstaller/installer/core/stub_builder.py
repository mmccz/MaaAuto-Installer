"""
本地打包 stub：uninstall.exe / upgrade.exe。

安装器不再内嵌已打包的 stub exe，而是内嵌 stub 源码 + installer/core 子集；
用户端安装时用刚下好的 embeddable Python + PyInstaller 现场打包。
这样安装器体积可减 ~50 MB（主要为 PySide6 相关）。

stubs_source.zip 结构约定（由 build_installer.py 生成）：
    uninstall_stub.py
    upgrade_stub.py
    VERSION
    resources/icon.ico
    installer/__init__.py
    installer/core/__init__.py            ← 最小化（空）
    installer/core/upgrade_engine.py
    installer/core/mirror.py
    installer/core/downloader.py
    installer/core/python_env.py
    installer/core/pip_installer.py
    installer/core/pyinstaller_builder.py
    installer/core/source_deployer.py
    installer/core/manifest.py
    installer/core/cleanup.py
"""

import os
import sys
import shutil
import zipfile
import subprocess
from pathlib import Path
from typing import Callable, Optional, Tuple


def _log(logger, msg):
    if logger:
        try:
            logger(msg)
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# 两个 stub 的 PyInstaller 配置
# --------------------------------------------------------------------------- #
_STUB_CONFIG = {
    "uninstall": {
        "script": "uninstall_stub.py",
        "icon": "resources/icon_uninstall.ico",
        # 只用标准库 + ctypes
        "excludes": [
            "PySide6", "PySide2", "PyQt5", "PyQt6",
            "matplotlib", "numpy", "scipy", "pandas",
            "PIL", "tkinter", "IPython", "jupyter", "notebook",
            "psutil", "pywin32", "win32com",
        ],
        "add_version": False,
        "add_icon": True,
        "uac_admin": True,
    },
    "upgrade": {
        "script": "upgrade_stub.py",
        "icon": "resources/icon_upgrade.ico",
        # upgrade 需要 PySide6（交互进度窗）
        "excludes": [
            "matplotlib", "numpy", "scipy", "pandas",
            "PIL", "IPython", "jupyter", "notebook",
            "psutil", "pywin32", "win32com",
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
        "add_version": True,
        "add_icon": True,
        "uac_admin": False,
    },
}

STUB_NAMES = tuple(_STUB_CONFIG.keys())


# --------------------------------------------------------------------------- #
# 解压 stubs_source.zip
# --------------------------------------------------------------------------- #
def unpack_stubs_source(zip_path: Path,
                        target_dir: Path,
                        log: Optional[Callable[[str], None]] = None) -> Path:
    """解压 stubs_source.zip 到 target_dir。"""
    zip_path = Path(zip_path)
    target_dir = Path(target_dir)

    if not zip_path.exists():
        raise FileNotFoundError(f"stubs_source.zip 不存在: {zip_path}")

    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)
    target_dir.mkdir(parents=True, exist_ok=True)

    size_kb = zip_path.stat().st_size / 1024
    _log(log, f"解压 stub 源码 ({size_kb:.0f} KB)...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(target_dir)

    # 校验关键文件
    for name in ("uninstall_stub.py", "upgrade_stub.py"):
        if not (target_dir / name).exists():
            raise RuntimeError(f"stub 源码不完整，缺少 {name}")

    _log(log, f"stub 源码已解压到 {target_dir}")
    return target_dir


# --------------------------------------------------------------------------- #
# 打包单个 stub
# --------------------------------------------------------------------------- #
def build_stub(name: str,
               python_exe: Path,
               stub_source_dir: Path,
               out_dir: Path,
               log: Optional[Callable[[str], None]] = None,
               timeout: int = 1800) -> Path:
    """
    用 PyInstaller 打包单个 stub。

    :param name: "uninstall" 或 "upgrade"
    :param python_exe: embeddable Python 解释器
    :param stub_source_dir: 解压后的 stub 源码根（含 uninstall_stub.py 等）
    :param out_dir: 产物输出目录
    :return: exe 路径
    """
    if name not in _STUB_CONFIG:
        raise ValueError(f"未知 stub: {name}")

    cfg = _STUB_CONFIG[name]
    stub_source_dir = Path(stub_source_dir).resolve()
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    script = stub_source_dir / cfg["script"]
    if not script.exists():
        raise FileNotFoundError(f"找不到 stub 脚本: {script}")

    # 清理旧的产物（避免复用）
    exe_path = out_dir / f"{name}.exe"
    if exe_path.exists():
        try:
            exe_path.unlink()
        except Exception:
            pass

    work = out_dir / f"_work_{name}"
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)

    icon_rel = cfg.get("icon", "resources/icon.ico")
    icon_src = stub_source_dir / icon_rel
    if not icon_src.exists():
        # fallback：找不到指定图标就用通用 icon.ico
        icon_src = stub_source_dir / "resources" / "icon.ico"

    icon_staged = work / "icon.ico"
    if icon_src.exists():
        shutil.copy2(icon_src, icon_staged)

    version_file = stub_source_dir / "VERSION"

    cmd = [
        str(python_exe), "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--name", name,
        "--onefile",
        "--windowed",
    ]
    if cfg.get("uac_admin"):
        cmd += ["--uac-admin"]
    cmd += [
        "--distpath", str(out_dir),
        "--workpath", str(work / "build"),
        "--specpath", str(work),
    ]
    if icon_staged.exists() and cfg.get("add_icon"):
        # exe 外壳图标
        cmd += ["--icon", str(icon_staged)]
        # 内嵌为 resources/icon.ico，供 Qt setWindowIcon 用
        cmd += ["--add-data", f"{icon_staged}{os.pathsep}resources"]
    for m in cfg.get("excludes", []):
        cmd += ["--exclude-module", m]
    # ★ 关键：把 stub 源码根加进 PyInstaller 搜索路径
    #   这样 upgrade_stub.py 能 `import installer.core.*`
    cmd += ["--paths", str(stub_source_dir)]
    if cfg.get("add_version") and version_file.exists():
        cmd += ["--add-data", f"{version_file}{os.pathsep}."]

    cmd.append(str(script))

    _log(log, f"[stub] 打包 {name} ...")

    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYI_DISABLE_UPX"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(stub_source_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=env,
            creationflags=0x08000000 if os.name == "nt" else 0,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except Exception as e:
        raise RuntimeError(f"启动 PyInstaller 失败: {e}") from e

    assert proc.stdout is not None
    try:
        for line in iter(proc.stdout.readline, ""):
            line = line.rstrip()
            if line:
                _log(log, line)
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise RuntimeError(f"打包 {name} 超时（{timeout} 秒）")

    if not exe_path.exists():
        raise RuntimeError(
            f"PyInstaller 退出码 {proc.returncode}，未生成 {exe_path}"
        )

    # 清理 PyInstaller 中间目录（保留 exe）
    shutil.rmtree(work, ignore_errors=True)

    size_mb = exe_path.stat().st_size / (1024 * 1024)
    _log(log, f"[stub] {name}.exe 完成 ({size_mb:.1f} MB)")
    return exe_path


# --------------------------------------------------------------------------- #
# 打包全部 stub（一次两个）
# --------------------------------------------------------------------------- #
def build_all_stubs(python_exe: Path,
                    stub_source_dir: Path,
                    out_dir: Path,
                    log: Optional[Callable[[str], None]] = None,
                    ) -> Tuple[Path, Path]:
    """
    依次打包 uninstall + upgrade。
    :return: (uninstall_exe, upgrade_exe)
    """
    uninstall_exe = build_stub("uninstall", python_exe,
                               stub_source_dir, out_dir, log=log)
    upgrade_exe = build_stub("upgrade", python_exe,
                             stub_source_dir, out_dir, log=log)
    return uninstall_exe, upgrade_exe