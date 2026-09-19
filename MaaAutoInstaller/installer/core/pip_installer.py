"""
pip 相关：
  - 为 embeddable Python 安装 pip（get-pip.py，优先官方源）
  - 升级 pip 到最新（避免老版本无法装 PySide6）
  - 预处理 requirements.txt 编码（剥离非 ASCII 字符）
  - 用 pip 安装 requirements.txt / PyInstaller
"""

import os
import subprocess
from pathlib import Path
from typing import Callable, Optional, List

from installer.core.downloader import download_file


# get-pip.py 地址：官方源优先（更可靠），镜像做 fallback
GET_PIP_OFFICIAL = "https://bootstrap.pypa.io/get-pip.py"
GET_PIP_MIRROR = "https://mirrors.aliyun.com/pypi/get-pip.py"


# --------------------------------------------------------------------------- #
# pip 检测
# --------------------------------------------------------------------------- #
def has_pip(python_exe: Path) -> bool:
    try:
        subprocess.check_output(
            [str(python_exe), "-m", "pip", "--version"],
            stderr=subprocess.DEVNULL, timeout=10,
            creationflags=0x08000000 if os.name == "nt" else 0,
        )
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# 安装 + 升级 pip
# --------------------------------------------------------------------------- #
def ensure_pip(python_exe: Path,
               log: Optional[Callable[[str], None]] = None,
               temp_dir: Optional[Path] = None,
               prefer_mirror: bool = True):
    """确保 python_exe 有 pip 可用，并升级到最新版。"""
    def _log(msg):
        if log:
            try:
                log(msg)
            except Exception:
                pass

    if has_pip(python_exe):
        _log("pip 已存在，跳过安装")
    else:
        _log("为 embeddable Python 安装 pip ...")
        if temp_dir is None:
            temp_dir = python_exe.parent.parent / "_dl"
        temp_dir = Path(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)

        get_pip = temp_dir / "get-pip.py"
        # 每次都重新下载，避免上次的陈旧快照（阿里云镜像的 get-pip 可能很旧）
        if get_pip.exists():
            try:
                get_pip.unlink()
            except Exception:
                pass

        # 优先官方源（get-pip.py 是动态脚本，官方更可靠）
        urls = [GET_PIP_OFFICIAL, GET_PIP_MIRROR]
        ok = False
        for url in urls:
            try:
                _log(f"下载 get-pip.py: {url}")
                download_file(url, get_pip, log=log)
                ok = True
                break
            except Exception as e:
                _log(f"  失败: {e}")
        if not ok:
            raise RuntimeError("无法下载 get-pip.py")

        run_pip_command(
            python_exe,
            [str(get_pip), "--no-warn-script-location"],
            log=log,
        )
        if not has_pip(python_exe):
            raise RuntimeError("pip 安装失败")
        _log("pip 安装完成")

    # ---- 升级 pip 到最新（关键：老版 pip 装不了 PySide6） ----
    _log("升级 pip 到最新版本 ...")
    try:
        run_pip_command(
            python_exe,
            ["-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel",
             "--no-warn-script-location",
             "--disable-pip-version-check",
             "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"],
            log=log,
            timeout=600,
        )
    except Exception as e:
        _log(f"pip 升级失败（继续使用当前版本）: {e}")


# --------------------------------------------------------------------------- #
# 预处理 requirements.txt（剥离非 ASCII 字符，避免 GBK 解码崩溃）
# --------------------------------------------------------------------------- #
def _sanitize_requirements(src: Path) -> Path:
    """
    读 requirements.txt（多编码尝试），过滤非 ASCII 字符，
    生成一个纯 ASCII 的临时文件给 pip 用。
    """
    src = Path(src)
    raw = src.read_bytes()

    text = None
    for enc in ("utf-8-sig", "utf-8", "gbk", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw.decode("latin-1", errors="replace")

    safe_lines = []
    for line in text.splitlines():
        # 去掉 `#` 后面的注释（注意 URL 里可能有 #，简单处理）
        code = line.split("#", 1)[0].rstrip()
        if not code:
            continue
        # 只保留纯 ASCII
        try:
            code.encode("ascii")
            safe_lines.append(code)
        except UnicodeEncodeError:
            continue

    tmp = src.parent / "_requirements_sanitized.txt"
    tmp.write_text("\n".join(safe_lines) + "\n", encoding="ascii")
    return tmp


# --------------------------------------------------------------------------- #
# 安装依赖
# --------------------------------------------------------------------------- #
def install_requirements(python_exe: Path,
                        requirements_file: Path,
                        pypi_mirror: str,
                        log: Optional[Callable[[str], None]] = None,
                        extra_args: Optional[List[str]] = None,
                        timeout_seconds: int = 3600):
    """使用 pip 安装 requirements.txt。逐行输出日志。"""
    def _log(msg):
        if log:
            try:
                log(msg)
            except Exception:
                pass

    requirements_file = Path(requirements_file)
    if not requirements_file.exists():
        raise FileNotFoundError(f"requirements 文件不存在: {requirements_file}")

    # ★ 预处理编码
    try:
        sanitized = _sanitize_requirements(requirements_file)
        _log(f"已规范化 requirements.txt（原始 {requirements_file.stat().st_size} 字节 → "
             f"{sanitized.stat().st_size} 字节）")
        requirements_file = sanitized
    except Exception as e:
        _log(f"requirements.txt 预处理失败（使用原始文件）: {e}")

    args = [
        "-m", "pip", "install",
        "--upgrade",
        "--no-warn-script-location",
        "--disable-pip-version-check",
        "-r", str(requirements_file),
    ]
    if pypi_mirror:
        args += ["-i", pypi_mirror]
    if extra_args:
        args += list(extra_args)

    _log(f"使用镜像: {pypi_mirror or '官方 PyPI'}")
    _log("开始安装依赖（首次约需 3-10 分钟）...")
    run_pip_command(python_exe, args, log=log, timeout=timeout_seconds)


# --------------------------------------------------------------------------- #
# 安装 PyInstaller
# --------------------------------------------------------------------------- #
def install_pyinstaller(python_exe: Path,
                        pypi_mirror: str,
                        log: Optional[Callable[[str], None]] = None,
                        timeout_seconds: int = 1800):
    """安装 PyInstaller（用于本地打包主程序）。"""
    def _log(msg):
        if log:
            try:
                log(msg)
            except Exception:
                pass

    args = [
        "-m", "pip", "install",
        "--upgrade",
        "--no-warn-script-location",
        "--disable-pip-version-check",
        "pyinstaller",
    ]
    if pypi_mirror:
        args += ["-i", pypi_mirror]

    _log("正在安装 PyInstaller ...")
    run_pip_command(python_exe, args, log=log, timeout=timeout_seconds)
    _log("PyInstaller 安装完成")


# --------------------------------------------------------------------------- #
# 底层
# --------------------------------------------------------------------------- #
def run_pip_command(python_exe: Path,
                    args: List[str],
                    log: Optional[Callable[[str], None]] = None,
                    timeout: int = 3600):
    """
    执行 python_exe <args>。
    - args 以 .py 结尾 → 直接执行脚本（get-pip.py）
    - args[0] == "-m"    → python -m ...
    - 其他              → python -m pip ...
    """
    if args and args[0].endswith(".py"):
        cmd = [str(python_exe)] + list(args)
    elif args and args[0] == "-m":
        cmd = [str(python_exe)] + list(args)
    else:
        cmd = [str(python_exe), "-m", "pip"] + list(args)

    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    # 让 pip 的子进程输出 UTF-8
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=env,
            creationflags=0x08000000 if os.name == "nt" else 0,
            bufsize=1,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception as e:
        raise RuntimeError(f"启动 pip 失败: {e}") from e

    assert proc.stdout is not None
    try:
        for line in iter(proc.stdout.readline, ""):
            line = line.rstrip()
            if not line:
                continue
            if log:
                try:
                    log(line)
                except Exception:
                    pass
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise RuntimeError(f"pip 执行超时（{timeout} 秒）")
    finally:
        try:
            proc.stdout.close()
        except Exception:
            pass

    if proc.returncode != 0:
        raise RuntimeError(f"pip 退出码 {proc.returncode}")