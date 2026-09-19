"""
本地打包主程序：
  调用源码目录里的 build.py，产出 PyInstaller onedir 包。
  与主程序 build.py 完全解耦——安装器只负责"执行 + 拷贝结果"。
"""

import subprocess
import shutil
import os
import sys
from pathlib import Path
from typing import Callable, Optional


def _log(logger, msg):
    if logger:
        try:
            logger(msg)
        except Exception:
            pass


def build_main_program(
    source_dir: Path,
    python_exe: Path,
    log: Optional[Callable[[str], None]] = None,
    timeout: int = 3600,
    extra_args: Optional[list] = None,
) -> Path:
    """
    在 source_dir 里执行 build.py，返回 dist 下的 onedir 输出目录。

    约定（与 MaaAutoProject/build.py 一致）：
      - 主程序名 = "MaaAuto"
      - 产物位置 = <source_dir>/dist/MaaAuto/

    :return: 产物目录（如 <source_dir>/dist/MaaAuto/）
    """
    source_dir = Path(source_dir).resolve()
    python_exe = Path(python_exe).resolve()
    build_script = source_dir / "build.py"

    if not build_script.exists():
        raise FileNotFoundError(f"源码里没有 build.py: {build_script}")
    if not python_exe.exists():
        raise FileNotFoundError(f"Python 解释器不存在: {python_exe}")

    _log(log, f"调用 build.py: {build_script}")

    # 先清一次旧产物，避免 build.py 的 --noconfirm 处理不干净
    dist_dir = source_dir / "dist"
    build_dir = source_dir / "build"
    for p in (dist_dir, build_dir):
        if p.exists():
            _log(log, f"清空旧目录: {p.name}")
            shutil.rmtree(p, ignore_errors=True)

    # 执行 build.py（windowed 模式下 PyInstaller 会输出到 stdout，
    # 但 PyInstaller 本身不弹窗，所以在这里是安全的）
    cmd = [str(python_exe), str(build_script)]
    if extra_args:
        cmd += list(extra_args)

    _log(log, f"命令: {' '.join(cmd)}")
    _log(log, "打包主程序（可能耗时 1~5 分钟）...")

    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # 关掉 PyInstaller 的 UPX 压缩，避免杀软误报
    env["PYI_DISABLE_UPX"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"           # ← 新增
    env["PYTHONLEGACYWINDOWSSTDIO"] = "0"       # ← 新增
    env["PYTHONUTF8"] = "1"                     # ← 新增

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(source_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=env,
            creationflags=0x08000000 if os.name == "nt" else 0,  # CREATE_NO_WINDOW
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except Exception as e:
        raise RuntimeError(f"启动 build.py 失败: {e}") from e

    # 实时转发日志
    assert proc.stdout is not None
    try:
        for line in iter(proc.stdout.readline, ""):
            line = line.rstrip()
            if line:
                _log(log, line)
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise RuntimeError(f"打包超时（{timeout} 秒）")

    if proc.returncode != 0:
        raise RuntimeError(f"build.py 退出码 {proc.returncode}（打包失败）")

    # 校验输出
    out_dir = dist_dir / "MaaAuto"
    out_exe = out_dir / "MaaAuto.exe"

    if not out_exe.exists():
        # 真失败：产物不存在才 raise
        raise RuntimeError(
            f"build.py 退出码 {proc.returncode}，且未找到产物: {out_exe}\n"
            f"请检查 build.py 是否生成 dist/MaaAuto/MaaAuto.exe"
        )

    if proc.returncode != 0:
        # build.py 有报错但产物存在：警告，继续
        _log(log, f"⚠ build.py 返回码 {proc.returncode}，但产物已生成，继续安装")

    _log(log, f"打包完成: {out_dir}")
    return out_dir


def copy_dist_to_install(
    dist_app_dir: Path,
    install_dir: Path,
    log: Optional[Callable[[str], None]] = None,
) -> int:
    """
    把 dist/MaaAuto/ 里的所有内容拷到 install_dir/。
    覆盖同名文件（不删除 install_dir 里已有的其他文件）。
    """
    dist_app_dir = Path(dist_app_dir).resolve()
    install_dir = Path(install_dir).resolve()
    install_dir.mkdir(parents=True, exist_ok=True)

    if not dist_app_dir.exists():
        raise FileNotFoundError(f"打包产物不存在: {dist_app_dir}")

    _log(log, f"复制产物: {dist_app_dir} → {install_dir}")

    copied = 0
    for item in dist_app_dir.iterdir():
        dst = install_dir / item.name
        if item.is_dir():
            if dst.exists():
                shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(item, dst)
            copied += sum(1 for _ in dst.rglob("*") if _.is_file())
        else:
            if dst.exists():
                dst.unlink()
            shutil.copy2(item, dst)
            copied += 1

    _log(log, f"已复制 {copied} 个文件")
    return copied