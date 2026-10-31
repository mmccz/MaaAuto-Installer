"""安装/卸载 smoke：静默安装 → 校验产物与 manifest → 静默卸载 → 确认清空。

与 ``verify_release.py`` 的区别：那个是**完整**验证（升级链路、假 Release、
开始菜单任务、数据保留…），本机手动跑；这个只保留发布前必须过的核心断言，
几分钟内跑完，供 ``release.yml`` 在「构建完成、发布 Release 之前」调用：

* 安装包装不上、manifest 写错、产物缺失、卸载残留 → 直接红在发布之前，
  不会把一个装不上的版本发出去；
* 不联网、不启动主程序（主程序要求管理员，CI 里弹 UAC 会挂），因此可安全跑在 runner。

用法（安装器仓库根目录）::

    python MaaAutoInstaller/tools/smoke_install.py 1.1.1
    python MaaAutoInstaller/tools/smoke_install.py v1.1.1 --keep
    python MaaAutoInstaller/tools/smoke_install.py --setup dist/MaaAuto_Setup_v1.1.1-Windows-x64.exe

退出码：0 = 全部通过；1 = 有断言失败或异常。
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# CI（cp1252 控制台）打印中文会崩，统一 UTF-8
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent          # MaaAutoInstaller/tools/
INSTALLER_ROOT = HERE.parent.parent             # MaaAuto-Installer/
INSTALLER_PKG = HERE.parent                     # MaaAutoInstaller/
DIST = INSTALLER_ROOT / "dist"
sys.path.insert(0, str(INSTALLER_PKG))   # MaaAutoInstaller/，包名叫 installer
from installer.core import shell_integration as shell  # noqa: E402

# 必须装在**独立目录**：Inno 的卸载注册表项 / 开始菜单组 / 桌面快捷方式按 AppId
# 全局共享，装在用户的正式安装目录（甚至用户自选的 D:\MaaAuto）上再卸载，会把
# 用户那份的登记信息一起删掉（1.4.1 踩过：「设置→应用」变成「系统找不到应用」）。
DEFAULT_DIR = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) \
    / "Programs" / "MaaAuto_verify"
START_MENU = shell.start_menu_group()
DESKTOP_LNK = shell.desktop_lnk()

fails = []


def check(name, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + name +
          (f"  [{detail}]" if detail and not cond else ""), flush=True)
    if not cond:
        fails.append(name)
    return cond


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd, timeout=600):
    print("  $ " + " ".join(str(c) for c in cmd), flush=True)
    try:
        return subprocess.run([str(c) for c in cmd], timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"  ! 超时（{timeout}s）", flush=True)
        return None


def uninstaller_alive():
    """Inno 卸载器会把自己复制到临时目录再执行，原进程秒退。

    所以要等这些副本进程（unins* / _iu*）退出，否则会误判「卸载完了」。
    """
    try:
        import psutil
    except ImportError:
        return False
    for proc in psutil.process_iter(["name"]):
        name = (proc.info.get("name") or "").lower()
        if name.startswith("unins") or name.startswith("_iu"):
            return True
    return False


def wait_gone(path, timeout=180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not path.exists() and not uninstaller_alive():
            return True
        time.sleep(0.5)
    return not path.exists()


def contract_extra():
    """安装器侧契约默认值；导入失败时返回空 dict（对应断言会失败）。"""
    sys.path.insert(0, str(INSTALLER_PKG))
    try:
        from installer.contract import default_manifest_extra
        return default_manifest_extra()
    except Exception as e:                       # 不应发生：同仓库同目录
        print(f"  ! 读取 contract.py 失败: {e}", flush=True)
        return {}


def find_setup(version_arg):
    version = (version_arg or "").strip().lstrip("vV")
    if version:
        path = DIST / f"MaaAuto_Setup_v{version}-Windows-x64.exe"
        if path.exists():
            return version, path
        print(f"  ! 指定版本找不到安装包: {path}", flush=True)
        return version, None
    candidates = sorted(DIST.glob("MaaAuto_Setup_v*-Windows-x64.exe"),
                        key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        return "", None
    path = candidates[0]
    version = path.name.split("MaaAuto_Setup_v")[1].split("-Windows-x64")[0]
    return version, path


def main():
    ap = argparse.ArgumentParser(description="安装/卸载 smoke（发布前必过）")
    ap.add_argument("version", nargs="?", default="",
                    help="版本号（可带 v 前缀）；缺省取 dist 里最新的 Setup")
    ap.add_argument("--setup", default="", help="直接指定 Setup 路径")
    ap.add_argument("--dir", default="",
                    help="安装目录（默认 %%LOCALAPPDATA%%\Programs\MaaAuto_verify；别指向正式安装目录）")
    ap.add_argument("--keep", action="store_true", help="不卸载（排查用）")
    args = ap.parse_args()

    print("=" * 72, flush=True)

    if args.setup:
        setup = Path(args.setup)
        version = (args.version or "").strip().lstrip("vV")
        if not version:
            version = setup.name.split("MaaAuto_Setup_v")[-1].split("-Windows-x64")[0]
    else:
        version, setup = find_setup(args.version)

    app_dir = Path(args.dir) if args.dir else DEFAULT_DIR
    default_app = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "MaaAuto"
    if app_dir.resolve() == default_app.resolve():
        print("  ! 拒绝在默认正式安装目录上跑 smoke（会删掉用户的安装与登记）",
              flush=True)
        return 1
    foreign = shell.foreign_install(app_dir)
    snapshot = shell.snapshot()
    print(f"  已备份外壳集成：{snapshot.summary()}", flush=True)
    if foreign is not None:
        print(f"  ! 本机另有一份安装：{foreign}（跑完会还原它的登记）", flush=True)

    print(f"[1] 安装包检查（版本 {version or '?'}）", flush=True)
    if not check("安装包存在", bool(setup) and setup.exists(), str(setup)):
        print("  找不到安装包，先跑 build_release.py。", flush=True)
        return 1
    check("版本号非空", bool(version))
    print(f"  大小 {setup.stat().st_size / 1024 / 1024:.1f} MB", flush=True)

    sums = setup.parent / "SHA256SUMS.txt"
    if sums.exists():
        listed = {}
        for line in sums.read_text(encoding="utf-8").splitlines():
            if line.strip():
                digest, name = line.split()
                listed[name] = digest
        check("SHA256SUMS 与安装包一致",
              listed.get(setup.name) == sha256_of(setup),
              f"sums={listed.get(setup.name)} actual={sha256_of(setup)}")

    # Low IL / 沙箱目录下 Inno 建临时目录会失败（错误 5），复制到 TEMP 再跑
    tmp_root = Path(tempfile.mkdtemp(prefix="maa_smoke_"))
    local_setup = tmp_root / setup.name
    shutil.copy2(setup, local_setup)

    print(f"[2] 静默安装 → {app_dir}", flush=True)
    # 清掉上次残留，否则「安装成功」可能是在看旧目录
    if app_dir.exists():
        shutil.rmtree(app_dir, ignore_errors=True)
        time.sleep(0.5)
    shell.clear_start_menu_group()

    proc = run([local_setup, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                f"/DIR={app_dir}", "/MERGETASKS=!startmenuicon"], timeout=900)
    check("安装退出码 0", proc is not None and proc.returncode == 0,
          "" if proc is None else str(proc.returncode))

    print("[3] 安装结果校验", flush=True)
    check("安装目录存在", app_dir.exists(), str(app_dir))
    check("主程序在", (app_dir / "MaaAuto.exe").exists())
    check("升级器在（自动升级依赖）", (app_dir / "upgrade.exe").exists())
    check("卸载器在", (app_dir / "unins000.exe").exists())
    check("_internal 已解包", (app_dir / "_internal").is_dir())
    # /MERGETASKS=!startmenuicon 必须生效，否则用户开始菜单会被塞快捷方式
    check("未创建开始菜单（任务参数生效）", not shell.start_menu_files(), str(START_MENU))

    manifest_path = app_dir / ".maaauto.json"
    manifest = {}
    if check("manifest 存在", manifest_path.exists(), str(manifest_path)):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            check("manifest 是合法 JSON", False, str(e))
    if manifest:
        check(f"manifest.version = {version}", manifest.get("version") == version,
              str(manifest.get("version")))
        check(f"manifest.installer_version = {version}",
              manifest.get("installer_version") == version,
              str(manifest.get("installer_version")))
        check("manifest_version = 3", manifest.get("manifest_version") == 3,
              str(manifest.get("manifest_version")))

        extra = manifest.get("extra") or {}
        expected = contract_extra()
        for key in ("update_api", "payload_asset_prefix", "min_installer_version"):
            if key in expected:
                check(f"extra.{key} 与 contract.py 一致",
                      extra.get(key) == expected[key],
                      f"{extra.get(key)!r} != {expected[key]!r}")

    if args.keep:
        print(f"[4] --keep：跳过卸载，安装目录保留在 {app_dir}", flush=True)
    else:
        print("[4] 静默卸载（/PURGEDATA）", flush=True)
        unins = app_dir / "unins000.exe"
        if unins.exists():
            proc = run([unins, "/VERYSILENT", "/SUPPRESSMSGBOXES",
                        "/NORESTART", "/PURGEDATA"], timeout=600)
            check("卸载退出码 0", proc is not None and proc.returncode == 0,
                  "" if proc is None else str(proc.returncode))
        check("安装目录已清空（无残留）", wait_gone(app_dir), str(app_dir))
        check("没有残留卸载器进程", not uninstaller_alive())

    if not args.keep:
        try:
            print(f"[5] 还原外壳集成：{shell.restore(snapshot)}", flush=True)
        except Exception as e:
            print(f"  ! 还原外壳集成失败({e})，可跑 tools/repair_integration.py",
                  flush=True)
            fails.append("还原外壳集成")
    shutil.rmtree(tmp_root, ignore_errors=True)

    print("=" * 72, flush=True)
    if fails:
        print(f"FAILED {len(fails)} 项：", flush=True)
        for name in fails:
            print(f"  - {name}", flush=True)
        return 1
    print("SMOKE OK：安装 → 校验 → 卸载 全部通过", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"异常: {e}", flush=True)
        raise SystemExit(1)
