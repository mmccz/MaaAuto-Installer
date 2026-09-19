"""
MaaAutoInstaller 一键构建脚本。

流程：
  1. 打包 ../MaaAutoProject/ 为 _embedded/source.zip
  2. 调用 tools/build_stubs.py 打包 uninstall.exe / upgrade.exe
  3. PyInstaller 打包 installer/ → dist/MaaAuto_Setup.exe（onefile）
       内嵌 uninstall.exe + upgrade.exe（用户端必需）
  4. 组合最终交付 zip：
        MaaAuto_Setup.exe        安装器
        MaaAuto_Source.zip       源码（安装器同级读取）
        README.txt

用法：
    python build_installer.py
    python build_installer.py --source-dir ../MaaAutoProject
    python build_installer.py --debug
    python build_installer.py --no-stub-rebuild
    python build_installer.py --keep-build
"""

import os
import re
import sys
import shutil
import argparse
import subprocess
import zipfile
from pathlib import Path

# --------------------------------------------------------------------------- #
# 路径
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parent
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
EMBEDDED_DIR = ROOT / "_embedded"
STUBS_OUT = ROOT / "tools" / "_out"
SPEC_FILE = ROOT / "MaaAuto_Setup.spec"
VERSION_FILE = ROOT / "VERSION"

DEFAULT_SOURCE_DIR = ROOT.parent / "MaaAutoProject"


# 打包源码时排除的目录 / 文件后缀
SOURCE_EXCLUDE_DIRS = {
    "__pycache__",
    ".git", ".github", ".gitignore", ".gitattributes",
    ".idea", ".vscode",
    "build", "dist",
    "config", "logs",
    "venv", ".venv", "env", ".env",
}
SOURCE_EXCLUDE_SUFFIXES = (".pyc", ".pyo", ".log", ".spec")


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #
def log(msg):
    print(f"[build] {msg}")


def err(msg):
    print(f"[build][ERROR] {msg}", file=sys.stderr)


def read_installer_version():
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text(encoding="utf-8").strip() or "0.0.0"
    return "0.0.0"


def read_app_version(source_dir: Path):
    p = source_dir / "app_info.py"
    if not p.exists():
        return "0.0.0"
    text = p.read_text(encoding="utf-8")
    m = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']*)["\']', text, re.M)
    return m.group(1) if m else "0.0.0"


def should_skip(name: str, path: Path):
    n = name.lower()
    if n in SOURCE_EXCLUDE_DIRS:
        return True
    if path.is_file():
        for suf in SOURCE_EXCLUDE_SUFFIXES:
            if n.endswith(suf):
                return True
    return False


# --------------------------------------------------------------------------- #
# 1) source.zip
# --------------------------------------------------------------------------- #
def build_source_zip(source_dir: Path, output_zip: Path) -> Path:
    if not source_dir.exists():
        raise FileNotFoundError(f"源码目录不存在: {source_dir}")

    log(f"打包源码: {source_dir} → {output_zip}")
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    if output_zip.exists():
        output_zip.unlink()

        count = 0
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for root, dirs, files in os.walk(source_dir):
            root_path = Path(root)
            dirs[:] = [d for d in dirs if not should_skip(d, root_path / d)]
            for fname in files:
                fpath = root_path / fname
                if should_skip(fname, fpath):
                    continue
                arcname = fpath.relative_to(source_dir)
                zf.write(fpath, arcname.as_posix())
                count += 1

        # ← 新增：若 source_dir 里没有 requirements.txt，尝试从上级补齐
        req_in_source = source_dir / "requirements.txt"
        if not req_in_source.exists():
            for candidate in (
                source_dir.parent / "requirements.txt",
                source_dir.parent.parent / "requirements.txt",
            ):
                if candidate.exists():
                    log(f"  + 补充 requirements.txt（来自 {candidate.parent.name}/）")
                    zf.write(candidate, "requirements.txt")
                    count += 1
                    break

    size_kb = output_zip.stat().st_size / 1024
    log(f"  → {count} 个文件, {size_kb:.0f} KB")
    return output_zip


# --------------------------------------------------------------------------- #
# 2) stubs（uninstall.exe / upgrade.exe）
# --------------------------------------------------------------------------- #
def build_stubs(force: bool, debug: bool):
    """
    调用 tools/build_stubs.py 打包两个 stub。
    """
    uninstall_exe = STUBS_OUT / "uninstall.exe"
    upgrade_exe = STUBS_OUT / "upgrade.exe"

    need_rebuild = force or not (uninstall_exe.exists() and upgrade_exe.exists())
    if not need_rebuild:
        log(f"复用已有 stubs:")
        log(f"  uninstall.exe ({uninstall_exe.stat().st_size / 1024:.0f} KB)")
        log(f"  upgrade.exe   ({upgrade_exe.stat().st_size / 1024:.0f} KB)")
        return uninstall_exe, upgrade_exe

    build_script = ROOT / "tools" / "build_stubs.py"
    if not build_script.exists():
        raise FileNotFoundError(f"找不到 stub 构建脚本: {build_script}")

    log("构建 stubs (uninstall.exe / upgrade.exe)...")
    cmd = [sys.executable, str(build_script)]
    if debug:
        cmd.append("--debug")
    ret = subprocess.call(cmd, cwd=str(ROOT))
    if ret != 0:
        raise RuntimeError(f"stub 构建失败 (exit {ret})")

    if not uninstall_exe.exists() or not upgrade_exe.exists():
        raise RuntimeError("stub 产物不完整")

    log(f"  uninstall.exe ({uninstall_exe.stat().st_size / 1024:.0f} KB)")
    log(f"  upgrade.exe   ({upgrade_exe.stat().st_size / 1024:.0f} KB)")
    return uninstall_exe, upgrade_exe


# --------------------------------------------------------------------------- #
# 3) 安装器 exe
# --------------------------------------------------------------------------- #
def build_installer_exe(uninstall_exe: Path,
                        upgrade_exe: Path,
                        version: str,
                        debug: bool) -> Path:
    """
    PyInstaller 打包 installer/ → dist/MaaAuto_Setup.exe（onefile）。
    内嵌 uninstall.exe + upgrade.exe。
    source.zip 不内嵌（外置）。
    """
    log("打包安装器 (MaaAuto_Setup.exe) [onefile]...")

    # 准备临时 _embedded 目录
    build_embedded = BUILD_DIR / "_embedded"
    if build_embedded.exists():
        shutil.rmtree(build_embedded, ignore_errors=True)
    build_embedded.mkdir(parents=True, exist_ok=True)
    shutil.copy2(uninstall_exe, build_embedded / "uninstall.exe")
    shutil.copy2(upgrade_exe, build_embedded / "upgrade.exe")

    icon = ROOT / "resources" / "icon.ico"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--name", "MaaAuto_Setup",
        "--onefile",
        "--windowed" if not debug else "--console",
        str(ROOT / "installer" / "__main__.py"),
        # 内嵌 stubs
        "--add-data", f"{build_embedded / 'uninstall.exe'}{os.pathsep}_embedded",
        "--add-data", f"{build_embedded / 'upgrade.exe'}{os.pathsep}_embedded",
        # i18n
        "--add-data", f"{ROOT / 'installer' / 'i18n'}{os.pathsep}installer/i18n",
        # hidden imports
        "--hidden-import", "PySide6.QtNetwork",
        "--hidden-import", "win32com",
        "--hidden-import", "win32com.client",
        "--hidden-import", "pythoncom",
        "--hidden-import", "pywintypes",
        # 排除
        "--exclude-module", "PySide6.QtWebEngineCore",
        "--exclude-module", "PySide6.QtWebEngineWidgets",
        "--exclude-module", "PySide6.Qt3DCore",
        "--exclude-module", "PySide6.QtMultimedia",
        "--exclude-module", "PySide6.QtQml",
        "--exclude-module", "PySide6.QtQuick",
        "--exclude-module", "matplotlib",
        "--exclude-module", "numpy",
        "--exclude-module", "tkinter",
    ]

    if icon.exists():
        cmd += ["--icon", str(icon)]

    vf = _write_version_file(version)
    if vf:
        cmd += ["--version-file", str(vf)]

    ret = subprocess.call(cmd, cwd=str(ROOT))
    if ret != 0:
        raise RuntimeError(f"PyInstaller 打包失败 (exit {ret})")

    final_exe = DIST_DIR / "MaaAuto_Setup.exe"
    if not final_exe.exists():
        raise RuntimeError(f"未找到打包产物: {final_exe}")

    size_mb = final_exe.stat().st_size / (1024 * 1024)
    log(f"  → MaaAuto_Setup.exe ({size_mb:.1f} MB)")
    return final_exe


def _write_version_file(version: str):
    try:
        parts = re.findall(r"\d+", version) or ["0", "0", "0", "0"]
        while len(parts) < 4:
            parts.append("0")
        vt = ", ".join(parts[:4])
        content = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({vt}),
    prodvers=({vt}),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(u'080404B0', [
        StringStruct(u'CompanyName', u'MaaAuto'),
        StringStruct(u'FileDescription', u'MaaAuto Installer'),
        StringStruct(u'FileVersion', u'{version}'),
        StringStruct(u'InternalName', u'MaaAuto_Setup'),
        StringStruct(u'OriginalFilename', u'MaaAuto_Setup.exe'),
        StringStruct(u'ProductName', u'MaaAuto'),
        StringStruct(u'ProductVersion', u'{version}')
      ])
    ]),
    VarFileInfo([VarStruct(u'Translation', [2052, 1200])])
  ]
)
"""
        path = ROOT / "_installer_version_info.txt"
        path.write_text(content, encoding="utf-8")
        return path
    except Exception as e:
        log(f"版本信息生成失败（跳过）: {e}")
        return None


# --------------------------------------------------------------------------- #
# 4) 交付 zip
# --------------------------------------------------------------------------- #
def compose_final_zip(installer_exe: Path,
                     source_zip: Path,
                     version: str,
                     app_version: str) -> Path:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    final_zip = DIST_DIR / f"MaaAuto_v{app_version}.zip"
    if final_zip.exists():
        final_zip.unlink()

    github_url = _read_github()

    readme = f"""MaaAuto 安装说明
================

版本：{app_version}
安装器版本：{version}

【重要】请勿单独移动 MaaAuto_Setup.exe！
        它需要与 MaaAuto_Source.zip 保持在同一目录。

使用步骤：
  1. 解压本压缩包到任意目录（保持三个文件在同一文件夹）
  2. 双击 MaaAuto_Setup.exe 启动安装向导
  3. 按提示选择安装目录
  4. 等待安装完成（需联网，约 6-20 分钟）
  5. 从桌面快捷方式启动 MaaAuto

注意事项：
  - 安装时会联网下载依赖，建议使用稳定网络
  - 安装过程中 CPU 占用较高（本地打包主程序），属正常现象
  - 若杀毒软件误报，请添加信任
  - 安装完成后会生成卸载器 (uninstall.exe) 和升级器 (upgrade.exe)

系统要求：
  - Windows 10 / 11 (64 位)
  - 约 1 GB 磁盘空间
  - 网络连接

更多信息：{github_url}
"""
    readme_tmp = DIST_DIR / "README.txt"
    readme_tmp.write_text(readme, encoding="utf-8")

    log(f"组合最终压缩包: {final_zip.name}")
    with zipfile.ZipFile(final_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.write(installer_exe, "MaaAuto_Setup.exe")
        zf.write(source_zip, "MaaAuto_Source.zip")
        zf.write(readme_tmp, "README.txt")

    readme_tmp.unlink(missing_ok=True)

    size_mb = final_zip.stat().st_size / (1024 * 1024)
    log(f"  → {final_zip} ({size_mb:.1f} MB)")
    return final_zip


def _read_github():
    try:
        p = DEFAULT_SOURCE_DIR / "app_info.py"
        if p.exists():
            text = p.read_text(encoding="utf-8")
            m = re.search(r'^APP_GITHUB\s*=\s*["\']([^"\']*)["\']', text, re.M)
            if m:
                return m.group(1)
    except Exception:
        pass
    return "https://github.com/"


# --------------------------------------------------------------------------- #
# 清理
# --------------------------------------------------------------------------- #
def clean_artifacts():
    for p in (DIST_DIR, BUILD_DIR):
        if p.exists():
            log(f"清理 {p}")
            shutil.rmtree(p, ignore_errors=True)
    for f in (SPEC_FILE, ROOT / "_installer_version_info.txt"):
        if f.exists():
            f.unlink(missing_ok=True)


def clean_pycache(root: Path):
    removed = 0
    skip = {".git", "venv", ".venv", "env", "node_modules",
            "build", "dist", "_embedded", "_launcher_build",
            "_work_uninstall", "_work_upgrade"}
    for dirpath, dirnames, _files in os.walk(root, topdown=True):
        dirnames[:] = [d for d in dirnames if d.lower() not in skip]
        if "__pycache__" in dirnames:
            p = Path(dirpath) / "__pycache__"
            shutil.rmtree(p, ignore_errors=True)
            removed += 1
            dirnames.remove("__pycache__")
    if removed:
        log(f"清理 {removed} 个 __pycache__")


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def main():
    parser = argparse.ArgumentParser(
        description="构建 MaaAuto 安装器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR,
                        help=f"MaaAutoProject 源码目录（默认: {DEFAULT_SOURCE_DIR}）")
    parser.add_argument("--debug", action="store_true",
                        help="保留控制台 + stubs 也 debug")
    parser.add_argument("--no-stub-rebuild", action="store_true",
                        help="复用已有 stubs")
    parser.add_argument("--keep-build", action="store_true",
                        help="不清理 dist/ build/ _embedded/")
    args = parser.parse_args()

    source_dir = args.source_dir.resolve()

    print("=" * 64)
    print("MaaAutoInstaller 构建")
    print("=" * 64)
    print(f"项目根目录   : {ROOT}")
    print(f"源码目录     : {source_dir}")
    print(f"Python       : {sys.version.split()[0]} ({sys.executable})")
    print("=" * 64)

    if not source_dir.exists():
        err(f"源码目录不存在: {source_dir}")
        sys.exit(1)

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        err("未安装 PyInstaller。请先: pip install pyinstaller")
        sys.exit(1)

    installer_version = read_installer_version()
    app_version = read_app_version(source_dir)
    log(f"安装器版本  : {installer_version}")
    log(f"应用版本    : {app_version}")

    if not args.keep_build:
        clean_artifacts()
    clean_pycache(ROOT)

    # 1) source.zip
    source_zip = EMBEDDED_DIR / "source.zip"
    build_source_zip(source_dir, source_zip)

    # 2) stubs
    uninstall_exe, upgrade_exe = build_stubs(
        force=not args.no_stub_rebuild,
        debug=args.debug,
    )

    # 3) 安装器 exe
    installer_exe = build_installer_exe(
        uninstall_exe=uninstall_exe,
        upgrade_exe=upgrade_exe,
        version=installer_version,
        debug=args.debug,
    )

    # 4) 交付 zip
    final_zip = compose_final_zip(
        installer_exe=installer_exe,
        source_zip=source_zip,
        version=installer_version,
        app_version=app_version,
    )

    if not args.keep_build:
        clean_pycache(ROOT)

    print("=" * 64)
    print("构建成功 ✅")
    print("=" * 64)
    print(f"最终产物 : {final_zip}")
    print(f"           （解压后得到 MaaAuto_Setup.exe + MaaAuto_Source.zip + README.txt）")
    print()
    print("自测方法 :")
    print("  1. 解压 final_zip 到临时目录（三个文件放一起）")
    print("  2. 双击 MaaAuto_Setup.exe，走完整安装流程")
    print("  3. 检查安装目录里有 MaaAuto.exe / uninstall.exe / upgrade.exe")
    print("  4. 从桌面快捷方式启动 MaaAuto")
    print("  5. 双击 uninstall.exe，验证卸载")
    print("=" * 64)


if __name__ == "__main__":
    main()