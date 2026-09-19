"""统一下载工具（urllib 实现，支持进度回调 + 镜像回退）。"""

import os
import shutil
import urllib.request
import urllib.error
from pathlib import Path
from typing import Callable, Optional


class DownloadError(Exception):
    pass


USER_AGENT = "MaaAutoInstaller/1.0 (+https://github.com/mmccz/MaaAuto-Tool-works)"

# 分块大小：256 KB
CHUNK = 256 * 1024


def download_file(url: str,
                  dest: Path,
                  log: Optional[Callable[[str], None]] = None,
                  progress: Optional[Callable[[int, int], None]] = None,
                  timeout: int = 60) -> Path:
    """
    下载 url 到 dest。若 dest 已存在会被覆盖。

    :param log:      回调 (msg)
    :param progress: 回调 (current_bytes, total_bytes)；total=0 表示未知
    :return: dest
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    def _log(msg):
        if log:
            try:
                log(msg)
            except Exception:
                pass

    _log(f"下载 {url}")

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    tmp = dest.with_suffix(dest.suffix + ".part")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            total = int(resp.headers.get("Content-Length", 0) or 0)
            received = 0
            with open(tmp, "wb") as f:
                while True:
                    chunk = resp.read(CHUNK)
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)
                    if progress:
                        try:
                            progress(received, total)
                        except Exception:
                            pass
        # 下载完成，原子替换
        if dest.exists():
            dest.unlink()
        os.replace(tmp, dest)
    except urllib.error.HTTPError as e:
        _cleanup(tmp)
        raise DownloadError(f"HTTP {e.code} {e.reason}: {url}") from e
    except urllib.error.URLError as e:
        _cleanup(tmp)
        raise DownloadError(f"网络错误: {e.reason}") from e
    except Exception as e:
        _cleanup(tmp)
        raise DownloadError(f"下载失败: {e}") from e

    _log(f"下载完成: {dest.name} ({dest.stat().st_size / (1024*1024):.1f} MB)")
    return dest


def _cleanup(p: Path):
    try:
        if p.exists():
            p.unlink()
    except Exception:
        pass


def copy_with_progress(src: Path, dst: Path,
                       log: Optional[Callable[[str], None]] = None,
                       progress: Optional[Callable[[int, int], None]] = None,
                       chunk: int = 1024 * 1024) -> Path:
    """本地大文件复制（用于释放内嵌的 launcher.exe 等）。"""
    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    total = src.stat().st_size
    received = 0
    with open(src, "rb") as fi, open(dst, "wb") as fo:
        while True:
            buf = fi.read(chunk)
            if not buf:
                break
            fo.write(buf)
            received += len(buf)
            if progress:
                try:
                    progress(received, total)
                except Exception:
                    pass
    if log:
        try:
            log(f"复制 {src.name} → {dst}")
        except Exception:
            pass
    return dst