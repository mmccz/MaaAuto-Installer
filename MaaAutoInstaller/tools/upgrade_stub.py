"""MaaAuto 升级器（``upgrade.exe``）—— 3.0.0 payload 模式。

不再在用户机上编译：下载 CI 产出的 ``MaaAuto_payload_v{ver}.zip``，
校验、解压、备份替换、更新 manifest，失败回滚。

命令行（与 2.x 保持一致，主程序无需改调用方式）::

    upgrade.exe --from-main [--restart] [--silent] [--check-only]
                [--downgrade] [--channel stable|beta]

退出码：0 成功/有新版本；1 仅 --check-only 且已最新；2 错误。
"""

import argparse
import datetime
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path

# 兼容两种布局：① 仓库里 tools/upgrade_stub.py ② 打包后的根目录
_HERE = Path(__file__).resolve().parent
if (_HERE / "installer").is_dir():
    _ROOT = _HERE
else:
    _ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from installer import __version__ as INSTALLER_VERSION
from installer.core import (
    read_manifest, write_manifest,
    check_update, compare_versions, sha256_of_file, download_file,
    is_main_running, request_main_exit,
    clear_upgrading_flag, write_failure_flag,
    apply_payload, restart_main,
    cleanup_old_exe, cleanup_backups,
    DEFAULT_MIN_INSTALLER_VERSION,
)

APP_TITLE = "MaaAuto 升级程序"
APP_TITLE_SILENT = "MaaAuto 后台升级中"
MAIN_EXE = "MaaAuto.exe"


# --------------------------------------------------------------------------- #
# 参数
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


def get_install_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# 日志
# --------------------------------------------------------------------------- #
class Logger:
    def __init__(self, install_dir: Path):
        self.install_dir = Path(install_dir)
        self.log_path = None
        self._fh = None

    def open(self) -> Path:
        ts = time.strftime("%Y%m%d_%H%M%S")
        self.log_path = Path(tempfile.gettempdir()) / f"MaaAuto_upgrade_{ts}.log"
        try:
            self._fh = open(self.log_path, "w", encoding="utf-8")
        except Exception:
            self._fh = None
        self.info(f"{APP_TITLE} {INSTALLER_VERSION}")
        self.info(f"argv: {sys.argv}")
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
        line = f"[{datetime.datetime.now():%H:%M:%S}] [{level}] {msg}"
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

    def info(self, msg): self._write("INFO", msg)
    def warn(self, msg): self._write("WARN", msg)
    def error(self, msg): self._write("ERROR", msg)

    def copy_to_install(self) -> None:
        """把本次日志复制到 ``<install>/logs/upgrade/``。"""
        if not self.log_path or not Path(self.log_path).exists():
            return
        try:
            target_dir = self.install_dir / "logs" / "upgrade"
            target_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copy2(self.log_path, target_dir / f"{stamp}.log")
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# 流程
# --------------------------------------------------------------------------- #
class UpgradeFlow:
    def __init__(self, args, log: Logger,
                 on_stage=None, on_progress=None, on_message=None,
                 cancel_check=None):
        self.args = args
        self.log = log
        self.on_stage = on_stage
        self.on_progress = on_progress
        self.on_message = on_message
        self.cancel_check = cancel_check
        self.install_dir = get_install_dir()
        self.manifest = None
        self._fail_reason = ""

    # ---- 回调 ----
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
        self.log.info(text)
        if self.on_message:
            try:
                self.on_message(str(text), level)
            except Exception:
                pass

    def _cancelled(self):
        if self.cancel_check:
            try:
                return bool(self.cancel_check())
            except Exception:
                return False
        return False

    # ---- 终态 ----
    def _restart_if_needed(self, reason: str) -> bool:
        if not getattr(self.args, "restart", False):
            self.log.info(f"未指定 --restart，跳过重启（{reason}）")
            return False
        try:
            if is_main_running():
                self.log.info("主程序仍在运行，跳过重启")
                return False
        except Exception:
            pass
        clear_upgrading_flag(self.install_dir)
        self.log.info(f"重启主程序（{reason}）")
        return restart_main(self.install_dir, log=self.log.info)

    def _write_failure(self, reason: str, info=None) -> None:
        try:
            write_failure_flag(
                install_dir=self.install_dir,
                from_version=(self.manifest.version if self.manifest else "?"),
                to_version=(getattr(info, "latest", "") if info else ""),
                reason=reason,
                log_path=str(self.log.log_path or ""),
            )
            self.log.info(f"已写 upgrade_failed.flag: {reason}")
        except Exception as e:
            self.log.warn(f"写 upgrade_failed.flag 失败: {e}")

    # ---- 检查 ----
    def _settings(self):
        extra = (self.manifest.extra if self.manifest else {}) or {}
        api = extra.get("update_api") or \
            "https://api.github.com/repos/mmccz/MaaAuto-Tool-works/releases/latest"
        prefix = extra.get("payload_asset_prefix") or "MaaAuto_payload_v"
        min_ver = extra.get("min_installer_version") or DEFAULT_MIN_INSTALLER_VERSION
        return api, prefix, min_ver

    def _do_check(self):
        self._stage("locate")
        self.manifest = read_manifest(self.install_dir)
        if self.manifest is None:
            self.log.error(f"找不到 .maaauto.json: {self.install_dir}")
            self._fail_reason = "缺少安装信息 (.maaauto.json)"
            self._msg("未找到安装信息，请用完整安装包重新安装。", "error")
            return None, 2

        api, prefix, min_ver = self._settings()
        self.log.info(f"当前版本 {self.manifest.version}，升级器 {INSTALLER_VERSION}")

        cmp_result = compare_versions(INSTALLER_VERSION, min_ver)
        if cmp_result is None or cmp_result < 0:
            msg = f"升级器版本过低（需要 ≥ {min_ver}），请下载最新完整安装包。"
            self.log.error(msg)
            self._fail_reason = msg
            self._msg(msg, "error")
            return None, 2

        self._stage("check")
        info = check_update(self.manifest, api, prefix,
                            allow_downgrade=bool(self.args.downgrade),
                            log=self.log.info)
        if info.error:
            self.log.error(f"检查更新失败: {info.error}")
            self._fail_reason = f"检查更新失败: {info.error}"
            self._msg(f"检查更新失败：{info.error}", "error")
            return None, 2

        if not info.has_update:
            self.log.info(f"已是最新版本 ({info.current})")
            self._msg(f"已是最新版本 v{info.current}", "info")
            return info, 1
        self._msg(f"发现新版本：v{info.current} → v{info.latest}", "info")
        return info, 0

    # ---- 仅检查 ----
    def run_check_only(self) -> int:
        try:
            _info, code = self._do_check()
            return code
        except Exception as e:
            self.log.error(f"检查异常: {e}\n{traceback.format_exc()}")
            self._msg(f"检查更新失败：{e}", "error")
            return 2

    # ---- 完整升级 ----
    def run_full(self) -> int:
        cleanup_old_exe(self.install_dir)
        cleanup_backups(self.install_dir)

        info, code = self._do_check()
        if code == 2:
            self._write_failure(self._fail_reason or "检查更新失败")
            self._restart_if_needed("检查更新失败")
            return 2
        if code == 1 or info is None or not info.has_update:
            self._restart_if_needed("已是最新")
            return 1 if self.args.check_only else 0

        if self.args.check_only:
            self.log.info("--check-only 模式，不执行升级")
            return 0

        if self._cancelled():
            self.log.info("用户取消")
            self._restart_if_needed("用户取消")
            return 0

        # 1) 下载 payload
        self._stage("download")
        work = Path(tempfile.gettempdir()) / f"MaaAuto_payload_dl_{int(time.time())}"
        work.mkdir(parents=True, exist_ok=True)
        payload = work / info.payload_name
        try:
            self._msg(f"下载 payload（{info.payload_size / 1048576:.1f} MB）...", "info")
            download_file(info.payload_url, payload, log=self.log.info,
                          progress=self._progress)
        except Exception as e:
            self.log.error(f"下载失败: {e}")
            self._write_failure(f"下载 payload 失败: {e}", info)
            shutil.rmtree(work, ignore_errors=True)
            self._restart_if_needed("下载失败")
            return 2

        if self._cancelled():
            shutil.rmtree(work, ignore_errors=True)
            self._restart_if_needed("用户取消")
            return 0

        # 2) 校验
        self._stage("verify")
        try:
            actual = sha256_of_file(payload)
        except Exception as e:
            self._write_failure(f"读取 payload 失败: {e}", info)
            shutil.rmtree(work, ignore_errors=True)
            self._restart_if_needed("校验失败")
            return 2

        expected = (info.payload_sha or "").lower()
        if expected and actual != expected:
            msg = f"payload 校验失败：期望 {expected[:12]}…，实际 {actual[:12]}…"
            self.log.error(msg)
            self._write_failure(msg, info)
            shutil.rmtree(work, ignore_errors=True)
            self._restart_if_needed("校验失败")
            return 2
        self.log.info(f"payload sha256: {actual}")

        # 3) 停主程序
        self._stage("stop_main")
        if not request_main_exit(self.install_dir, log=self.log.info):
            self.log.error("无法停止主程序")
            self._write_failure("无法停止主程序", info)
            clear_upgrading_flag(self.install_dir)
            shutil.rmtree(work, ignore_errors=True)
            self._restart_if_needed("无法停止主程序")
            return 2

        # 4) 替换
        self._stage("apply")
        old_version = self.manifest.version
        result = apply_payload(self.install_dir, payload, log=self.log.info,
                               progress=self._progress,
                               cancel_check=self._cancelled)
        shutil.rmtree(work, ignore_errors=True)

        if not result.success:
            self.log.error(f"替换失败: {result.error}")
            self._write_failure(f"替换失败: {result.error}", info)
            clear_upgrading_flag(self.install_dir)
            self._restart_if_needed("升级失败")
            return 2

        # 5) 更新 manifest
        self._stage("manifest")
        try:
            self.manifest.version = info.latest
            self.manifest.installer_version = INSTALLER_VERSION
            self.manifest.last_upgrade_from = old_version
            self.manifest.last_checked_at = datetime.datetime.now().isoformat(timespec="seconds")
            self.manifest.source_hash = actual
            write_manifest(self.install_dir, self.manifest)
        except Exception as e:
            self.log.warn(f"更新 .maaauto.json 失败: {e}")

        clear_upgrading_flag(self.install_dir)
        self.log.copy_to_install()
        cleanup_backups(self.install_dir)
        self._msg(f"升级完成：v{old_version} → v{info.latest}", "success")
        time.sleep(1.0)
        self._restart_if_needed("升级成功")
        return 0


# --------------------------------------------------------------------------- #
# 无 UI 模式
# --------------------------------------------------------------------------- #
def run_headless(args, log: Logger) -> int:
    flow = UpgradeFlow(args, log)
    return flow.run_check_only() if args.check_only else flow.run_full()


# --------------------------------------------------------------------------- #
# 进度窗
# --------------------------------------------------------------------------- #
STAGE_TEXT = {
    "locate": "读取安装信息…",
    "check": "检查更新…",
    "download": "下载更新包…",
    "verify": "校验文件…",
    "stop_main": "等待主程序退出…",
    "apply": "替换程序文件…",
    "manifest": "更新安装信息…",
    "restart": "重启主程序…",
    "done": "完成",
}


def run_ui(args, log: Logger, mode: str = "upgrade") -> int:
    from PySide6.QtCore import QThread, Signal, QTimer
    from PySide6.QtWidgets import (QApplication, QDialog, QLabel, QProgressBar,
                                   QPushButton, QTextEdit, QVBoxLayout, QHBoxLayout)

    class Worker(QThread):
        stage = Signal(str)
        progress = Signal(int, int)
        message = Signal(str, str)
        finished_code = Signal(int)

        def __init__(self, flow):
            super().__init__()
            self.flow = flow

        def run(self):
            try:
                code = self.flow.run_check_only() if args.check_only else self.flow.run_full()
            except Exception:
                code = 2
            self.finished_code.emit(code)

    class Dialog(QDialog):
        def __init__(self):
            super().__init__()
            self.setWindowTitle(APP_TITLE_SILENT if args.silent else APP_TITLE)
            self.setMinimumSize(520, 380)
            self.cancelled = False
            self.code = None

            lay = QVBoxLayout(self)
            self.stage_label = QLabel("准备中…")
            self.stage_label.setStyleSheet("font-size:14px;font-weight:600;")
            lay.addWidget(self.stage_label)

            self.bar = QProgressBar()
            self.bar.setRange(0, 100)
            lay.addWidget(self.bar)

            self.log_view = QTextEdit()
            self.log_view.setReadOnly(True)
            lay.addWidget(self.log_view, 1)

            row = QHBoxLayout()
            row.addStretch(1)
            self.btn = QPushButton("后台升级中…" if args.silent else "取消")
            self.btn.setEnabled(not args.silent)
            self.btn.clicked.connect(self._on_cancel)
            row.addWidget(self.btn)
            lay.addLayout(row)

            self.flow = UpgradeFlow(
                args, log,
                on_stage=self._on_stage,
                on_progress=self._on_progress,
                on_message=self._on_message,
                cancel_check=lambda: self.cancelled,
            )
            self.worker = Worker(self.flow)
            self.worker.stage.connect(self._on_stage)
            self.worker.progress.connect(self._on_progress)
            self.worker.message.connect(self._on_message)
            self.worker.finished_code.connect(self._on_finished)

        def _on_cancel(self):
            self.cancelled = True
            self.btn.setEnabled(False)
            self.stage_label.setText("正在取消…")

        def _on_stage(self, key):
            self.stage_label.setText(STAGE_TEXT.get(key, key))
            self.log_view.append(f"· {STAGE_TEXT.get(key, key)}")

        def _on_progress(self, cur, total):
            self.bar.setRange(0, max(1, total))
            self.bar.setValue(cur)

        def _on_message(self, text, level):
            self.log_view.append(text)

        def _on_finished(self, code):
            self.code = code
            if code == 0:
                self.stage_label.setText("升级完成，正在重启…")
                self.bar.setValue(self.bar.maximum())
            elif code == 1:
                self.stage_label.setText("已是最新版本")
            else:
                self.stage_label.setText("升级失败，详见日志")
            delay = 800 if (args.silent or args.check_only) else 2500
            QTimer.singleShot(delay, self.accept)

        def reject(self):
            # silent 模式不允许关窗打断升级
            if args.silent and self.code is None:
                return
            super().reject()

    app = QApplication.instance() or QApplication(sys.argv)
    dlg = Dialog()
    dlg.worker.start()
    dlg.exec()
    try:
        dlg.worker.wait(3000)
    except Exception:
        pass
    return dlg.code if dlg.code is not None else 2


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #
def main() -> int:
    args = parse_args(sys.argv[1:])
    install_dir = get_install_dir()
    log = Logger(install_dir)
    log.open()

    if not args.from_main:
        log.warn("缺少 --from-main，退出（防止误双击触发升级）")
        log.close()
        return 0

    try:
        if args.silent and args.check_only:
            return run_headless(args, log)
        return run_ui(args, log, mode="silent" if args.silent else "upgrade")
    except Exception:
        log.error(f"未捕获异常:\n{traceback.format_exc()}")
        return 2
    finally:
        log.close()


if __name__ == "__main__":
    sys.exit(main())
