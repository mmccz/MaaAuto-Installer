"""
MaaAuto 升级器 stub（独立 exe）。
PyInstaller 打包后 → tools/_out/upgrade.exe
安装时被释放到 <install>/upgrade.exe。

命令行参数：
  --from-main    必须（否则弹提示退出）
  --silent       静默升级：有窗口但不可交互（无取消、不可关）
  --check-only   交互模式：弹 UI 展示检查结果，可一键升级
                 --silent 时：纯静默，仅退出码
  --restart      升级成功后自动重启主程序
  --downgrade    允许降级
  --channel      stable / beta

退出码：
  0  成功 / 有新版本
  1  已是最新
  2  错误
"""

import os
import sys
import json
import time
import glob
import shutil
import tempfile
import argparse
import datetime
import subprocess
import traceback
from pathlib import Path


# --------------------------------------------------------------------------- #
# sys.path
# --------------------------------------------------------------------------- #
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


APP_TITLE = "MaaAuto 升级程序"
APP_TITLE_SILENT = "MaaAuto 后台升级中"
MAIN_EXE = "MaaAuto.exe"


# --------------------------------------------------------------------------- #
# 主题
# --------------------------------------------------------------------------- #
LIGHT_PALETTE = {
    "bg": "#F7F8FA", "surface": "#FFFFFF",
    "border": "#E5E7EB", "border_in": "#D1D5DB", "border_hover": "#9CA3AF",
    "hover": "#F3F4F6", "pressed": "#E5E7EB",
    "text": "#111827", "text_sub": "#6B7280", "text_hint": "#9CA3AF",
    "text_field": "#374151",
    "primary": "#2563EB", "primary_h": "#1D4ED8", "primary_p": "#1E40AF",
    "primary_d": "#BFDBFE",
    "bar_bg": "#E5E7EB", "bar_1": "#60A5FA", "bar_2": "#2563EB",
    "log_bg": "#0F172A", "log_fg": "#CBD5E1", "log_border": "#1E293B",
    "scroll": "#CBD5E1", "scroll_h": "#94A3B8",
}

DARK_PALETTE = {
    "bg": "#1A1D21", "surface": "#23262B",
    "border": "#343A40", "border_in": "#3F454D", "border_hover": "#6B7280",
    "hover": "#2E3339", "pressed": "#3A4048",
    "text": "#F3F4F6", "text_sub": "#9CA3AF", "text_hint": "#6B7280",
    "text_field": "#D1D5DB",
    "primary": "#3B82F6", "primary_h": "#2563EB", "primary_p": "#1D4ED8",
    "primary_d": "#1E3A8A",
    "bar_bg": "#2E3339", "bar_1": "#60A5FA", "bar_2": "#3B82F6",
    "log_bg": "#0F172A", "log_fg": "#CBD5E1", "log_border": "#1E293B",
    "scroll": "#4B5563", "scroll_h": "#6B7280",
}

_QSS_TEMPLATE = """
QDialog { background: @bg@; }
QWidget {
    font-family: "Segoe UI", "Microsoft YaHei UI", "PingFang SC", sans-serif;
    font-size: 13px;
}
QLabel { color: @text@; background: transparent; }
QLabel#Head  { font-size: 18px; font-weight: 600; color: @text@; }
QLabel#Sub   { font-size: 13px; color: @text_sub@; }
QLabel#Ver   { font-size: 12px; color: @text_hint@; }
QLabel#Stage { font-size: 13px; font-weight: 500; color: @text_field@; }
QLabel#Pct   { font-size: 13px; font-weight: 600; color: @primary@; }

QProgressBar#Bar {
    background: @bar_bg@; border: none; border-radius: 5px; height: 10px;
}
QProgressBar#Bar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 @bar_1@, stop:1 @bar_2@);
    border-radius: 5px;
}

QTextEdit#Log {
    background: @log_bg@; color: @log_fg@;
    border: 1px solid @log_border@; border-radius: 8px;
    font-family: "Cascadia Mono", "Consolas", "Courier New", monospace;
    font-size: 12px; padding: 10px;
    selection-background-color: @primary_h@; selection-color: #FFFFFF;
}

QPushButton {
    background: @surface@; color: @text_field@;
    border: 1px solid @border_in@; border-radius: 6px;
    padding: 8px 18px; font-size: 13px; min-width: 72px;
}
QPushButton:hover   { background: @hover@; border-color: @border_hover@; }
QPushButton:pressed { background: @pressed@; }
QPushButton:disabled{ color: @text_hint@; background: @bg@; border-color: @border@; }

QPushButton#Primary {
    background: @primary@; color: #FFFFFF; border: none;
    padding: 8px 22px; font-weight: 500; min-width: 88px;
}
QPushButton#Primary:hover   { background: @primary_h@; }
QPushButton#Primary:pressed { background: @primary_p@; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical {
    background: @scroll@; border-radius: 5px; min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: @scroll_h@; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }

QScrollBar:horizontal { background: transparent; height: 10px; }
QScrollBar::handle:horizontal {
    background: @scroll@; border-radius: 5px; min-width: 30px;
}
QScrollBar::handle:horizontal:hover { background: @scroll_h@; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
"""


def build_qss(palette: dict) -> str:
    qss = _QSS_TEMPLATE
    for k, v in palette.items():
        qss = qss.replace(f"@{k}@", v)
    return qss


def detect_dark_mode() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        try:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return int(value) == 0
        finally:
            winreg.CloseKey(key)
    except Exception:
        return False


def get_icon_path() -> str:
    try:
        base = getattr(sys, "_MEIPASS", None)
        if base:
            p = Path(base) / "resources" / "icon.ico"
            if p.exists():
                return str(p)
    except Exception:
        pass
    for base in (_HERE, _ROOT):
        p = Path(base) / "resources" / "icon.ico"
        if p.exists():
            return str(p)
    return ""


# --------------------------------------------------------------------------- #
# 阶段进度布局
# --------------------------------------------------------------------------- #
STAGE_LAYOUT = [
    ("locate",             1),
    ("check",              2),
    ("download_source",    8),
    ("stop_main",          2),
    ("prepare",            2),
    ("backup",             5),
    ("download_python",    8),
    ("unpack_source",      3),
    ("install_pip",        3),
    ("install_deps",      25),
    ("install_pyinstaller",5),
    ("build_main",        30),
    ("deploy",             3),
    ("manifest",           1),
    ("cleanup",            1),
    ("done",               1),
]

STAGE_BOUNDS = {}
_run = 0
for _k, _w in STAGE_LAYOUT:
    STAGE_BOUNDS[_k] = (_run, _w)
    _run += _w


STAGE_TEXT = {
    "locate":              "定位安装目录...",
    "check":               "检查更新...",
    "download_source":     "下载源码包...",
    "stop_main":           "停止主程序...",
    "prepare":             "准备升级...",
    "backup":              "备份现有文件...",
    "download_python":     "下载独立 Python 3.11.9...",
    "unpack_source":       "解压源码...",
    "install_pip":         "安装 pip...",
    "install_deps":        "安装依赖（约 200 MB）...",
    "install_pyinstaller": "安装 PyInstaller...",
    "build_main":          "本地打包主程序...",
    "deploy":              "覆盖安装目录...",
    "manifest":            "写入元数据...",
    "cleanup":             "清理临时文件...",
    "done":                "完成",
    "restart":             "启动主程序...",
}


# --------------------------------------------------------------------------- #
# Win32 MessageBox
# --------------------------------------------------------------------------- #
MB_OK = 0x0
MB_ICONINFORMATION = 0x40
MB_ICONERROR = 0x10


def win_msg(title: str, text: str,
            flags: int = MB_OK | MB_ICONINFORMATION) -> int:
    try:
        import ctypes
        return ctypes.windll.user32.MessageBoxW(0, str(text), str(title), flags)
    except Exception:
        print(f"{title}: {text}", file=sys.stderr)
        return 0


# --------------------------------------------------------------------------- #
# 版本
# --------------------------------------------------------------------------- #
def get_installer_version() -> str:
    try:
        base = getattr(sys, "_MEIPASS", None) or str(_HERE)
        vf = Path(base) / "VERSION"
        if vf.exists():
            return vf.read_text(encoding="utf-8").strip() or "1.0.0"
    except Exception:
        pass
    try:
        vf = _ROOT / "VERSION"
        if vf.exists():
            return vf.read_text(encoding="utf-8").strip() or "1.0.0"
    except Exception:
        pass
    return "1.0.0"


# --------------------------------------------------------------------------- #
# 日志
# --------------------------------------------------------------------------- #
class Logger:
    def __init__(self, install_dir: Path = None):
        self.install_dir = install_dir
        self.log_path = None
        self._fh = None

    def open(self) -> Path:
        ts = time.strftime("%Y%m%d_%H%M%S")
        self.log_path = Path(tempfile.gettempdir()) / f"MaaAuto_upgrade_{ts}.log"
        try:
            self._fh = open(self.log_path, "w", encoding="utf-8")
        except Exception:
            self._fh = None
        self.info("=" * 48)
        self.info("MaaAuto Upgrade started")
        self.info(f"time: {datetime.datetime.now().isoformat(timespec='seconds')}")
        self.info(f"argv: {sys.argv}")
        self.info(f"frozen: {getattr(sys, 'frozen', False)}")
        self.info(f"version: {get_installer_version()}")
        self.info("=" * 48)
        return self.log_path

    def close(self):
        if self._fh:
            try:
                self._fh.flush()
                self._fh.close()
            except Exception:
                pass

    def _write(self, level: str, msg: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] [{level}] {msg}"
        try:
            print(line, flush=True)
        except Exception:
            pass
        if self._fh:
            try:
                self._fh.write(line + "\n")
                self._fh.flush()
            except Exception:
                pass

    def info(self, msg: str):
        self._write("INFO", msg)

    def warn(self, msg: str):
        self._write("WARN", msg)

    def error(self, msg: str):
        self._write("ERROR", msg)

    def copy_to_install(self):
        if not self.install_dir or not self.log_path:
            return
        try:
            dst_dir = Path(self.install_dir) / "logs" / "upgrade"
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst = dst_dir / self.log_path.name
            shutil.copy2(self.log_path, dst)
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# 备份清理工具
# --------------------------------------------------------------------------- #
def cleanup_all_backups(log=None):
    """删除 %TEMP% 下所有 MaaAuto_backup_*.zip。"""
    temp = Path(tempfile.gettempdir())
    count = 0
    for p in glob.glob(str(temp / "MaaAuto_backup_*.zip")):
        try:
            Path(p).unlink()
            count += 1
        except Exception:
            pass
    if count and log:
        try:
            log.info(f"清理遗留备份: {count} 个")
        except Exception:
            pass
    return count


# --------------------------------------------------------------------------- #
# 参数解析
# --------------------------------------------------------------------------- #
def parse_args(argv):
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--from-main", action="store_true")
    p.add_argument("--silent", action="store_true")
    p.add_argument("--check-only", action="store_true")
    p.add_argument("--restart", action="store_true")
    p.add_argument("--downgrade", action="store_true")
    p.add_argument("--channel", default="stable", choices=["stable", "beta"])
    p.add_argument("--debug", action="store_true")
    args, _unknown = p.parse_known_args(argv)
    return args


# --------------------------------------------------------------------------- #
# 定位安装目录
# --------------------------------------------------------------------------- #
def get_install_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# 重启主程序
# --------------------------------------------------------------------------- #
def restart_main(install_dir: Path, log: Logger):
    install_dir = Path(install_dir)
    exe = install_dir / MAIN_EXE
    if not exe.exists():
        log.warn(f"未找到主程序: {exe}")
        return False

    extra_args = []
    args_file = install_dir / "config" / "last_launch_args.json"
    if args_file.exists():
        try:
            data = json.loads(args_file.read_text(encoding="utf-8"))
            extra_args = list(data.get("args", []))
            extra_args = [a for a in extra_args if a not in ("--upgrading",)]
        except Exception as e:
            log.warn(f"读 last_launch_args.json 失败: {e}")

    try:
        subprocess.Popen(
            [str(exe)] + extra_args,
            cwd=str(install_dir),
            creationflags=0x00000008 | 0x00000200,
            close_fds=True,
        )
        log.info(f"主程序已启动: {exe} {extra_args}")
        return True
    except Exception as e:
        log.error(f"启动主程序失败: {e}")
        return False


# --------------------------------------------------------------------------- #
# 升级流程（UI 无关）
# --------------------------------------------------------------------------- #
class UpgradeFlow:
    def __init__(self, args, log: Logger,
                 on_stage=None, on_progress=None, on_message=None,
                 cancel_check=None,
                 skip_check: bool = False,
                 pre_check_info=None):
        self.args = args
        self.log = log
        self.on_stage = on_stage
        self.on_progress = on_progress
        self.on_message = on_message
        self.cancel_check = cancel_check
        self.install_dir = get_install_dir()
        self.installer_version = get_installer_version()
        self.manifest = None
        self.skip_check = skip_check
        self.pre_check_info = pre_check_info

    # ---- 内部回调 ----
    def _stage(self, key):
        if self.on_stage:
            try:
                self.on_stage(key)
            except Exception:
                pass

    def _progress(self, cur, total):
        if self.on_progress:
            try:
                self.on_progress(cur, total)
            except Exception:
                pass

    def _msg(self, text, level="info"):
        if self.on_message:
            try:
                self.on_message(text, level)
            except Exception:
                pass

    def _engine_log(self, msg):
        self.log.info(msg)
        if self.on_message:
            try:
                self.on_message(str(msg), "info")
            except Exception:
                pass

    def _cancelled(self):
        if self.cancel_check:
            try:
                return bool(self.cancel_check())
            except Exception:
                return False
        return False

    # -------------------------------------------------------------- #
    def _do_check(self, check_update, read_manifest,
                  check_installer_version, DEFAULT_MIN_INSTALLER_VERSION):
        """执行检查阶段。返回 (info, error_code)。"""
        self._stage("locate")
        self.log.info(f"安装目录: {self.install_dir}")
        self.manifest = read_manifest(self.install_dir)
        if self.manifest is None:
            self.log.error(f"找不到 .maaauto.json: {self.install_dir}")
            self._msg("未找到安装信息 (.maaauto.json)。\n"
                      "请通过完整安装包重新安装 MaaAuto。", "error")
            return None, 2

        current = self.manifest.version
        self.log.info(f"当前版本: {current}")

        min_ver = (self.manifest.extra or {}).get(
            "min_installer_version", DEFAULT_MIN_INSTALLER_VERSION)
        if not check_installer_version(self.manifest, min_ver):
            msg = (f"当前升级器版本过低（需要 ≥ {min_ver}）。\n\n"
                   f"请到 GitHub Releases 下载最新的完整安装包。")
            self.log.error(msg)
            self._msg(msg, "error")
            return None, 2

        self._stage("check")
        allow_downgrade = bool(self.args.downgrade)
        info = check_update(self.manifest, log=self._engine_log,
                            allow_downgrade=allow_downgrade)
        if info.error:
            self.log.error(f"检查更新失败: {info.error}")
            self._msg(f"检查更新失败：\n{info.error}", "error")
            return None, 2

        if not info.has_update:
            self.log.info(f"已是最新版本 ({info.current})")
            self._msg(f"已是最新版本 v{info.current}", "info")
            return info, 1

        self.log.info(f"发现新版本: {info.current} → {info.latest}")
        self._msg(f"发现新版本：v{info.current} → v{info.latest}", "info")
        return info, 0

    # -------------------------------------------------------------- #
    def run_check_only(self) -> int:
        try:
            from installer.core.upgrade_engine import (
                read_manifest, check_update, check_installer_version,
                DEFAULT_MIN_INSTALLER_VERSION,
            )
        except Exception as e:
            self.log.error(f"import engine 失败: {e}")
            self._msg(f"升级器内部错误：{e}", "error")
            return 2

        _info, code = self._do_check(
            check_update, read_manifest,
            check_installer_version, DEFAULT_MIN_INSTALLER_VERSION
        )
        return code

    # -------------------------------------------------------------- #
    def run_full(self) -> int:
        try:
            from installer.core.upgrade_engine import (
                read_manifest, check_update, download_source, sha256_of_file,
                perform_upgrade, check_installer_version,
                request_main_exit,
                write_failure_flag,
                DEFAULT_MIN_INSTALLER_VERSION,
            )
        except Exception as e:
            self.log.error(f"import engine 失败: {e}")
            self._msg(f"升级器内部错误：无法加载升级引擎\n{e}", "error")
            return 2

        # ---- 保险：清理上一次升级可能遗留的备份 ----
        try:
            cleanup_all_backups(log=self.log)
        except Exception:
            pass

        # ---- 检查阶段（或跳过）----
        if self.skip_check and self.pre_check_info is not None:
            info = self.pre_check_info
            self._stage("locate")
            self.manifest = read_manifest(self.install_dir)
            if self.manifest is None:
                self.log.error(f"找不到 .maaauto.json: {self.install_dir}")
                self._msg("未找到安装信息 (.maaauto.json)。", "error")
                return 2
            self.log.info(f"（跳过检查）当前版本: {self.manifest.version}")
            self._stage("check")
            self._msg(f"目标版本：v{info.latest}", "info")
        else:
            info, code = self._do_check(
                check_update, read_manifest,
                check_installer_version, DEFAULT_MIN_INSTALLER_VERSION
            )
            if code == 2:
                return 2
            if code == 1 or not info.has_update:
                return 1 if self.args.check_only else 0

        if self.args.check_only:
            self.log.info("--check-only 模式，不执行升级")
            return 0

        if self._cancelled():
            self.log.info("用户取消")
            return 0

        # ---- 下载 source.zip ----
        self._stage("download_source")
        work_dir = Path(tempfile.gettempdir()) / f"MaaAuto_upgrade_dl_{int(time.time())}"
        work_dir.mkdir(parents=True, exist_ok=True)
        source_zip = work_dir / "MaaAuto_Source.zip"

        try:
            self.log.info(f"下载: {info.source_url}")
            download_source(
                info.source_url, source_zip,
                log=self._engine_log,
                progress=self._progress,
                expected_sha256=info.source_sha256,
            )
        except Exception as e:
            self.log.error(f"下载失败: {e}")
            self._msg(f"下载源码包失败：\n{e}", "error")
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                pass
            return 2

        actual_sha = info.source_sha256 or sha256_of_file(source_zip)
        self.log.info(f"source.zip sha256: {actual_sha}")

        if self._cancelled():
            self.log.info("用户取消")
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                pass
            return 0

        # ---- 停止主程序 ----
        self._stage("stop_main")
        if not request_main_exit(self.install_dir, log=self._engine_log):
            self.log.error("无法停止主程序")
            self._msg("无法停止 MaaAuto 主程序，升级中止。", "error")
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                pass
            return 2

        # ---- 执行升级 ----
        result = perform_upgrade(
            install_dir=self.install_dir,
            source_zip=source_zip,
            manifest=self.manifest,
            installer_version=self.installer_version,
            source_zip_sha256=actual_sha,
            log=self._engine_log,
            progress=self._progress,
            on_stage=self._stage,
            cancel_check=self._cancelled,
        )

        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass

        # ---- 结果 ----
        if result.success:
            self.log.info(f"升级成功: {result.from_version} → {result.to_version}")
            self._msg(f"升级成功！\n\n{result.from_version} → {result.to_version}",
                      "success")
            try:
                self.log.copy_to_install()
            except Exception:
                pass

            # ★ 保险：升级成功后再清一次备份（engine finally 应已清，双保险）
            try:
                cleanup_all_backups(log=self.log)
            except Exception:
                pass

            self._stage("restart")
            time.sleep(1.0)
            restart_main(self.install_dir, self.log)
            return 0
        else:
            reason = result.error or "未知错误"
            self.log.error(f"升级失败: {reason}")
            if result.rolled_back:
                self.log.info("已从备份回滚到原版本")
                reason += "（已回滚到原版本）"
            else:
                self.log.warn("回滚未成功")
            try:
                write_failure_flag(
                    install_dir=self.install_dir,
                    from_version=result.from_version,
                    to_version=result.to_version,
                    reason=reason,
                    log_path=str(self.log.log_path or ""),
                )
            except Exception:
                pass
            self._msg(f"升级失败：\n{reason}\n\n日志：{self.log.log_path}",
                      "error")
            return 2


# --------------------------------------------------------------------------- #
# 纯静默：无 UI
# --------------------------------------------------------------------------- #
def run_headless(args, log: Logger) -> int:
    flow = UpgradeFlow(args, log)
    if args.check_only:
        return flow.run_check_only()
    return flow.run_full()


# --------------------------------------------------------------------------- #
# 完整 UI
# --------------------------------------------------------------------------- #
def run_ui(args, log: Logger, mode: str = "upgrade") -> int:
    """
    :param mode: "upgrade" = 交互升级（有取消按钮）
                 "silent"  = 静默升级（无取消按钮、不可关）
                 "check"   = 先检查后询问
    """
    try:
        from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout,
                                       QHBoxLayout, QLabel, QProgressBar,
                                       QTextEdit, QPushButton, QMessageBox)
        from PySide6.QtCore import Qt, QTimer, QThread, Signal
        from PySide6.QtGui import QTextCursor, QIcon
    except ImportError as e:
        log.error(f"PySide6 未安装: {e}")
        win_msg(APP_TITLE, f"无法加载 UI 组件。\n\n{e}",
                MB_OK | MB_ICONERROR)
        return 2

    dark = detect_dark_mode()
    log.info(f"主题: {'dark' if dark else 'light'}  mode: {mode}")
    palette = DARK_PALETTE if dark else LIGHT_PALETTE

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("MaaAuto Upgrade")
    app.setStyleSheet(build_qss(palette))

    icon_path = get_icon_path()
    if icon_path:
        try:
            app.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass

    silent_mode = (mode == "silent")
    check_mode = (mode == "check")

    dlg = QDialog()
    dlg.setWindowTitle(APP_TITLE_SILENT if silent_mode else APP_TITLE)
    dlg.setMinimumSize(620, 480)
    dlg.setWindowFlags(dlg.windowFlags() & ~Qt.WindowContextHelpButtonHint)

    root = QVBoxLayout(dlg)
    root.setContentsMargins(28, 24, 28, 24)
    root.setSpacing(12)

    if silent_mode:
        head_text = "MaaAuto 正在后台升级"
    elif check_mode:
        head_text = "检查更新"
    else:
        head_text = "正在升级 MaaAuto"
    head = QLabel(head_text)
    head.setObjectName("Head")
    root.addWidget(head)

    if silent_mode:
        sub_text = "升级过程需要几分钟，主程序会在完成后自动重启。"
    elif check_mode:
        sub_text = "正在从 GitHub 检查是否有新版本..."
    else:
        sub_text = "请勿关闭此窗口，升级过程中主程序会暂时退出。"
    sub = QLabel(sub_text)
    sub.setObjectName("Sub")
    sub.setWordWrap(True)
    root.addWidget(sub)

    ver_label = QLabel(f"升级器 v{get_installer_version()}")
    ver_label.setObjectName("Ver")
    root.addWidget(ver_label)

    stage_row = QHBoxLayout()
    stage_row.setSpacing(10)
    stage_label = QLabel("准备中...")
    stage_label.setObjectName("Stage")
    stage_row.addWidget(stage_label, 1)
    pct_label = QLabel("0%")
    pct_label.setObjectName("Pct")
    pct_label.setFixedWidth(48)
    pct_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    stage_row.addWidget(pct_label)
    root.addLayout(stage_row)

    bar = QProgressBar()
    bar.setObjectName("Bar")
    bar.setRange(0, 100)
    bar.setValue(0)
    bar.setTextVisible(False)
    bar.setFixedHeight(10)
    root.addWidget(bar)

    log_view = QTextEdit()
    log_view.setObjectName("Log")
    log_view.setReadOnly(True)
    log_view.setAcceptRichText(False)
    log_view.setLineWrapMode(QTextEdit.NoWrap)
    root.addWidget(log_view, 1)

    btn_row = QHBoxLayout()
    btn_row.addStretch()

    btn_secondary = QPushButton("稍后" if check_mode else "取消")
    btn_secondary.setCursor(Qt.PointingHandCursor)
    btn_row.addWidget(btn_secondary)

    btn_primary = QPushButton("立即升级")
    btn_primary.setObjectName("Primary")
    btn_primary.setCursor(Qt.PointingHandCursor)
    btn_primary.hide()
    btn_row.addWidget(btn_primary)

    root.addLayout(btn_row)

    if silent_mode:
        btn_secondary.hide()
        btn_primary.hide()

    state = {
        "cancelled": False,
        "finished": False,
        "result_code": 2,
        "target_pct": 0,
        "display_pct": 0,
        "current_stage": ("locate", 0, 1),
        "current_frac": 0.0,
        "check_info": None,
        "user_decision": None,
        "phase": "check" if check_mode else "upgrade",
    }

    # ---- 日志缓冲 ----
    log_buffer = []
    log_timer = QTimer(dlg)
    log_timer.setInterval(150)
    log_timer.setSingleShot(True)

    def flush_logs():
        if not log_buffer:
            return
        lines = log_buffer[:]
        log_buffer.clear()
        cursor = log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        for line in lines:
            cursor.insertText(line + "\n")
        log_view.setTextCursor(cursor)
        sb = log_view.verticalScrollBar()
        sb.setValue(sb.maximum())
        doc = log_view.document()
        if doc.blockCount() > 3000:
            c = log_view.textCursor()
            c.movePosition(QTextCursor.MoveOperation.Start)
            for _ in range(doc.blockCount() - 3000):
                c.select(QTextCursor.SelectionType.BlockUnderCursor)
                c.removeSelectedText()
                c.deleteChar()

    log_timer.timeout.connect(flush_logs)

    def append_log(text):
        log_buffer.append(text)
        if not log_timer.isActive():
            log_timer.start()

    # ---- UI 回调 ----
    def on_stage(key):
        if key in STAGE_BOUNDS:
            start, weight = STAGE_BOUNDS[key]
            state["current_stage"] = (key, start, weight)
            state["current_frac"] = 0.0
            state["target_pct"] = max(state["target_pct"], start)
        stage_label.setText(STAGE_TEXT.get(key, key))

    def on_progress(cur, total):
        _, start, weight = state["current_stage"]
        if total > 0:
            frac = min(1.0, cur / total)
        else:
            frac = min(0.9, state["current_frac"] + 0.01)
        state["current_frac"] = frac
        pct = int(start + weight * frac)
        state["target_pct"] = max(state["target_pct"], min(99, pct))

    def on_message(text, level):
        prefix = {"info": "", "success": "[OK] ", "error": "[ERR] "}.get(level, "")
        append_log(prefix + text)

    # ---- 按钮 ----
    def on_secondary():
        if state["finished"]:
            dlg.accept()
            return
        if check_mode and state["phase"] == "check":
            dlg.accept()
            return
        if state["cancelled"]:
            return
        if QMessageBox.question(
            dlg, "确认取消",
            "升级正在进行中，取消可能留下不完整的安装。\n\n确定要取消吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        state["cancelled"] = True
        btn_secondary.setEnabled(False)
        btn_secondary.setText("正在取消...")
        append_log("[用户] 已请求取消")

    def on_primary():
        if state["phase"] == "check":
            state["user_decision"] = "upgrade"
            btn_primary.setEnabled(False)
            btn_secondary.setEnabled(False)
            btn_primary.setText("升级中...")
            stage_label.setText("准备升级...")

    btn_secondary.clicked.connect(on_secondary)
    btn_primary.clicked.connect(on_primary)

    # ---- 关闭事件 ----
    def close_event(ev):
        if state["finished"]:
            ev.accept()
            return
        if silent_mode:
            ev.ignore()
            return
        if check_mode and state["phase"] == "check":
            state["user_decision"] = "cancel"
            ev.accept()
            return
        if QMessageBox.question(
            dlg, "确认取消",
            "升级正在进行中，关闭窗口将中止升级。\n\n确定要中止吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) == QMessageBox.Yes:
            state["cancelled"] = True
            btn_secondary.setEnabled(False)
            btn_secondary.setText("正在取消...")
            append_log("[用户] 已请求取消")
        ev.ignore()

    dlg.closeEvent = close_event

    # ---- 进度平滑 ----
    anim = QTimer(dlg)
    anim.setInterval(30)

    def anim_tick():
        if state["display_pct"] < state["target_pct"]:
            diff = state["target_pct"] - state["display_pct"]
            state["display_pct"] += max(1, diff // 6)
            if state["display_pct"] > state["target_pct"]:
                state["display_pct"] = state["target_pct"]
            bar.setValue(state["display_pct"])
            pct_label.setText(f"{state['display_pct']}%")
        elif state["target_pct"] >= 100 and state["display_pct"] < 100:
            state["display_pct"] = 100
            bar.setValue(100)
            pct_label.setText("100%")

    anim.timeout.connect(anim_tick)
    anim.start()

    # ---- Worker ----
    class Worker(QThread):
        stage_sig = Signal(str)
        progress_sig = Signal(int, int)
        message_sig = Signal(str, str)
        finished_code = Signal(int)

        def __init__(self, phase: str):
            super().__init__()
            self.phase = phase

        def run(self):
            code = 2
            try:
                flow = UpgradeFlow(
                    args, log,
                    on_stage=lambda k: self.stage_sig.emit(k),
                    on_progress=lambda c, t: self.progress_sig.emit(c, t),
                    on_message=lambda t, l: self.message_sig.emit(t, l),
                    cancel_check=lambda: state["cancelled"],
                    skip_check=(self.phase == "upgrade_after_check"),
                    pre_check_info=state.get("check_info"),
                )
                code = flow.run_full()
                self.finished_code.emit(code)
            except Exception as e:
                log.error(f"Worker 异常: {e}")
                log.error(traceback.format_exc())
                self.finished_code.emit(2)

    def do_check_sync():
        try:
            from installer.core.upgrade_engine import (
                read_manifest, check_update, check_installer_version,
                DEFAULT_MIN_INSTALLER_VERSION,
            )
        except Exception as e:
            log.error(f"import engine 失败: {e}")
            append_log(f"[ERR] {e}")
            return None, 2

        flow = UpgradeFlow(args, log,
                           on_message=lambda t, l: append_log(t))
        info, code = flow._do_check(
            check_update, read_manifest,
            check_installer_version, DEFAULT_MIN_INSTALLER_VERSION
        )
        if info is not None:
            state["check_info"] = info
        return info, code

    # ---- 完成回调 ----
    def on_finished(code):
        state["result_code"] = code
        state["finished"] = True
        state["target_pct"] = 100

        if code == 0:
            stage_label.setText("升级完成")
        elif code == 1:
            stage_label.setText("已是最新")
        else:
            stage_label.setText("升级失败")

        # ★ 关键修复：无论 silent 与否，成功/已最新都延迟自动关闭
        if code in (0, 1):
            delay = 2500 if silent_mode else 2200
            QTimer.singleShot(delay, lambda: dlg.accept())
        else:
            # 失败
            if silent_mode:
                # silent 模式失败也要关闭（主程序侧会处理 flag）
                QTimer.singleShot(3000, lambda: dlg.accept())
            else:
                # 交互模式失败：保留窗口让用户看错误
                btn_secondary.setText("关闭")
                btn_secondary.setEnabled(True)
                btn_primary.hide()

    # ---- 启动逻辑 ----
    if check_mode:
        def start_check():
            flush_logs()
            stage_label.setText("正在检查更新...")
            info, code = do_check_sync()
            flush_logs()

            if code == 1:
                head.setText("已是最新版本")
                sub.setText(f"当前版本 v{info.current} 已是最新。")
                stage_label.setText("已是最新")
                state["target_pct"] = 100
                state["finished"] = True
                btn_secondary.setText("关闭")
                btn_secondary.setEnabled(True)
                state["result_code"] = 1
                btn_primary.hide()
                return

            if code == 2 or info is None:
                head.setText("检查失败")
                sub.setText("请查看下方日志，或稍后重试。")
                stage_label.setText("检查失败")
                state["finished"] = True
                btn_secondary.setText("关闭")
                btn_secondary.setEnabled(True)
                state["result_code"] = 2
                btn_primary.hide()
                return

            # 有新版
            head.setText(f"发现新版本 v{info.latest}")
            sub.setText(f"当前 v{info.current} → 最新 v{info.latest}")
            stage_label.setText("是否立即升级？")
            state["target_pct"] = 100
            state["display_pct"] = 100
            bar.setValue(100)
            pct_label.setText("100%")
            btn_primary.setText("立即升级")
            btn_primary.setEnabled(True)
            btn_primary.show()
            state["result_code"] = 0

            poll = QTimer(dlg)
            poll.setInterval(150)

            def poll_decision():
                if state["user_decision"] == "upgrade":
                    poll.stop()
                    head.setText("正在升级 MaaAuto")
                    sub.setText("请勿关闭此窗口，升级过程中主程序会暂时退出。")
                    stage_label.setText("准备升级...")
                    state["phase"] = "upgrade"
                    state["target_pct"] = 0
                    state["display_pct"] = 0
                    state["current_stage"] = ("locate", 0, 1)
                    state["current_frac"] = 0.0
                    bar.setValue(0)
                    pct_label.setText("0%")
                    btn_primary.hide()
                    btn_secondary.setText("取消")
                    btn_secondary.setEnabled(True)

                    worker = Worker(phase="upgrade_after_check")
                    worker.stage_sig.connect(on_stage)
                    worker.progress_sig.connect(on_progress)
                    worker.message_sig.connect(on_message)
                    worker.finished_code.connect(on_finished)
                    worker.start()

            poll.timeout.connect(poll_decision)
            poll.start()

        QTimer.singleShot(200, start_check)
    else:
        worker = Worker(phase="upgrade")
        worker.stage_sig.connect(on_stage)
        worker.progress_sig.connect(on_progress)
        worker.message_sig.connect(on_message)
        worker.finished_code.connect(on_finished)
        QTimer.singleShot(200, lambda: worker.start())

    dlg.exec()
    return state["result_code"]


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #
def main():
    args = parse_args(sys.argv[1:])

    if not args.from_main:
        win_msg(
            APP_TITLE,
            "本程序由 MaaAuto 主程序自动调用。\n\n"
            "请打开 MaaAuto，在【设置】或【关于】中检查更新。",
            MB_OK | MB_ICONINFORMATION,
        )
        return 0

    install_dir = get_install_dir()
    log = Logger(install_dir)
    log.open()

    try:
        if args.silent and args.check_only:
            return run_headless(args, log)

        if args.check_only:
            return run_ui(args, log, mode="check")

        if args.silent:
            return run_ui(args, log, mode="silent")

        return run_ui(args, log, mode="upgrade")
    except Exception as e:
        log.error(f"未捕获异常: {e}")
        log.error(traceback.format_exc())
        if not args.silent:
            win_msg(APP_TITLE,
                    f"升级器内部错误：\n\n{e}\n\n日志：{log.log_path}",
                    MB_OK | MB_ICONERROR)
        return 2
    finally:
        log.close()


if __name__ == "__main__":
    sys.exit(main())