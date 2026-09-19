"""
MaaAutoInstaller 一键构建脚本（单 exe 版）。

流程：
  1. 打包主程序源码 → _embedded/source.zip（临时）
  2. 打包 stubs → tools/_out/uninstall.exe + upgrade.exe
  3. PyInstaller 打包安装器 → dist/MaaAuto_Online_vX.X.X-Windows-x64.exe
     （onefile，内嵌 source.zip + uninstall.exe + upgrade.exe）
  4. 默认清理所有中间产物，只留最终 exe

用法：
    python build_installer.py
    python build_installer.py --source-dir ../MaaAuto-Tool-works/MaaAutoProject
    python build_installer.py --debug              # 保留控制台 + 不清理
    python build_installer.py --keep-build         # 不清理中间产物
    python build_installer.py --no-stub-rebuild    # 复用已有 stubs（若存在）

产物：
    dist/MaaAuto_Online_v{app_version}-Windows-x64.exe
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


def _find_default_source_dir() -> Path:
    """
    探测主程序源码目录。按优先级：
      1. <ROOT>/../../MaaAuto-Tool-works/MaaAutoProject   ← 主约定（同级工作区）
      2. <ROOT>/../MaaAuto-Tool-works/MaaAutoProject
      3. <ROOT>/../MaaAutoProject
      4. <ROOT>/MaaAutoProject
    找到含 app_info.py 的目录即采用。
    """
    candidates = [
        ROOT.parent.parent / "MaaAuto-Tool-works" / "MaaAutoProject",
        ROOT.parent / "MaaAuto-Tool-works" / "MaaAutoProject",
        ROOT.parent / "MaaAutoProject",
        ROOT / "MaaAutoProject",
    ]
    for c in candidates:
        try:
            if c.exists() and (c / "app_info.py").exists():
                return c.resolve()
        except Exception:
            continue
    return candidates[0]


DEFAULT_SOURCE_DIR = _find_default_source_dir()


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
    """
    打包 source_dir 为 zip，排除 __pycache__ / .git / build / dist / config / logs 等。
    - zip 内部顶层就是源码根（不含 source_dir 名字）
    - 若 source_dir 里没有 requirements.txt，自动从上一级补
    """
    if not source_dir.exists():
        raise FileNotFoundError(f"源码目录不存在: {source_dir}")

    log(f"打包源码: {source_dir} → {output_zip}")
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    if output_zip.exists():
        output_zip.unlink()

    count = 0

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED,
                         compresslevel=9) as zf:
        for root, dirs, files in os.walk(source_dir):
            root_path = Path(root)
            dirs[:] = [
                d for d in dirs
                if not should_skip(d, root_path / d)
            ]
            for fname in files:
                fpath = root_path / fname
                if should_skip(fname, fpath):
                    continue
                arcname = fpath.relative_to(source_dir)
                zf.write(fpath, arcname.as_posix())
                count += 1

        # 补齐 requirements.txt
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
# stub 源码清单（相对安装器根）
_STUB_SOURCE_FILES = [
    ("tools/uninstall_stub.py",              "uninstall_stub.py"),
    ("tools/upgrade_stub.py",                "upgrade_stub.py"),
    ("VERSION",                              "VERSION"),
    ("resources/icon.ico",                   "resources/icon.ico"),
    ("installer/__init__.py",                "installer/__init__.py"),
    ("installer/core/upgrade_engine.py",     "installer/core/upgrade_engine.py"),
    ("installer/core/mirror.py",             "installer/core/mirror.py"),
    ("installer/core/downloader.py",         "installer/core/downloader.py"),
    ("installer/core/python_env.py",         "installer/core/python_env.py"),
    ("installer/core/pip_installer.py",      "installer/core/pip_installer.py"),
    ("installer/core/pyinstaller_builder.py","installer/core/pyinstaller_builder.py"),
    ("installer/core/source_deployer.py",    "installer/core/source_deployer.py"),
    ("installer/core/manifest.py",           "installer/core/manifest.py"),
    ("installer/core/cleanup.py",            "installer/core/cleanup.py"),
]


def build_stubs_source_zip(output_zip: Path) -> Path:
    """
    打包 stub 源码子集，供用户端本地打包 stub 用。
    - 不打包 shortcut / uninstall / upgrade 等涉及 pywin32 的模块
    - installer/core/__init__.py 写一个最小化版本（避免拖入无关依赖）
    """
    log(f"打包 stub 源码: → {output_zip}")
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    if output_zip.exists():
        output_zip.unlink()

    count = 0
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED,
                         compresslevel=9) as zf:
        for rel, arcname in _STUB_SOURCE_FILES:
            src = ROOT / rel
            if not src.exists():
                raise FileNotFoundError(f"缺少 stub 源码文件: {src}")
            zf.write(src, arcname)
            count += 1

        # ★ 最小化 installer/core/__init__.py
        zf.writestr(
            "installer/core/__init__.py",
            '"""stub 场景下的最小 core 包（避免拖入 pywin32）。"""\n',
        )
        count += 1

    size_kb = output_zip.stat().st_size / 1024
    log(f"  → {count} 个文件, {size_kb:.0f} KB")
    return output_zip


# --------------------------------------------------------------------------- #
# 3) 安装器 exe（onefile，内嵌 3 个）
# --------------------------------------------------------------------------- #
def build_installer_exe(source_zip: Path,
                        stubs_source_zip: Path,
                        version: str,
                        debug: bool) -> Path:
    """
    PyInstaller 打包 installer/ → dist/MaaAuto_Setup.exe（onefile）。
    内嵌 source.zip + stubs_source.zip。
    """
    log("打包安装器 (MaaAuto_Setup.exe) [onefile]...")

    build_embedded = BUILD_DIR / "_embedded"
    if build_embedded.exists():
        shutil.rmtree(build_embedded, ignore_errors=True)
    build_embedded.mkdir(parents=True, exist_ok=True)

    shutil.copy2(source_zip, build_embedded / "source.zip")
    shutil.copy2(stubs_source_zip, build_embedded / "stubs_source.zip")

    icon = ROOT / "resources" / "icon.ico"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--name", "MaaAuto_Setup",
        "--onefile",
        "--uac-admin",                      # ★ 新增：请求管理员权限，才能写 HKLM
        "--windowed" if not debug else "--console",
        str(ROOT / "installer" / "__main__.py"),
        # 内嵌 2 个资源
        "--add-data", f"{build_embedded / 'source.zip'}{os.pathsep}_embedded",
        "--add-data", f"{build_embedded / 'stubs_source.zip'}{os.pathsep}_embedded",
        # i18n
        "--add-data", f"{ROOT / 'installer' / 'i18n'}{os.pathsep}installer/i18n",
        "--add-data", f"{ROOT / 'resources'}{os.pathsep}resources",
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
# 4) 清理
# --------------------------------------------------------------------------- #
def clean_pycache(root: Path):
    """清理 root 下所有 __pycache__。"""
    removed = 0
    skip = {".git", "venv", ".venv", "env", "node_modules",
            "_embedded", "_work_uninstall", "_work_upgrade"}
    for dirpath, dirnames, _files in os.walk(root, topdown=True):
        dirnames[:] = [d for d in dirnames if d.lower() not in skip]
        if "__pycache__" in dirnames:
            p = Path(dirpath) / "__pycache__"
            shutil.rmtree(p, ignore_errors=True)
            removed += 1
            dirnames.remove("__pycache__")
    if removed:
        log(f"清理 {removed} 个 __pycache__")


def clean_all(source_dir: Path,
              keep_stub_output: bool = False,
              keep_final_exe: str = ""):
    """
    清理所有中间产物。默认只保留 dist/<keep_final_exe>。
    """
    log("清理中间产物...")

    # ---- 1. 安装器项目内 ----
    for p in (BUILD_DIR, EMBEDDED_DIR):
        if p.exists():
            log(f"  删 {p.relative_to(ROOT)}/")
            shutil.rmtree(p, ignore_errors=True)

    for f in (SPEC_FILE, ROOT / "_installer_version_info.txt"):
        if f.exists():
            log(f"  删 {f.name}")
            f.unlink(missing_ok=True)

    # dist 里除最终 exe 之外
    if DIST_DIR.exists():
        for item in list(DIST_DIR.iterdir()):
            if keep_final_exe and item.name == keep_final_exe:
                continue
            try:
                if item.is_dir():
                    log(f"  删 dist/{item.name}/")
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    log(f"  删 dist/{item.name}")
                    item.unlink(missing_ok=True)
            except Exception as e:
                log(f"  删 dist/{item.name} 失败: {e}")

    # ---- 2. tools/_out + tools/_work_* ----
    

    # ---- 3. 主程序源码里的 build/ dist/ ----
    if source_dir.exists():
        for p in (source_dir / "build", source_dir / "dist"):
            if p.exists():
                log(f"  删 {p}/")
                shutil.rmtree(p, ignore_errors=True)

    # ---- 4. __pycache__ ----
    clean_pycache(ROOT)
    if source_dir.exists():
        clean_pycache(source_dir)


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def main():
    parser = argparse.ArgumentParser(
        description="构建 MaaAuto 安装器（单 exe）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR,
                        help=f"MaaAutoProject 源码目录（默认: {DEFAULT_SOURCE_DIR}）")
    parser.add_argument("--debug", action="store_true",
                        help="保留控制台（同时不清理中间产物）")
    parser.add_argument("--no-stub-rebuild", action="store_true",
                        help="复用已有 stubs（若存在）")
    parser.add_argument("--keep-build", action="store_true",
                        help="不清理中间产物")
    args = parser.parse_args()

    source_dir = args.source_dir.resolve()
    keep_build = args.keep_build or args.debug   # Q5: --debug 自动等于 --keep-build

    print("=" * 64)
    print("MaaAutoInstaller 构建（单 exe）")
    print("=" * 64)
    print(f"项目根目录   : {ROOT}")
    print(f"源码目录     : {source_dir}")
    print(f"Python       : {sys.version.split()[0]} ({sys.executable})")
    print(f"清理中间产物 : {'否' if keep_build else '是'}")
    print("=" * 64)

    if not source_dir.exists():
        err(f"源码目录不存在: {source_dir}")
        err(f"请用 --source-dir 指定正确的路径")
        sys.exit(1)

    if not (source_dir / "app_info.py").exists():
        err(f"源码目录里没有 app_info.py: {source_dir}")
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

    # 每次构建前先清一遍旧的临时中间产物
    # （但不动 dist，因为 dist 里可能有上一次的最终 exe，构建最后会一起处理）
    if not keep_build:
        for p in (BUILD_DIR, EMBEDDED_DIR):
            if p.exists():
                shutil.rmtree(p, ignore_errors=True)
        for f in (SPEC_FILE, ROOT / "_installer_version_info.txt"):
            if f.exists():
                f.unlink(missing_ok=True)

    # 1) source.zip（主程序源码）
    source_zip = EMBEDDED_DIR / "source.zip"
    build_source_zip(source_dir, source_zip)

    # 2) stubs_source.zip（stub 源码，供用户端本地打包）
    stubs_source_zip = EMBEDDED_DIR / "stubs_source.zip"
    build_stubs_source_zip(stubs_source_zip)

    # 3) 安装器 exe
    built_exe = build_installer_exe(
        source_zip=source_zip,
        stubs_source_zip=stubs_source_zip,
        version=installer_version,
        debug=args.debug,
    )

    # 4) 改名为最终产物
    final_name = f"MaaAuto_Online_v{app_version}-Windows-x64.exe"
    final_exe = DIST_DIR / final_name
    if final_exe.exists():
        final_exe.unlink()
    shutil.move(str(built_exe), str(final_exe))
    size_mb = final_exe.stat().st_size / (1024 * 1024)
    log(f"最终产物: dist/{final_name} ({size_mb:.1f} MB)")

    # 5) 清理
    if not keep_build:
        clean_all(source_dir, keep_final_exe=final_name)
    else:
        log("（跳过清理：--keep-build 或 --debug）")

    print("=" * 64)
    print("构建成功 ✅")
    print("=" * 64)
    print(f"最终产物 : {final_exe}")
    print()
    print("这是一个独立 exe：用户双击即启动安装向导，")
    print("无需任何同级文件（source.zip + stubs 已内嵌）。")
    print()
    print("自测方法 :")
    print("  1. 拷贝该 exe 到任意临时目录（单独一个文件）")
    print("  2. 双击，走完整安装流程")
    print("  3. 检查安装目录里有 MaaAuto.exe / uninstall.exe / upgrade.exe")
    print("  4. 从桌面快捷方式启动 MaaAuto")
    print("  5. 双击 uninstall.exe，验证卸载")
    print("=" * 64)


if __name__ == "__main__":
    main()