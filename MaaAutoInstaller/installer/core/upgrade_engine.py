"""
升级引擎：纯逻辑，无 GUI 依赖。

复用 installer/core/* 的已有模块：
  - mirror              → 镜像解析
  - downloader          → 文件下载
  - python_env          → embeddable Python 部署
  - pip_installer       → pip 依赖安装
  - pyinstaller_builder → 本地重打包
  - source_deployer     → 源码解压
  - cleanup             → 临时目录清理

与安装器的差异：
  - 不需要释放 uninstall/upgrade stub（已存在）
  - 不需要创建快捷方式（默认跳过）
  - 覆盖 install_dir 时保留 config/ logs/ .maaauto.json
  - 失败时从备份回滚

约定（与 MaaAutoProject 冻结，2026-09）：
  - upgrade.exe 必须带 --from-main 参数（防止用户直接双击）
  - 版本比较：非法版本号判「无法比较」→ 不升级
  - 失败时写 <install>/config/upgrade_failed.flag
  - 备份放 %TEMP%/MaaAuto_backup_<ts>.zip
  - 工作目录放 <install_parent>/.MaaAuto_upgrade_<ts>/
  - 升级完成/失败后必须清 <install>/config/.upgrading，否则主程序启动即退出
"""

import os
import re
import sys
import json
import time
import shutil
import hashlib
import tempfile
import zipfile
import datetime
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Callable, Optional, Tuple, List, Dict, Any
from dataclasses import dataclass, field

from installer.core.mirror import (resolve_pypi_mirror, resolve_python_mirror)
from installer.core.downloader import download_file, DownloadError
from installer.core.python_env import (install_embedded_python, verify_python,
                                       get_python_version, PYTHON_VERSION)
from installer.core.pip_installer import (ensure_pip, install_requirements,
                                          install_pyinstaller)
from installer.core.pyinstaller_builder import (build_main_program,
                                                copy_dist_to_install)
from installer.core.source_deployer import (unpack_source, hash_requirements)
from installer.core.manifest import (Manifest, read_manifest, write_manifest,
                                     MANIFEST_NAME, MANIFEST_VERSION)
from installer.core.cleanup import (remove_work_dir, clean_pip_cache,
                                    clean_system_temp)


# --------------------------------------------------------------------------- #
# 常量
# --------------------------------------------------------------------------- #
MAIN_EXE_NAME = "MaaAuto.exe"
UPGRADE_FLAG_NAME = ".upgrading"
FAILURE_FLAG_NAME = "upgrade_failed.flag"
BACKUP_EXCLUDE_TOP = {"config", "logs"}
BACKUP_EXCLUDE_FILES = {MANIFEST_NAME}

# 主程序默认要求的最低升级器版本（如果 manifest.extra 没指定）
DEFAULT_MIN_INSTALLER_VERSION = "1.0.0"

USER_AGENT = "MaaAuto-UpgradeStub/1.0"

# 停止主程序的默认超时（秒）—— 5 秒给主程序 kill_all_related_processes 留足时间
DEFAULT_EXIT_TIMEOUT = 5.0


# --------------------------------------------------------------------------- #
# 数据类
# --------------------------------------------------------------------------- #
@dataclass
class UpdateInfo:
    has_update: bool = False
    current: str = ""
    latest: str = ""
    tag: str = ""
    source_url: str = ""
    source_sha256: str = ""
    notes: str = ""
    html_url: str = ""
    error: str = ""


@dataclass
class UpgradeResult:
    success: bool = False
    from_version: str = ""
    to_version: str = ""
    error: str = ""
    log_path: str = ""
    rolled_back: bool = False


# --------------------------------------------------------------------------- #
# 异常
# --------------------------------------------------------------------------- #
class UpgradeCancelled(Exception):
    """用户主动中止。"""
    pass


# --------------------------------------------------------------------------- #
# 内部工具
# --------------------------------------------------------------------------- #
def _log_cb(logger, msg):
    if logger:
        try:
            logger(msg)
        except Exception:
            pass


def _stage_cb(on_stage, key):
    if on_stage:
        try:
            on_stage(key)
        except Exception:
            pass


def _progress_cb(progress, cur, total):
    if progress:
        try:
            progress(int(cur), int(total))
        except Exception:
            pass


def _check_cancel(cancel_check):
    if cancel_check:
        try:
            if cancel_check():
                raise UpgradeCancelled("用户中止")
        except UpgradeCancelled:
            raise
        except Exception:
            pass


def _set_hidden(path: Path):
    """把目录设为隐藏（Windows 资源管理器默认看不到）。"""
    if os.name != "nt":
        return
    try:
        FILE_ATTRIBUTE_HIDDEN = 0x02
        import ctypes
        ctypes.windll.kernel32.SetFileAttributesW(str(path),
                                                  FILE_ATTRIBUTE_HIDDEN)
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# 版本比较（PEP 440 简化版，不引入 packaging 依赖）
# --------------------------------------------------------------------------- #
_VER_RE = re.compile(
    r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?"
    r"(?:(a|alpha|b|beta|rc)(\d*))?"
    r"(?:\.?(post)(\d*))?"
    r"$",
    re.IGNORECASE,
)


def parse_version(tag: str) -> Optional[Tuple[int, int, int, int, int, int]]:
    """
    解析 PEP 440 版本号为可比较元组。
    返回 (major, minor, patch, pre_rank, pre_num, post_num) 或 None。

    pre_rank: -3=alpha, -2=beta, -1=rc, 0=release, 1=post
    """
    if not tag:
        return None
    v = str(tag).strip().lstrip("vV")
    if not v:
        return None

    m = _VER_RE.match(v)
    if not m:
        return None

    major = int(m.group(1))
    minor = int(m.group(2) or 0)
    patch = int(m.group(3) or 0)
    pre_tag = (m.group(4) or "").lower()
    pre_num = int(m.group(5) or 0)
    is_post = bool(m.group(6))
    post_num = int(m.group(7) or 0)

    if pre_tag in ("a", "alpha"):
        pre_rank = -3
    elif pre_tag in ("b", "beta"):
        pre_rank = -2
    elif pre_tag == "rc":
        pre_rank = -1
    elif is_post:
        pre_rank = 1
    else:
        pre_rank = 0

    return (major, minor, patch, pre_rank, pre_num, post_num)


def compare_versions(a: str, b: str) -> Optional[int]:
    """
    返回 -1 / 0 / 1；任一无法解析 → None。
    a < b → -1
    a == b → 0
    a > b → 1
    """
    pa = parse_version(a)
    pb = parse_version(b)
    if pa is None or pb is None:
        return None
    if pa < pb:
        return -1
    if pa > pb:
        return 1
    return 0


def check_installer_version(manifest: Optional[Manifest],
                            min_installer_version: str = "") -> bool:
    """
    检查当前升级器版本是否满足主程序要求的下限。
    :return: True 表示满足（或无法判断，宽松处理）；False 表示版本过低
    """
    if manifest is None:
        return True

    # 优先用 manifest 里声明的，其次用默认值
    min_ver = min_installer_version or DEFAULT_MIN_INSTALLER_VERSION

    current = manifest.installer_version or "0.0.0"
    cmp = compare_versions(current, min_ver)
    if cmp is None:
        # 无法解析 → 宽松处理，避免误拦
        return True
    return cmp >= 0


# --------------------------------------------------------------------------- #
# 检查更新（GitHub Release API）
# --------------------------------------------------------------------------- #
def fetch_latest_release(update_api: str, timeout: int = 20) -> dict:
    """请求 GitHub Release API，返回 json dict。异常向上抛。"""
    req = urllib.request.Request(
        update_api,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_update(manifest: Optional[Manifest],
                 log: Optional[Callable[[str], None]] = None,
                 allow_downgrade: bool = False) -> UpdateInfo:
    """
    根据 manifest 的 extra.update_api 检查更新。
    任何失败都返回 UpdateInfo(has_update=False, error=...)，不抛异常。
    """
    if manifest is None:
        return UpdateInfo(has_update=False, error="manifest 为空")

    current = manifest.version or "0.0.0"
    extra = manifest.extra or {}
    update_api = extra.get("update_api", "")
    if not update_api:
        return UpdateInfo(has_update=False, current=current,
                          error="manifest 缺少 extra.update_api")

    if parse_version(current) is None:
        return UpdateInfo(has_update=False, current=current,
                          error=f"当前版本号无法解析: {current}")

    try:
        _log_cb(log, f"请求: {update_api}")
        release = fetch_latest_release(update_api)
    except urllib.error.HTTPError as e:
        return UpdateInfo(has_update=False, current=current,
                          error=f"HTTP {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        return UpdateInfo(has_update=False, current=current,
                          error=f"网络错误: {e.reason}")
    except Exception as e:
        return UpdateInfo(has_update=False, current=current,
                          error=f"请求失败: {e}")

    tag = release.get("tag_name", "") or ""
    if parse_version(tag) is None:
        return UpdateInfo(has_update=False, current=current, tag=tag,
                          error=f"远端版本号无法解析: {tag!r}")

    latest = tag.strip().lstrip("vV")

    cmp = compare_versions(current, latest)
    if cmp is None:
        return UpdateInfo(has_update=False, current=current, latest=latest,
                          tag=tag, error=f"无法比较: {current} vs {latest}")

    # 找 source asset
    source_asset_name = extra.get("source_asset_name", "MaaAuto_Source.zip")
    source_url = ""
    source_sha256 = ""
    for asset in release.get("assets", []) or []:
        if asset.get("name") == source_asset_name:
            source_url = asset.get("browser_download_url", "") or ""
            digest = asset.get("digest") or ""
            if digest.startswith("sha256:"):
                source_sha256 = digest[len("sha256:"):]
            break

    notes = release.get("body", "") or ""
    html_url = release.get("html_url", "") or ""

    if allow_downgrade:
        has_update = (cmp != 0)
    else:
        has_update = (cmp < 0)

    info = UpdateInfo(
        has_update=has_update,
        current=current,
        latest=latest,
        tag=tag,
        source_url=source_url,
        source_sha256=source_sha256,
        notes=notes,
        html_url=html_url,
    )
    if has_update and not source_url:
        info.has_update = False
        info.error = f"Release 里没有找到 asset: {source_asset_name}"
    return info


# --------------------------------------------------------------------------- #
# 下载 + 校验
# --------------------------------------------------------------------------- #
def sha256_of_file(path: Path) -> str:
    """公开版本：计算文件 sha256（供 stub 调用）。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download_source(url: str,
                    dest: Path,
                    log: Optional[Callable[[str], None]] = None,
                    progress: Optional[Callable[[int, int], None]] = None,
                    expected_sha256: str = "") -> Path:
    """
    下载 Source.zip 到 dest，可选 sha256 校验。
    :return: dest
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    download_file(url, dest, log=log, progress=progress)

    if expected_sha256:
        _log_cb(log, "校验 sha256 ...")
        actual = sha256_of_file(dest)
        if actual.lower() != expected_sha256.lower():
            try:
                dest.unlink()
            except Exception:
                pass
            raise RuntimeError(
                f"sha256 校验失败\n  期望: {expected_sha256}\n  实际: {actual}"
            )
        _log_cb(log, "sha256 校验通过")
    else:
        _log_cb(log, "（Release 未提供 sha256，跳过校验）")

    return dest


# --------------------------------------------------------------------------- #
# 检测 / 停止主程序
# --------------------------------------------------------------------------- #
def is_main_running(exe_name: str = MAIN_EXE_NAME) -> bool:
    """检测主程序是否在运行。"""
    if os.name != "nt":
        return False
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", f"IMAGENAME eq {exe_name}",
             "/FO", "CSV", "/NH"],
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000,
            timeout=10,
        ).decode("utf-8", errors="ignore")
        return exe_name.lower() in out.lower()
    except Exception:
        return False


def request_main_exit(install_dir: Path,
                      log: Optional[Callable[[str], None]] = None,
                      timeout: float = DEFAULT_EXIT_TIMEOUT) -> bool:
    """
    请求主程序优雅退出：
      1. 写 <install>/config/.upgrading 标志
      2. 等 timeout 秒
      3. 仍在跑 → taskkill /F
    :return: True 表示主程序已退出（或本来就没跑）
    """
    install_dir = Path(install_dir)

    if not is_main_running():
        _log_cb(log, "主程序未运行，无需停止")
        return True

    # 1. 写标志文件
    flag = install_dir / "config" / UPGRADE_FLAG_NAME
    try:
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.write_text("upgrading", encoding="utf-8")
        _log_cb(log, f"已写升级标志: {flag}")
    except Exception as e:
        _log_cb(log, f"写升级标志失败: {e}")

    # 2. 轮询等待
    steps = max(1, int(timeout * 10))
    for i in range(steps):
        if not is_main_running():
            _log_cb(log, f"主程序已优雅退出（{i / 10:.1f}s）")
            return True
        time.sleep(0.1)

    # 3. taskkill
    _log_cb(log, f"主程序 {timeout:.0f}s 内未退出，强制结束")
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", MAIN_EXE_NAME],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=0x08000000,
            timeout=15,
        )
        time.sleep(0.8)
        if not is_main_running():
            _log_cb(log, "主程序已被强制结束")
            return True
        _log_cb(log, "警告：taskkill 后主程序仍在运行")
        return False
    except Exception as e:
        _log_cb(log, f"taskkill 失败: {e}")
        return False


def clear_upgrading_flag(install_dir: Path):
    """删除 <install>/config/.upgrading 标志。"""
    try:
        flag = Path(install_dir) / "config" / UPGRADE_FLAG_NAME
        if flag.exists():
            flag.unlink()
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# 失败标记
# --------------------------------------------------------------------------- #
def write_failure_flag(install_dir: Path,
                       from_version: str,
                       to_version: str,
                       reason: str,
                       log_path: str = ""):
    """写 <install>/config/upgrade_failed.flag。"""
    try:
        flag = Path(install_dir) / "config" / FAILURE_FLAG_NAME
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.write_text(json.dumps({
            "failed_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "from_version": from_version,
            "to_version": to_version,
            "reason": reason,
            "log_path": log_path,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def clear_failure_flag(install_dir: Path):
    """删除 <install>/config/upgrade_failed.flag。"""
    try:
        flag = Path(install_dir) / "config" / FAILURE_FLAG_NAME
        if flag.exists():
            flag.unlink()
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# 备份 / 回滚
# --------------------------------------------------------------------------- #
def backup_install(install_dir: Path,
                   log: Optional[Callable[[str], None]] = None) -> Optional[Path]:
    """
    把 install_dir 里除 config/ logs/ .maaauto.json 之外的内容打包成 zip，
    存到 %TEMP%/MaaAuto_backup_<ts>.zip。
    :return: zip 路径；失败返回 None。
    """
    install_dir = Path(install_dir)
    if not install_dir.exists():
        return None

    ts = time.strftime("%Y%m%d_%H%M%S")
    zip_path = Path(tempfile.gettempdir()) / f"MaaAuto_backup_{ts}.zip"

    _log_cb(log, f"备份安装目录: {install_dir}")
    try:
        count = 0
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED,
                             compresslevel=6) as zf:
            for root, dirs, files in os.walk(install_dir):
                root_path = Path(root)
                try:
                    rel_root = root_path.relative_to(install_dir)
                except ValueError:
                    continue

                # 跳过顶层 config / logs
                if rel_root.parts and rel_root.parts[0].lower() in BACKUP_EXCLUDE_TOP:
                    dirs[:] = []
                    continue

                for fname in files:
                    if not rel_root.parts and fname in BACKUP_EXCLUDE_FILES:
                        continue
                    fpath = root_path / fname
                    try:
                        arcname = fpath.relative_to(install_dir).as_posix()
                        zf.write(fpath, arcname)
                        count += 1
                    except Exception as e:
                        _log_cb(log, f"  跳过 {fname}: {e}")

        size_mb = zip_path.stat().st_size / (1024 * 1024)
        _log_cb(log, f"备份完成: {count} 个文件, {size_mb:.1f} MB")
        return zip_path
    except Exception as e:
        _log_cb(log, f"备份失败: {e}")
        try:
            zip_path.unlink(missing_ok=True)
        except Exception:
            pass
        return None


def restore_backup(backup_zip: Path,
                   install_dir: Path,
                   log: Optional[Callable[[str], None]] = None) -> bool:
    """
    从备份 zip 恢复 install_dir 里除 config/ logs/ .maaauto.json 之外的内容。
    使用「rename → 解压 → 成功删/失败还原」三段式，避免解压中途崩溃导致数据丢失。

    :return: True 表示成功
    """
    backup_zip = Path(backup_zip)
    install_dir = Path(install_dir)

    if not backup_zip.exists():
        _log_cb(log, f"备份 zip 不存在: {backup_zip}")
        return False

    _log_cb(log, f"回滚: {backup_zip.name} → {install_dir}")

    # ---- 1. rename 现有非用户数据到 .old_<ts> ----
    ts = time.strftime("%Y%m%d_%H%M%S")
    stash = install_dir / f".old_{ts}"
    stash.mkdir(parents=True, exist_ok=True)
    moved: List[Tuple[Path, Path]] = []   # (原路径, 暂存路径)

    try:
        for item in list(install_dir.iterdir()):
            if item.name == stash.name:
                continue
            if item.name.lower() in BACKUP_EXCLUDE_TOP:
                continue
            if item.name in BACKUP_EXCLUDE_FILES:
                continue
            try:
                target = stash / item.name
                item.rename(target)
                moved.append((item, target))
            except Exception as e:
                _log_cb(log, f"  暂存 {item.name} 失败: {e}")
    except Exception as e:
        _log_cb(log, f"暂存现有内容失败: {e}")
        # 尝试把已 stash 的移回去
        for orig, stashed in reversed(moved):
            try:
                stashed.rename(orig)
            except Exception:
                pass
        shutil.rmtree(stash, ignore_errors=True)
        return False

    # ---- 2. 解压备份到 install_dir ----
    try:
        with zipfile.ZipFile(backup_zip, "r") as zf:
            zf.extractall(install_dir)
    except Exception as e:
        _log_cb(log, f"解压备份失败: {e}")
        # 清理半成品（可能污染 install_dir 的新解压内容）
        # 简化处理：删除 install_dir 里非用户数据内容，再把 stash 移回
        for item in list(install_dir.iterdir()):
            if item.name == stash.name:
                continue
            if item.name.lower() in BACKUP_EXCLUDE_TOP:
                continue
            if item.name in BACKUP_EXCLUDE_FILES:
                continue
            try:
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)
            except Exception:
                pass
        for orig, stashed in reversed(moved):
            try:
                stashed.rename(orig)
            except Exception:
                pass
        shutil.rmtree(stash, ignore_errors=True)
        return False

    # ---- 3. 成功：删 stash ----
    shutil.rmtree(stash, ignore_errors=True)
    _log_cb(log, "回滚完成")
    return True


def cleanup_backup(backup_zip: Path):
    """删除备份 zip。"""
    try:
        Path(backup_zip).unlink(missing_ok=True)
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# 工作目录
# --------------------------------------------------------------------------- #
def make_work_dir(install_dir: Path) -> Path:
    """
    创建临时工作目录，带隐藏属性。
    优先 <install_parent>/.MaaAuto_upgrade_<ts>，
    失败退 %TEMP%/MaaAuto_upgrade_<ts>。
    """
    ts = time.strftime("%Y%m%d_%H%M%S")

    try:
        parent = Path(install_dir).resolve().parent
        wd = parent / f".MaaAuto_upgrade_{ts}"
        wd.mkdir(parents=True, exist_ok=False)
        _set_hidden(wd)
        return wd
    except Exception:
        pass

    wd = Path(tempfile.gettempdir()) / f"MaaAuto_upgrade_{ts}"
    wd.mkdir(parents=True, exist_ok=True)
    return wd


# --------------------------------------------------------------------------- #
# 读版本号
# --------------------------------------------------------------------------- #
def read_app_version(source_dir: Path) -> str:
    """从 app_info.py 读 APP_VERSION。"""
    try:
        info = Path(source_dir) / "app_info.py"
        if info.exists():
            text = info.read_text(encoding="utf-8")
            m = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']*)["\']',
                          text, re.M)
            if m:
                return m.group(1)
    except Exception:
        pass
    return "0.0.0"


# --------------------------------------------------------------------------- #
# 主流程：执行完整升级（= 重跑一次安装）
# --------------------------------------------------------------------------- #
def perform_upgrade(install_dir: Path,
                    source_zip: Path,
                    manifest: Optional[Manifest],
                    installer_version: str = "1.0.0",
                    source_zip_sha256: str = "",
                    log: Optional[Callable[[str], None]] = None,
                    progress: Optional[Callable[[int, int], None]] = None,
                    on_stage: Optional[Callable[[str], None]] = None,
                    cancel_check: Optional[Callable[[], bool]] = None,
                    ) -> UpgradeResult:
    """
    执行完整升级。

    :param install_dir: 安装目录
    :param source_zip: 已下载的 MaaAuto_Source.zip 路径
    :param manifest: 当前 .maaauto.json 内容（可为 None）
    :param installer_version: 当前升级器版本号
    :param source_zip_sha256: 源包 sha256（非空时写入 manifest.source_hash）
    :param log: (msg) → None
    :param progress: (current, total) → None；total=0 表示未知
    :param on_stage: (stage_key: str) → None
                     取值：prepare / backup / download_python / unpack_source /
                          install_pip / install_deps / install_pyinstaller /
                          build_main / deploy / manifest / cleanup / done
    :param cancel_check: () → bool；返回 True 表示用户要求中止
    :return: UpgradeResult
    """
    install_dir = Path(install_dir).resolve()
    source_zip = Path(source_zip)

    old_version = manifest.version if manifest else "?"
    new_version = ""
    new_req_hash = ""
    backup_zip: Optional[Path] = None
    work_dir: Optional[Path] = None
    rolled_back = False

    if manifest is None:
        manifest = Manifest(install_dir=str(install_dir))

    # ---- 保险：清理上一次升级可能遗留的备份 ----
    try:
        import glob as _glob
        _old = _glob.glob(str(Path(tempfile.gettempdir()) / "MaaAuto_backup_*.zip"))
        for _p in _old:
            try:
                Path(_p).unlink()
            except Exception:
                pass
        if _old:
            _log_cb(log, f"清理历史备份: {len(_old)} 个")
    except Exception:
        pass

    try:
        # ---- 0. 准备 ----
        _check_cancel(cancel_check)
        _stage_cb(on_stage, "prepare")
        _log_cb(log, "=" * 48)
        _log_cb(log, f"升级开始：{old_version} → ?")
        _log_cb(log, f"安装目录: {install_dir}")
        _log_cb(log, "=" * 48)

        # ---- 1. 备份 ----
        _check_cancel(cancel_check)
        _stage_cb(on_stage, "backup")
        backup_zip = backup_install(install_dir, log=log)
        if backup_zip is None:
            _log_cb(log, "警告：备份失败，升级出错将无法自动回滚")

        # ---- 2. 创建工作目录 ----
        work_dir = make_work_dir(install_dir)
        _log_cb(log, f"临时工作目录: {work_dir}")

        # ---- 3. 下载 embeddable Python ----
        _check_cancel(cancel_check)
        _stage_cb(on_stage, "download_python")
        python_dir = work_dir / "python"
        python_mirror = resolve_python_mirror("auto", PYTHON_VERSION)
        _log_cb(log, f"Python 镜像: {python_mirror}")
        python_exe, _pythonw, python_dir = install_embedded_python(
            python_dir, python_mirror,
            log=log, progress=progress,
            temp_dir=work_dir / "_dl",
        )
        if not verify_python(python_exe):
            raise RuntimeError("Python 环境验证失败")
        _log_cb(log, f"Python 就绪: {python_exe} ({get_python_version(python_exe)})")

        # ---- 4. 解压源码 ----
        _check_cancel(cancel_check)
        _stage_cb(on_stage, "unpack_source")
        source_dir = work_dir / "source"
        unpack_source(source_zip, source_dir, log=log)
        new_version = read_app_version(source_dir)
        _log_cb(log, f"目标版本: {new_version}")

        # ---- 5. 装 pip（新增 stage key）----
        _check_cancel(cancel_check)
        _stage_cb(on_stage, "install_pip")
        ensure_pip(python_exe, log=log, temp_dir=work_dir / "_dl")

        # ---- 6. 装依赖 ----
        _check_cancel(cancel_check)
        _stage_cb(on_stage, "install_deps")
        pypi_url = resolve_pypi_mirror("auto")
        req_file = source_dir / "requirements.txt"
        if req_file.exists():
            install_requirements(python_exe, req_file, pypi_url, log=log)
            new_req_hash = hash_requirements(req_file)
        else:
            _log_cb(log, "未找到 requirements.txt，跳过依赖安装")
            new_req_hash = ""

        # ---- 7. 装 PyInstaller ----
        _check_cancel(cancel_check)
        _stage_cb(on_stage, "install_pyinstaller")
        install_pyinstaller(python_exe, pypi_url, log=log)

        # ---- 8. 打包主程序 ----
        _check_cancel(cancel_check)
        _stage_cb(on_stage, "build_main")
        dist_app_dir = build_main_program(source_dir, python_exe,
                                          log=log, timeout=1800)
        _log_cb(log, f"打包完成: {dist_app_dir}")

        # ---- 9. 拷贝产物到 install_dir ----
        _check_cancel(cancel_check)
        _stage_cb(on_stage, "deploy")
        _log_cb(log, "覆盖安装目录（保留 config/ logs/ .maaauto.json）")
        copy_dist_to_install(dist_app_dir, install_dir, log=log)

        # ---- 10. 更新 manifest ----
        _check_cancel(cancel_check)
        _stage_cb(on_stage, "manifest")
        manifest.version = new_version
        manifest.requirements_hash = new_req_hash
        manifest.installer_version = installer_version
        manifest.last_upgrade_from = old_version
        manifest.last_checked_at = datetime.datetime.now().isoformat(
            timespec="seconds")
        if source_zip_sha256:
            manifest.source_hash = source_zip_sha256
        write_manifest(install_dir, manifest)
        _log_cb(log, f"manifest 已更新: v{new_version}")

        # ---- 11. 完成 ----
        _stage_cb(on_stage, "done")
        _log_cb(log, "=" * 48)
        _log_cb(log, f"升级完成：{old_version} → {new_version}")
        _log_cb(log, "=" * 48)

        return UpgradeResult(
            success=True,
            from_version=old_version,
            to_version=new_version,
        )

    except UpgradeCancelled as e:
        _log_cb(log, f"升级中止: {e}")
        if backup_zip:
            rolled_back = restore_backup(backup_zip, install_dir, log=log)
        return UpgradeResult(
            success=False,
            from_version=old_version,
            to_version=new_version,
            error="用户中止",
            rolled_back=rolled_back,
        )

    except Exception as e:
        _log_cb(log, f"升级失败: {e}")
        if backup_zip:
            rolled_back = restore_backup(backup_zip, install_dir, log=log)
        return UpgradeResult(
            success=False,
            from_version=old_version,
            to_version=new_version,
            error=str(e),
            rolled_back=rolled_back,
        )

    finally:
        # ★ P1 修复：无论如何，必须清 .upgrading 标志
        #    否则升级成功重启的主程序会立即退出；失败后用户手动打开主程序也打不开
        try:
            clear_upgrading_flag(install_dir)
            _log_cb(log, "已清除 config/.upgrading 标志")
        except Exception as e:
            _log_cb(log, f"清除 .upgrading 标志失败: {e}")

        # 清理临时工作目录
        if work_dir and work_dir.exists():
            try:
                _stage_cb(on_stage, "cleanup")
                _log_cb(log, "清理临时工作目录...")
                remove_work_dir(work_dir, log=log)
                clean_system_temp(log=log)
            except Exception as e:
                _log_cb(log, f"清理临时目录失败: {e}")

        # 删备份（无论成功失败，回滚已在 except 里做完）
        if backup_zip:
            cleanup_backup(backup_zip)