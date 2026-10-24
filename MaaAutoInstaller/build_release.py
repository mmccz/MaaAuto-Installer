"""MaaAuto 3.0.0 一键构建（CI 与本机共用）。

产出（默认在 ``dist/``）::

    MaaAuto_payload_v{ver}.zip          ← 升级器下载
    MaaAuto_Setup_v{ver}-Windows-x64.exe ← 新用户下载（内嵌 payload）
    MaaAuto_Online_v{ver}-Windows-x64.exe← 在线引导包（约 2 MB）

流程：契约校验 → 主程序 build.py → 裁剪 payload → 打 upgrade.exe → 压 payload
→ Inno 编译完整包 → 计算 sha256 → Inno 编译在线包。
"""

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent          # MaaAutoInstaller/
REPO = HERE.parent                              # MaaAuto-Installer/
BUILD = HERE / "_build"
DIST = REPO / "dist"
TOOLS = HERE / "tools"
PACKAGING = HERE / "packaging"
RESOURCES = HERE / "resources"

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?(?:\.post\d+)?$")

ISCC_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
    Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    Path.home() / "AppData" / "Local" / "Programs" / "Inno Setup 6" / "ISCC.exe",
]


def log(msg: str) -> None:
    print(f"[build] {msg}", flush=True)


def err(msg: str) -> None:
    print(f"[build][ERROR] {msg}", file=sys.stderr, flush=True)


def human(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find_iscc(explicit: str = "") -> Path:
    if explicit:
        p = Path(explicit)
        if p.exists():
            return p
        raise FileNotFoundError(f"ISCC 不存在: {p}")

    # 候选路径（choco / winget / 手动安装的位置不一样）
    candidates = list(ISCC_CANDIDATES)
    for env_name in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        base = os.environ.get(env_name)
        if base:
            candidates.append(Path(base) / "Inno Setup 6" / "ISCC.exe")
            candidates.append(Path(base) / "Programs" / "Inno Setup 6" / "ISCC.exe")
    which = shutil.which("ISCC") or shutil.which("iscc")
    if which:
        candidates.insert(0, Path(which))

    for p in candidates:
        if p.exists():
            log(f"使用 ISCC: {p}")
            return p

    listed = "\n  ".join(str(p) for p in candidates)
    raise FileNotFoundError(
        "找不到 ISCC.exe（Inno Setup）。已尝试：\n  "
        f"{listed}\n请安装 Inno Setup 6（choco install innosetup）或传 --iscc。")


# --------------------------------------------------------------------------- #
# 契约
# --------------------------------------------------------------------------- #
def read_app_info(source_dir: Path) -> dict:
    text = (source_dir / "app_info.py").read_text(encoding="utf-8")
    keys = ["APP_VERSION", "APP_UPDATE_API",
            "APP_MIN_INSTALLER_VERSION", "APP_PAYLOAD_ASSET_PREFIX"]
    out = {}
    for key in keys:
        m = re.search(rf'^{key}\s*=\s*["\']([^"\']*)["\']', text, re.M)
        out[key] = m.group(1) if m else ""
    return out


def check_contract(source_dir: Path) -> dict:
    info = read_app_info(source_dir)
    version = info["APP_VERSION"]
    problems = []

    if not version:
        problems.append("APP_VERSION 缺失，或不是行首字符串常量")
    elif not VERSION_RE.match(version):
        problems.append(f"APP_VERSION={version!r} 不符合 X.Y.Z[(a|b|rc)N][.postN]")
    for key in ("APP_UPDATE_API", "APP_MIN_INSTALLER_VERSION",
                "APP_PAYLOAD_ASSET_PREFIX"):
        if not info[key]:
            problems.append(f"{key} 缺失")

    sys.path.insert(0, str(HERE))
    from installer.contract import default_manifest_extra, APP_INFO_CONSTANTS
    extra = default_manifest_extra()
    for extra_key, const_name in APP_INFO_CONSTANTS.items():
        if info.get(const_name) and info[const_name] != str(extra[extra_key]):
            problems.append(
                f"{const_name} 与 installer/contract.py 不一致："
                f"源码={info[const_name]!r}，安装器={extra[extra_key]!r}")

    if problems:
        raise RuntimeError("契约校验失败：\n  - " + "\n  - ".join(problems))
    log(f"契约校验通过: {version} / payload 前缀 {info['APP_PAYLOAD_ASSET_PREFIX']}")
    return info


# --------------------------------------------------------------------------- #
# 执行
# --------------------------------------------------------------------------- #
def run(cmd, cwd: Path, timeout: int = 3600, tag: str = "") -> None:
    log(f"执行{(' ' + tag) if tag else ''}: {' '.join(str(c) for c in cmd)}")
    proc = subprocess.Popen(
        [str(c) for c in cmd], cwd=str(cwd),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
    )
    assert proc.stdout is not None
    for line in iter(proc.stdout.readline, ""):
        line = line.rstrip()
        if line:
            print(f"  | {line}", flush=True)
    proc.wait(timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"命令失败（exit {proc.returncode}）: {cmd[0]}")


# --------------------------------------------------------------------------- #
# 步骤
# --------------------------------------------------------------------------- #
def build_main(source_dir: Path) -> Path:
    log("打包主程序（build.py）...")
    run([sys.executable, "build.py"], cwd=source_dir, tag="主程序")
    out = source_dir / "dist" / "MaaAuto"
    if not (out / "MaaAuto.exe").exists():
        raise RuntimeError(f"主程序产物缺失: {out / 'MaaAuto.exe'}")
    log(f"主程序产物: {out}")
    return out


def make_payload(main_dist: Path, trim: bool) -> Path:
    payload = BUILD / "payload"
    shutil.rmtree(payload, ignore_errors=True)
    log("复制产物为 payload...")
    shutil.copytree(main_dist, payload)

    if trim:
        log("裁剪 payload...")
        run([sys.executable, str(PACKAGING / "trim_payload.py"), str(payload), "--apply"],
            cwd=HERE, tag="裁剪")

    # payload 不应包含用户数据
    for name in ("config", "logs", ".maaauto.json"):
        p = payload / name
        if p.exists():
            shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink()
    return payload


def build_upgrade_exe(debug: bool) -> Path:
    out_dir = BUILD / "stub"
    shutil.rmtree(out_dir, ignore_errors=True)
    work = BUILD / "pyi_work"
    shutil.rmtree(work, ignore_errors=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile",
        "--console" if debug else "--windowed",
        "--name", "upgrade",
        "--noupx",
        "--icon", str(RESOURCES / "icon_upgrade.ico"),
        "--distpath", str(out_dir),
        "--workpath", str(work),
        "--specpath", str(BUILD),
        "--paths", str(HERE),
        "--hidden-import", "psutil",
        "--hidden-import", "installer.core.payload",
        str(TOOLS / "upgrade_stub.py"),
    ]
    log("打包 upgrade.exe ...")
    run(cmd, cwd=HERE, tag="upgrade.exe")
    exe = out_dir / "upgrade.exe"
    if not exe.exists():
        raise RuntimeError(f"upgrade.exe 未生成: {exe}")
    log(f"upgrade.exe: {human(exe.stat().st_size)}")
    return exe


def make_payload_zip(payload: Path, upgrade_exe: Path, version: str,
                     prefix: str) -> Path:
    shutil.copy2(upgrade_exe, payload / "upgrade.exe")
    out = BUILD / f"{prefix}{version}.zip"
    if out.exists():
        out.unlink()
    log("压缩 payload（LZMA）...")
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_LZMA) as zf:
        for p in sorted(payload.rglob("*")):
            if not p.is_file():
                continue
            zf.write(p, p.relative_to(payload).as_posix())
            count += 1
    log(f"payload: {count} 个文件，{human(out.stat().st_size)}")
    return out


def compile_installer(version: str, info: dict, payload_dir: Path,
                      iscc: Path) -> Path:
    exe_name = f"MaaAuto_Setup_v{version}-Windows-x64.exe"
    log("编译完整安装包（Inno Setup）...")
    run([
        iscc,
        f"/DMyAppVersion={version}",
        f"/DMyInstallerVersion={read_installer_version()}",
        f"/DMyUpdateApi={info['APP_UPDATE_API']}",
        f"/DMyPayloadPrefix={info['APP_PAYLOAD_ASSET_PREFIX']}",
        f"/DMyMinInstaller={info['APP_MIN_INSTALLER_VERSION']}",
        f"/DMyPayloadDir={payload_dir}",
        f"/DMyOutputDir={DIST}",
        f"/DMyIcon={RESOURCES / 'icon.ico'}",
        f"/DMySetupBase={exe_name[:-4]}",
        str(PACKAGING / "installer.iss"),
    ], cwd=HERE, tag="完整安装包")
    exe = DIST / exe_name
    if not exe.exists():
        raise RuntimeError(f"安装包未生成: {exe}")
    log(f"完整安装包: {human(exe.stat().st_size)}")
    return exe


def compile_online(version: str, setup_name: str, setup_sha: str,
                   iscc: Path) -> Path:
    url = (f"https://github.com/mmccz/MaaAuto-Tool-works/releases/download/"
           f"v{version}/{setup_name}")
    exe_name = f"MaaAuto_Online_v{version}-Windows-x64.exe"
    log("编译在线引导包（Inno Setup）...")
    run([
        iscc,
        f"/DMyAppVersion={version}",
        f"/DMySetupUrl={url}",
        f"/DMySetupSha256={setup_sha}",
        f"/DMyOutputDir={DIST}",
        f"/DMyIcon={RESOURCES / 'icon.ico'}",
        f"/DMyOnlineBase={exe_name[:-4]}",
        str(PACKAGING / "online.iss"),
    ], cwd=HERE, tag="在线引导包")
    exe = DIST / exe_name
    if not exe.exists():
        raise RuntimeError(f"在线引导包未生成: {exe}")
    log(f"在线引导包: {human(exe.stat().st_size)}")
    return exe


def read_installer_version() -> str:
    p = HERE / "VERSION"
    return p.read_text(encoding="utf-8").strip() if p.exists() else "0.0.0"


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="构建 MaaAuto 3.0.0 发布产物")
    ap.add_argument("--source-dir", type=Path, default=None,
                    help="主程序源码目录（默认自动探测）")
    ap.add_argument("--skip-main-build", action="store_true",
                    help="复用主程序已有 dist/MaaAuto")
    ap.add_argument("--skip-stub", action="store_true",
                    help="复用已有 _build/stub/upgrade.exe")
    ap.add_argument("--no-trim", action="store_true", help="不裁剪 payload")
    ap.add_argument("--keep-build", action="store_true", help="保留 _build/")
    ap.add_argument("--debug", action="store_true", help="upgrade.exe 保留控制台")
    ap.add_argument("--iscc", default="", help="ISCC.exe 路径")
    args = ap.parse_args()

    started = time.time()
    source_dir = (args.source_dir or default_source_dir()).resolve()
    if not (source_dir / "app_info.py").exists():
        err(f"源码目录无效: {source_dir}")
        return 1

    try:
        info = check_contract(source_dir)
    except Exception as e:
        err(str(e))
        traceback.print_exc()
        return 1

    version = info["APP_VERSION"]
    prefix = info["APP_PAYLOAD_ASSET_PREFIX"]
    try:
        iscc = find_iscc(args.iscc)
    except Exception as e:
        err(str(e))
        traceback.print_exc()
        return 1

    DIST.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)

    try:
        if args.skip_main_build:
            main_dist = source_dir / "dist" / "MaaAuto"
            if not (main_dist / "MaaAuto.exe").exists():
                raise RuntimeError(f"--skip-main-build 但产物不存在: {main_dist}")
            log(f"复用主程序产物: {main_dist}")
        else:
            main_dist = build_main(source_dir)

        payload = make_payload(main_dist, trim=not args.no_trim)

        if args.skip_stub:
            upgrade_exe = BUILD / "stub" / "upgrade.exe"
            if not upgrade_exe.exists():
                raise RuntimeError(f"--skip-stub 但不存在: {upgrade_exe}")
        else:
            upgrade_exe = build_upgrade_exe(args.debug)

        payload_zip = make_payload_zip(payload, upgrade_exe, version, prefix)
        shutil.copy2(payload_zip, DIST / payload_zip.name)

        setup = compile_installer(version, info, payload, iscc)
        setup_sha = sha256_of(setup)
        online = compile_online(version, setup.name, setup_sha, iscc)

        lines = []
        for p in (payload_zip, setup, online):
            lines.append(f"{sha256_of(p)}  {p.name}")
        (DIST / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

        if not args.keep_build:
            shutil.rmtree(BUILD / "pyi_work", ignore_errors=True)
            shutil.rmtree(BUILD / "payload", ignore_errors=True)
            spec = BUILD / "upgrade.spec"
            if spec.exists():
                spec.unlink()

        print()
        print("=" * 64)
        print(f"构建完成（{time.time() - started:.0f}s）→ {DIST}")
        print("=" * 64)
        for p in (setup, online, payload_zip):
            print(f"  {p.name:<52} {human(p.stat().st_size):>10}")
        print()
        print("README / Release 正文可直接引用 SHA256SUMS.txt")
        print()
        print("提示：如果本仓库目录被安全软件/沙箱标记为低完整性（Low IL），")
        print("      从 dist/ 直接双击安装包会报「无法创建目录 is-*.tmp，错误 5」。")
        print("      把 exe 复制到桌面或下载目录再运行即可。")
        return 0

    except Exception as e:
        err(str(e))
        traceback.print_exc()
        return 1


def default_source_dir() -> Path:
    candidates = [
        REPO.parent / "MaaAuto-Tool-works" / "MaaAutoProject",
        REPO / "MaaAuto-Tool-works" / "MaaAutoProject",
        REPO / "MaaAutoProject",
    ]
    for c in candidates:
        if (c / "app_info.py").exists():
            return c
    return candidates[0]


if __name__ == "__main__":
    raise SystemExit(main())
