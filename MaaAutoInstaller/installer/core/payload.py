"""payload 升级核心。

3.0.0 起，升级不再在用户机上编译：CI 产出 ``MaaAuto_payload_v{ver}.zip``
（主程序 onedir 产物 + 新版 upgrade.exe），升级器只负责

    查版本 → 下载 → 校验 sha256 → 解压到临时目录 → 备份并替换 → 更新 manifest

任何一步失败都回滚到升级前的文件集合。用户数据（``config/``、``logs/``、
``.maaauto.json``）永远不参与替换。
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from installer.core import delta as delta_mod
from installer.core.downloader import download_file, DownloadError
from installer.core.manifest import (Manifest, read_manifest, write_manifest,
                                     MANIFEST_NAME)

# --------------------------------------------------------------------------- #
# 常量
# --------------------------------------------------------------------------- #
MAIN_EXE_NAME = "MaaAuto.exe"
UPGRADE_EXE_NAME = "upgrade.exe"
UNINSTALL_EXE_NAME = "uninstall.exe"

UPGRADE_FLAG_NAME = ".upgrading"
FAILURE_FLAG_NAME = "upgrade_failed.flag"

# 顶层的这些名字不参与升级替换
PROTECTED_TOP = {"config", "logs", MANIFEST_NAME}

# 主程序收到 .upgrading 后要保存配置、等任务线程、杀子进程、退出 Qt
DEFAULT_EXIT_TIMEOUT = 15.0

# 清单里没有 extra.min_installer_version 时（1.0.0 之前装的旧版本）的兜底下限。
# 必须与 installer/contract.py 的 min_installer_version 基线一致：
# 之前写的是 3.0.0 —— 版本号重置后 1.x 的升级器永远「过旧」，老用户会被卡住。
DEFAULT_MIN_INSTALLER_VERSION = "1.0.0"
USER_AGENT = "MaaAutoUpgradeStub/3.0"

# 差分资产命名：``MaaAuto_delta_v{from}_to_{to}.zip``
# 与主程序 app_info.APP_DELTA_ASSET_PREFIX 保持一致（跨仓库契约，改了两边一起发版）。
DELTA_ASSET_PREFIX = "MaaAuto_delta_v"

_OLD_SUFFIX = ".old"


# --------------------------------------------------------------------------- #
# 版本
# --------------------------------------------------------------------------- #
def parse_version(text: str) -> Optional[Tuple[int, ...]]:
    """解析 ``X.Y.Z[(a|b|rc)N][.postN]``；失败返回 None。"""
    import re
    if not text:
        return None
    m = re.match(r"^[vV]?(\d+)\.(\d+)\.(\d+)(?:(a|b|rc)(\d+))?(?:\.post(\d+))?$",
                 text.strip())
    if not m:
        return None
    major, minor, patch = (int(m.group(i)) for i in (1, 2, 3))
    pre_kind = {"a": 0, "b": 1, "rc": 2}.get(m.group(4) or "", 3)
    pre_num = int(m.group(5) or 0)
    post = int(m.group(6) or 0)
    return (major, minor, patch, pre_kind, pre_num, post)


def compare_versions(a: str, b: str) -> Optional[int]:
    """>0 表示 a 比 b 新；解析失败返回 None。"""
    va, vb = parse_version(a), parse_version(b)
    if va is None or vb is None:
        return None
    return (va > vb) - (va < vb)


# --------------------------------------------------------------------------- #
# 查询
# --------------------------------------------------------------------------- #
@dataclass
class UpdateInfo:
    has_update: bool = False
    current: str = ""
    latest: str = ""
    tag: str = ""
    channel: str = "stable"
    payload_url: str = ""
    payload_name: str = ""
    payload_size: int = 0
    payload_sha: str = ""
    # 差分更新（Release 里有对应资产才用；失败自动回退整包）
    delta_url: str = ""
    delta_name: str = ""
    delta_size: int = 0
    delta_sha: str = ""
    # 跳版本时的串行差分：按顺序依次应用（每项是 GitHub 资产 dict）
    delta_chain: list = field(default_factory=list)
    notes: str = ""
    html_url: str = ""
    error: str = ""


def _request_json(url: str, timeout: int = 20):
    import urllib.request
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_latest_release(api: str, timeout: int = 20) -> dict:
    return _request_json(api, timeout)


def _list_api(update_api: str) -> str:
    """``.../releases/latest`` → ``.../releases``（beta 频道用）。"""
    base = (update_api or "").rstrip("/")
    if base.endswith("/latest"):
        base = base[: -len("/latest")]
    return base


def fetch_release(api: str, channel: str = "stable", timeout: int = 20) -> dict:
    """按频道取 Release。

    stable：只取 ``releases/latest``（GitHub 不返回 prerelease）；
    beta  ：取 ``releases`` 列表，忽略 draft，按版本号取最高（含 prerelease）。
    """
    if channel != "beta":
        return fetch_latest_release(api, timeout)

    releases = _request_json(_list_api(api), timeout)
    if not isinstance(releases, list):
        return {}
    candidates = []
    for rel in releases:
        if not isinstance(rel, dict) or rel.get("draft"):
            continue
        version = parse_version(rel.get("tag_name", ""))
        if version is not None:
            candidates.append((version, rel))
    if not candidates:
        return {}
    return max(candidates, key=lambda x: x[0])[1]


def _sha_from_asset(asset: dict) -> str:
    digest = (asset or {}).get("digest") or ""
    if digest.startswith("sha256:"):
        return digest.split(":", 1)[1].strip().lower()
    return ""


def pick_payload_asset(release: dict, version: str,
                       payload_prefix: str) -> Optional[dict]:
    """按固定命名规则找 payload：``{prefix}{version}.zip``。"""
    want = f"{payload_prefix}{version}.zip".lower()
    for asset in release.get("assets") or []:
        if (asset.get("name") or "").lower() == want:
            return asset
    return None


def pick_delta_asset(release: dict, current: str, latest: str) -> Optional[dict]:
    """找 ``MaaAuto_delta_v{current}_to_{latest}.zip``；没有就返回 None。"""
    if not current or parse_version(current) is None:
        return None
    want = f"{DELTA_ASSET_PREFIX}{current}_to_{latest}.zip".lower()
    for asset in release.get("assets") or []:
        if (asset.get("name") or "").lower() == want:
            return asset
    return None


def fetch_releases(api: str, timeout: int = 20, per_page: int = 60) -> list:
    """取 Release 列表（含旧版本），用于找「跳版本」的串行差分链。"""
    url = f"{_list_api(api)}?per_page={int(per_page)}"
    try:
        data = _request_json(url, timeout)
    except Exception:
        return []
    return data if isinstance(data, list) else []


def collect_delta_edges(releases) -> Dict[str, Dict[str, dict]]:
    """从所有 Release 的资产里收集 ``{from_version: {to_version: asset}}``。

    资产名规则：``{DELTA_ASSET_PREFIX}{from}_to_{to}.zip``。
    """
    edges: Dict[str, Dict[str, dict]] = {}
    prefix = DELTA_ASSET_PREFIX.lower()
    for rel in releases or []:
        if not isinstance(rel, dict) or rel.get("draft"):
            continue
        for asset in rel.get("assets") or []:
            name = (asset.get("name") or "").lower()
            if not (name.startswith(prefix) and name.endswith(".zip")):
                continue
            middle = name[len(prefix):-len(".zip")]
            if "_to_" not in middle:
                continue
            source, target = middle.split("_to_", 1)
            if parse_version(source) is None or parse_version(target) is None:
                continue
            edges.setdefault(source, {})[target] = asset
    return edges


def find_delta_chain(edges: Dict[str, Dict[str, dict]],
                     current: str, target: str,
                     max_hops: int = 4) -> list:
    """在差分图里找 ``current → target`` 的最短链（BFS）。找不到返回 ``[]``。"""
    if not current or current == target:
        return []
    queue = [(current, [])]
    seen = {current}
    while queue:
        node, path = queue.pop(0)
        if len(path) >= max_hops:
            continue
        for nxt, asset in (edges.get(node) or {}).items():
            if nxt in seen:
                continue
            new_path = path + [asset]
            if nxt == target:
                return new_path
            seen.add(nxt)
            queue.append((nxt, new_path))
    return []


def check_update(manifest: Optional[Manifest],
                 update_api: str,
                 payload_prefix: str,
                 allow_downgrade: bool = False,
                 log: Optional[Callable[[str], None]] = None,
                 channel: str = "stable") -> UpdateInfo:
    info = UpdateInfo()
    info.current = (manifest.version if manifest else "") or "0.0.0"
    info.channel = channel

    try:
        release = fetch_release(update_api, channel)
    except Exception as e:
        info.error = f"无法访问更新接口: {e}"
        return info
    if not release:
        info.error = "没有找到可用的 Release"
        return info

    info.tag = release.get("tag_name", "") or ""
    info.notes = release.get("body", "") or ""
    info.html_url = release.get("html_url", "") or ""

    latest = info.tag.lstrip("vV")
    if parse_version(latest) is None:
        info.error = f"无法解析远端版本号: {info.tag!r}"
        return info
    info.latest = latest

    cmp_result = compare_versions(latest, info.current)
    if cmp_result is None:
        info.error = f"无法比较版本: {latest!r} vs {info.current!r}"
        return info

    if cmp_result > 0:
        info.has_update = True
    elif cmp_result < 0 and allow_downgrade:
        info.has_update = True
    else:
        return info

    asset = pick_payload_asset(release, latest, payload_prefix)
    if not asset:
        info.error = (f"Release {info.tag} 里找不到 "
                      f"{payload_prefix}{latest}.zip")
        info.has_update = False
        return info

    info.payload_name = asset.get("name", "")
    info.payload_url = asset.get("browser_download_url", "")
    info.payload_size = int(asset.get("size") or 0)
    info.payload_sha = _sha_from_asset(asset)

    # 差分资产可选：只有「当前版本正好是某个 base」时才有，没有就整包
    delta_asset = pick_delta_asset(release, info.current, latest)
    if delta_asset:
        info.delta_name = delta_asset.get("name", "")
        info.delta_url = delta_asset.get("browser_download_url", "")
        info.delta_size = int(delta_asset.get("size") or 0)
        info.delta_sha = _sha_from_asset(delta_asset)
        info.delta_chain = [delta_asset]
    else:
        # 没有「上一版→本版」的直接差分：找串行链（1.2.0 → 1.3.0 → 1.4.0）
        chain = find_delta_chain(
            collect_delta_edges(fetch_releases(update_api)),
            info.current, latest)
        if chain:
            info.delta_chain = chain
            info.delta_name = chain[0].get("name", "")
            info.delta_url = chain[0].get("browser_download_url", "")
            info.delta_size = sum(int(a.get("size") or 0) for a in chain)
            info.delta_sha = _sha_from_asset(chain[0])
            if log:
                log("跳版本升级：可用串行差分 " + " → ".join(
                    [info.current] + [a.get("name", "")[len(DELTA_ASSET_PREFIX):-4]
                                      .split("_to_")[-1] for a in chain]))

    if log:
        via = f"，差分 {info.delta_size / 1048576:.1f} MB" if info.delta_url else ""
        log(f"发现新版本 {info.current} → {latest}，"
            f"payload {info.payload_size / 1048576:.1f} MB{via}")
    return info


# --------------------------------------------------------------------------- #
# 校验
# --------------------------------------------------------------------------- #
def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# 主程序进程
# --------------------------------------------------------------------------- #
def is_main_running(exe_name: str = MAIN_EXE_NAME) -> bool:
    try:
        import psutil
    except Exception:
        return False
    try:
        for proc in psutil.process_iter(["name"]):
            try:
                if (proc.info.get("name") or "").lower() == exe_name.lower():
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def request_main_exit(install_dir: Path,
                      timeout: float = DEFAULT_EXIT_TIMEOUT,
                      log: Optional[Callable[[str], None]] = None) -> bool:
    """写 ``.upgrading`` 并等待主程序退出；超时 taskkill。

    无论成功失败，只要走到 taskkill 分支就清理标志——标志的归属权在
    调用方（终态处理会再清一次）。
    """
    install_dir = Path(install_dir)

    def _log(msg):
        if log:
            try:
                log(msg)
            except Exception:
                pass

    if not is_main_running():
        _log("主程序未运行，无需停止")
        return True

    flag = install_dir / "config" / UPGRADE_FLAG_NAME
    try:
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.write_text("upgrading", encoding="utf-8")
        _log(f"已写升级标志: {flag}")
    except Exception as e:
        _log(f"写升级标志失败: {e}")

    steps = max(1, int(timeout * 10))
    for i in range(steps):
        if not is_main_running():
            _log(f"主程序已优雅退出（{i / 10:.1f}s）")
            return True
        time.sleep(0.1)

    _log(f"主程序 {timeout:.0f}s 内未退出，强制结束")
    try:
        subprocess.run(["taskkill", "/F", "/IM", MAIN_EXE_NAME],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=0x08000000, timeout=15)
        time.sleep(0.8)
        if not is_main_running():
            _log("主程序已被强制结束")
            return True
        _log("警告：taskkill 后主程序仍在运行")
    except Exception as e:
        _log(f"taskkill 失败: {e}")

    clear_upgrading_flag(install_dir)
    return False


# --------------------------------------------------------------------------- #
# 握手文件
# --------------------------------------------------------------------------- #
def clear_upgrading_flag(install_dir: Path) -> bool:
    flag = Path(install_dir) / "config" / UPGRADE_FLAG_NAME
    try:
        if flag.exists():
            flag.unlink()
        return True
    except Exception:
        return False


def write_failure_flag(install_dir: Path, from_version: str, to_version: str,
                       reason: str, log_path: str = "") -> None:
    flag = Path(install_dir) / "config" / FAILURE_FLAG_NAME
    try:
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.write_text(json.dumps({
            "failed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "from_version": from_version,
            "to_version": to_version,
            "reason": reason,
            "log_path": log_path,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def clear_failure_flag(install_dir: Path) -> None:
    flag = Path(install_dir) / "config" / FAILURE_FLAG_NAME
    try:
        if flag.exists():
            flag.unlink()
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# 备份 / 替换
# --------------------------------------------------------------------------- #
@dataclass
class ApplyResult:
    success: bool = False
    rolled_back: bool = False
    replaced: int = 0
    error: str = ""
    # 差分专用：本地文件与补丁基准不符（不是同一份安装）→ 调用方应回退整包
    base_mismatch: bool = False
    # 这次是走差分还是整包
    via_delta: bool = False


def _is_protected(rel: Path) -> bool:
    return bool(rel.parts) and rel.parts[0].lower() in PROTECTED_TOP


def _safe_extract(zip_path: Path, dest: Path) -> int:
    """解压并拒绝路径穿越；返回文件数。"""
    count = 0
    dest_resolved = dest.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            rel = Path(member.filename.replace("\\", "/"))
            if rel.is_absolute() or ".." in rel.parts:
                raise ValueError(f"payload 含非法路径: {member.filename}")
            target = (dest_resolved / rel).resolve()
            if not str(target).startswith(str(dest_resolved)):
                raise ValueError(f"payload 路径越界: {member.filename}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
            count += 1
    return count


def _walk_files(root: Path) -> List[Path]:
    return [p for p in root.rglob("*") if p.is_file()]


def _remove_running_exe_conflict(target: Path) -> Optional[Path]:
    """若目标正是当前运行的 upgrade.exe，先把它改名让位（Windows 允许改名运行中的 exe）。"""
    try:
        running = Path(sys.executable).resolve()
    except Exception:
        return None
    if target.resolve() != running:
        return None
    old = target.with_name(target.name + _OLD_SUFFIX)
    if old.exists():
        try:
            old.unlink()
        except Exception:
            pass
    os.replace(target, old)
    return old


def cleanup_old_exe(install_dir: Path) -> None:
    """删除上一次升级留下的 ``upgrade.exe.old``（本次运行已可删除）。"""
    old = Path(install_dir) / (UPGRADE_EXE_NAME + _OLD_SUFFIX)
    try:
        if old.exists():
            old.unlink()
    except Exception:
        pass


def cleanup_backups(install_dir: Path) -> None:
    """删除升级遗留的临时目录（成功路径），失败路径由回滚负责。"""
    parent = Path(install_dir).parent
    for pattern in (".MaaAuto_new_*", ".MaaAuto_bak_*"):
        for p in parent.glob(pattern):
            shutil.rmtree(p, ignore_errors=True)


def _commit_tree(new_dir: Path, bak_dir: Path, install_dir: Path,
                 delete_rels: List[str], _log,
                 progress: Optional[Callable[[int, int], None]] = None,
                 cancel_check: Optional[Callable[[], bool]] = None,
                 via_delta: bool = False) -> ApplyResult:
    """把准备好的 ``new_dir`` 覆盖到安装目录；失败按相反顺序回滚。

    整包与差分共用这一层：差分只是「new_dir 里只有变更文件，外加一个删除清单」。
    每个被替换/删除的文件都会先备份到 ``bak_dir``，所以回滚能把两边都还原。
    """
    moved_in: List[Path] = []
    backed_up: List[Tuple[Path, Path]] = []
    old_exe: Optional[Path] = None
    try:
        if cancel_check and cancel_check():
            raise RuntimeError("用户取消")

        files = _walk_files(new_dir)
        _log(f"开始替换 {len(files)} 个文件")
        for idx, src in enumerate(files, 1):
            rel = src.relative_to(new_dir)
            if _is_protected(rel):
                continue
            dst = install_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)

            if dst.exists():
                bak = bak_dir / rel
                bak.parent.mkdir(parents=True, exist_ok=True)
                # 运行中的 upgrade.exe 不能直接覆盖，先改名
                renamed = _remove_running_exe_conflict(dst)
                if renamed is not None:
                    old_exe = renamed
                else:
                    os.replace(dst, bak)
                    backed_up.append((dst, bak))

            os.replace(src, dst)
            moved_in.append(dst)

            if progress and idx % 200 == 0:
                progress(1 + idx / max(1, len(files)), 3)

        # 差分包可能带「上一版有、这一版删掉」的文件（如改名的 DLL）
        for rel_name in delete_rels or []:
            rel = Path(rel_name)
            if _is_protected(rel):
                continue
            dst = install_dir / rel
            if not dst.is_file():
                continue
            bak = bak_dir / rel
            bak.parent.mkdir(parents=True, exist_ok=True)
            os.replace(dst, bak)
            backed_up.append((dst, bak))
            _log(f"删除旧文件: {rel.as_posix()}")

        if progress:
            progress(2, 3)
        shutil.rmtree(new_dir, ignore_errors=True)
        shutil.rmtree(bak_dir, ignore_errors=True)
        _log("替换完成")
        return ApplyResult(success=True, replaced=len(moved_in), via_delta=via_delta)

    except Exception as e:
        _log(f"替换失败，开始回滚: {e}")
        # 先删掉已经放进去的新文件
        for dst in reversed(moved_in):
            try:
                if dst.exists():
                    dst.unlink()
            except Exception:
                pass
        # 再把备份放回去（含被删除的旧文件）
        for dst, bak in reversed(backed_up):
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                os.replace(bak, dst)
            except Exception:
                pass
        if old_exe is not None:
            try:
                target = install_dir / UPGRADE_EXE_NAME
                if target.exists():
                    target.unlink()
                os.replace(old_exe, target)
            except Exception:
                pass
        shutil.rmtree(new_dir, ignore_errors=True)
        shutil.rmtree(bak_dir, ignore_errors=True)
        return ApplyResult(success=False, rolled_back=True, error=str(e),
                           via_delta=via_delta)


def apply_payload(install_dir: Path,
                  payload_zip: Path,
                  log: Optional[Callable[[str], None]] = None,
                  progress: Optional[Callable[[int, int], None]] = None,
                  cancel_check: Optional[Callable[[], bool]] = None) -> ApplyResult:
    """解压整包 payload 并替换安装目录内的文件；失败自动回滚。"""
    install_dir = Path(install_dir).resolve()
    parent = install_dir.parent
    stamp = time.strftime("%Y%m%d_%H%M%S")
    new_dir = parent / f".MaaAuto_new_{stamp}"
    bak_dir = parent / f".MaaAuto_bak_{stamp}"

    def _log(msg):
        if log:
            try:
                log(msg)
            except Exception:
                pass

    if cancel_check and cancel_check():
        return ApplyResult(success=False, error="用户取消")

    # 1) 解压
    try:
        shutil.rmtree(new_dir, ignore_errors=True)
        new_dir.mkdir(parents=True, exist_ok=True)
        _log(f"解压 payload → {new_dir.name}")
        total = _safe_extract(payload_zip, new_dir)
        if not (new_dir / MAIN_EXE_NAME).exists():
            raise ValueError("payload 内缺少 MaaAuto.exe")
        _log(f"payload 解压完成：{total} 个文件")
        if progress:
            progress(1, 3)
    except Exception as e:
        shutil.rmtree(new_dir, ignore_errors=True)
        return ApplyResult(success=False, error=f"解压失败: {e}")

    # 2) 备份 + 替换
    return _commit_tree(new_dir, bak_dir, install_dir, [], _log,
                        progress=progress, cancel_check=cancel_check)


def apply_delta(install_dir: Path,
                delta_zip: Path,
                log: Optional[Callable[[str], None]] = None,
                progress: Optional[Callable[[int, int], None]] = None,
                cancel_check: Optional[Callable[[], bool]] = None) -> ApplyResult:
    """用差分包更新安装目录。

    ``result.base_mismatch=True`` 表示本地文件与补丁基准不符（不是同一份安装），
    调用方应改下整包，而不是报错给用户。
    """
    install_dir = Path(install_dir).resolve()
    parent = install_dir.parent
    stamp = time.strftime("%Y%m%d_%H%M%S")
    new_dir = parent / f".MaaAuto_new_{stamp}"
    bak_dir = parent / f".MaaAuto_bak_{stamp}"

    def _log(msg):
        if log:
            try:
                log(msg)
            except Exception:
                pass

    if cancel_check and cancel_check():
        return ApplyResult(success=False, error="用户取消")

    try:
        shutil.rmtree(new_dir, ignore_errors=True)
        new_dir.mkdir(parents=True, exist_ok=True)
        _log("还原差分包 ...")
        count, deletes = delta_mod.materialize(
            delta_zip, install_dir, new_dir, log=log,
            progress=progress, cancel_check=cancel_check)
        if not (new_dir / MAIN_EXE_NAME).exists():
            raise ValueError("差分包内缺少 MaaAuto.exe")
        _log(f"差分包还原完成：{count} 个文件，待删除 {len(deletes)} 个")
    except delta_mod.BaseMismatch as e:
        shutil.rmtree(new_dir, ignore_errors=True)
        _log(f"差分包不适用，将回退整包: {e}")
        return ApplyResult(success=False, base_mismatch=True,
                           error=f"基准版本不一致: {e}")
    except Exception as e:
        shutil.rmtree(new_dir, ignore_errors=True)
        return ApplyResult(success=False, error=f"还原失败: {e}")

    return _commit_tree(new_dir, bak_dir, install_dir, deletes, _log,
                        progress=progress, cancel_check=cancel_check,
                        via_delta=True)


# --------------------------------------------------------------------------- #
# 重启
# --------------------------------------------------------------------------- #
def apply_delta_chain(install_dir: Path,
                      delta_zips: list,
                      log: Optional[Callable[[str], None]] = None,
                      progress: Optional[Callable[[int, int], None]] = None,
                      cancel_check: Optional[Callable[[], bool]] = None) -> ApplyResult:
    """依次应用多个差分包（跳版本升级，如 1.2.0 → 1.3.0 → 1.4.0）。

    做法：先把安装目录复制成一份「工作副本」，在副本上逐级打补丁
    （每级都以副本当前内容为基准），全部成功后再一次性覆盖安装目录。
    好处是**整个链只有一次提交/回滚**：中间任何一步失败，安装目录都没被动过。
    """
    install_dir = Path(install_dir).resolve()
    parent = install_dir.parent
    stamp = time.strftime("%Y%m%d_%H%M%S")
    new_dir = parent / f".MaaAuto_new_chain_{stamp}"
    bak_dir = parent / f".MaaAuto_bak_chain_{stamp}"

    def _log(msg):
        if log:
            try:
                log(msg)
            except Exception:
                pass

    if cancel_check and cancel_check():
        return ApplyResult(success=False, error="用户取消")
    if not delta_zips:
        return ApplyResult(success=False, error="没有可用的差分包")

    try:
        shutil.rmtree(new_dir, ignore_errors=True)
        _log(f"准备链式升级（共 {len(delta_zips)} 步）...")
        ignore = shutil.ignore_patterns(*(list(PROTECTED_TOP) + ["unins*", ".MaaAuto_*"]))
        shutil.copytree(install_dir, new_dir, ignore=ignore)

        for idx, zip_path in enumerate(delta_zips, 1):
            if cancel_check and cancel_check():
                raise RuntimeError("用户取消")
            _log(f"应用第 {idx}/{len(delta_zips)} 个差分包: {Path(zip_path).name}")
            count, deletes = delta_mod.materialize(
                zip_path, new_dir, new_dir, log=log,
                progress=progress, cancel_check=cancel_check)
            for rel_name in deletes:
                target = new_dir / rel_name
                try:
                    if target.is_file():
                        target.unlink()
                except OSError:
                    pass
            _log(f"  第 {idx} 步完成：{count} 个文件")

        if not (new_dir / MAIN_EXE_NAME).exists():
            raise ValueError("链式升级结果缺少 MaaAuto.exe")
    except delta_mod.BaseMismatch as e:
        shutil.rmtree(new_dir, ignore_errors=True)
        _log(f"链式差分基准不符，将回退整包: {e}")
        return ApplyResult(success=False, base_mismatch=True,
                           error=f"基准版本不一致: {e}")
    except Exception as e:
        shutil.rmtree(new_dir, ignore_errors=True)
        return ApplyResult(success=False, error=f"链式升级失败: {e}")

    return _commit_tree(new_dir, bak_dir, install_dir, [], _log,
                        progress=progress, cancel_check=cancel_check,
                        via_delta=True)


def read_launch_args(install_dir: Path) -> List[str]:
    path = Path(install_dir) / "config" / "last_launch_args.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        args = data.get("args") or []
        return [str(a) for a in args if isinstance(a, str) and a != "--upgrading"]
    except Exception:
        return []


def restart_main(install_dir: Path,
                 log: Optional[Callable[[str], None]] = None) -> bool:
    install_dir = Path(install_dir)
    exe = install_dir / MAIN_EXE_NAME
    if not exe.exists():
        if log:
            log(f"未找到主程序: {exe}")
        return False
    args = [str(exe)] + read_launch_args(install_dir)
    try:
        subprocess.Popen(args, cwd=str(install_dir))
        if log:
            log(f"已重启主程序: {' '.join(args)}")
        return True
    except Exception as e:
        if log:
            log(f"重启主程序失败: {e}")
        return False
