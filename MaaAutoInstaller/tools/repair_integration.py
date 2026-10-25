"""修复「升级后桌面图标 / 开始菜单 / 『设置→应用』条目消失」。

现象
----
* 「设置 → 应用」里的 MaaAuto 显示「系统找不到应用」（或整条没了）；
* 开始菜单里没有 MaaAuto 文件夹；
* 桌面图标不见了。

但安装目录（如 ``D:\\MaaAuto``）里的 ``MaaAuto.exe`` 还在、还能直接运行。

原因：Inno 的卸载注册表项、开始菜单组、桌面快捷方式都是**按 AppId 全局共享**的。
本地发布校验脚本用同一个 AppId 装到 ``%LOCALAPPDATA%\\Programs\\MaaAuto`` 再卸载，
就把用户那份（哪怕装在别的目录）的登记信息一起删了。程序文件不受影响。

本工具只重建登记信息，不动任何程序文件 / 用户配置：

    python MaaAutoInstaller/tools/repair_integration.py
    python MaaAutoInstaller/tools/repair_integration.py --dir D:\\MaaAuto
"""

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # MaaAutoInstaller/tools
INSTALLER_ROOT = HERE.parent.parent             # MaaAuto-Installer/
sys.path.insert(0, str(HERE.parent))   # MaaAutoInstaller/，包名叫 installer

from installer.core import shell_integration as shell  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def guess_candidates() -> list:
    """注册表里登记的目录 + 几个常见安装位置。"""
    out = []
    loc = shell.installed_location()
    if loc:
        out.append(loc)
    out.append(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "MaaAuto")
    out.append(Path(r"D:\MaaAuto"))
    out.append(Path(r"C:\Program Files\MaaAuto"))
    seen, uniq = set(), []
    for p in out:
        key = str(p).lower()
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq


def version_of(install_dir: Path) -> str:
    mf = install_dir / ".maaauto.json"
    if mf.exists():
        try:
            return json.loads(mf.read_text(encoding="utf-8")).get("version", "")
        except Exception:
            return ""
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="重建 MaaAuto 的图标与「设置→应用」登记")
    ap.add_argument("--dir", default="", help="安装目录；缺省自动探测")
    ap.add_argument("--version", default="", help="写进『应用』列表的版本号；缺省读 manifest")
    args = ap.parse_args()

    target = Path(args.dir) if args.dir else None
    if target is None:
        for cand in guess_candidates():
            if (cand / shell.MAIN_EXE).exists():
                target = cand
                break
    if target is None:
        print("找不到带 MaaAuto.exe 的安装目录，请用 --dir 指定。")
        return 2

    if not (target / shell.MAIN_EXE).exists():
        print(f"{target} 里没有 {shell.MAIN_EXE}，请确认安装目录。")
        return 2
    if not (target / shell.UNINSTALLER_EXE).exists():
        print(f"[!] {target} 里没有 {shell.UNINSTALLER_EXE}：安装不完整，"
              f"建议重新运行完整安装包。仍会重建图标，但「设置→应用」里的卸载会不可用。")

    version = args.version or version_of(target)
    print("=" * 72)
    print(f"安装目录 : {target}")
    print(f"版本     : {version or '（未知）'}")
    print("=" * 72)

    result = shell.repair_integration(target, version)
    labels = {
        "start_menu": "开始菜单快捷方式",
        "start_menu_uninstall": "开始菜单「卸载」快捷方式",
        "desktop": "桌面快捷方式",
        "registry": "「设置 → 应用」登记",
    }
    fails = 0
    for key, label in labels.items():
        ok = bool(result.get(key))
        print(("  OK   " if ok else "  FAIL ") + label)
        fails += 0 if ok else 1

    loc = shell.installed_location()
    print(f"\n注册表 InstallLocation = {loc}")
    print("完成。" if not fails else "部分项目失败（可能缺少 pywin32）；可手动重装一次安装包。")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
