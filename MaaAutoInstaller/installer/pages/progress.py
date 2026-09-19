"""第 4 步：安装进度（新流程：用户本地打包主程序）。"""

import os
import re
import sys
import tempfile
import traceback
from pathlib import Path

from PySide6.QtWidgets import (QVBoxLayout, QLabel, QProgressBar,
                               QTextEdit, QMessageBox)
from PySide6.QtCore import QThread, Signal, QTimer
from PySide6.QtGui import QTextCursor

from installer.pages.base import BasePage
from installer.core import (download_file,
                            resolve_pypi_mirror, resolve_python_mirror,
                            unpack_source, hash_requirements,
                            install_embedded_python, verify_python,
                            get_python_version, PYTHON_VERSION,
                            ensure_pip, install_requirements, install_pyinstaller,
                            build_main_program, copy_dist_to_install,
                            deploy_uninstaller, deploy_upgrader,
                            create_desktop_shortcut, create_startmenu_shortcut,
                            Manifest, write_manifest,
                            remove_work_dir, clean_pip_cache, clean_system_temp)


# --------------------------------------------------------------------------- #
# 内嵌资源查找
# --------------------------------------------------------------------------- #
def _exe_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def _meipass_dir() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return _exe_dir()


def _find_source_zip() -> Path:
    """MaaAuto_Source.zip 与安装器同级。"""
    p = _exe_dir() / "MaaAuto_Source.zip"
    if p.exists():
        return p
    # 开发兜底
    p = _exe_dir() / "_embedded" / "source.zip"
    if p.exists():
        return p
    raise FileNotFoundError(
        "找不到 MaaAuto_Source.zip\n"
        "请确保它与 MaaAuto_Setup.exe 在同一目录。"
    )


def _find_embedded_stub(name: str) -> Path:
    """从内嵌取 uninstall.exe / upgrade.exe。"""
    p = _meipass_dir() / "_embedded" / name
    if p.exists():
        return p
    # 开发兜底：tools/_out/
    p = _exe_dir() / "tools" / "_out" / name
    if p.exists():
        return p
    raise FileNotFoundError(f"找不到内嵌 {name}（请先运行 tools/build_stubs.py）")


# --------------------------------------------------------------------------- #
# 中断异常
# --------------------------------------------------------------------------- #
class _InterruptedError(Exception):
    pass


# --------------------------------------------------------------------------- #
# 后台安装 Worker
# --------------------------------------------------------------------------- #
class InstallWorker(QThread):
    log_signal = Signal(str)
    stage_signal = Signal(str)
    progress_signal = Signal(int, int)
    done_signal = Signal(bool, str)

    def __init__(self, state, installer_version: str, parent=None):
        super().__init__(parent)
        self.state = state
        self.installer_version = installer_version

    # ---- 便捷回调 ----
    def _log(self, msg):
        self.log_signal.emit(str(msg))

    def _stage(self, key):
        self.stage_signal.emit(key)

    def _progress(self, cur, total):
        self.progress_signal.emit(int(cur), int(total))

    def _check(self):
        if self.isInterruptionRequested():
            raise _InterruptedError("用户中止")

    # ------------------------------------------------------------------ #
    def run(self):
        try:
            self._do_install()
            self.done_signal.emit(True, "")
        except _InterruptedError:
            self.done_signal.emit(False, "__ABORTED__")
        except Exception as e:
            self.log_signal.emit(traceback.format_exc())
            self.done_signal.emit(False, str(e))

    # ------------------------------------------------------------------ #
    @staticmethod
    def _read_app_version(source_dir: Path) -> str:
        try:
            info = source_dir / "app_info.py"
            if info.exists():
                text = info.read_text(encoding="utf-8")
                m = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']*)["\']',
                              text, re.M)
                if m:
                    return m.group(1)
        except Exception:
            pass
        return "0.0.0"

    # ------------------------------------------------------------------ #
    def _do_install(self):
        s = self.state
        install_dir = Path(s.install_dir).resolve()
        install_dir.mkdir(parents=True, exist_ok=True)

        # ---- 0. 准备：创建临时工作目录 ----
        self._check()
        self._stage("page.progress.stage.prepare")
        self._log(f"安装目录: {install_dir}")

        # 工作目录放在 install_dir 的父目录下，确保删除时不出错
        work_dir = Path(tempfile.mkdtemp(
            prefix="MaaAuto_build_",
            dir=str(install_dir.parent),
        ))
        s.work_dir = work_dir
        self._log(f"临时工作目录: {work_dir}")
        self._log(f"安装器版本: {self.installer_version}")

        # ---- 1. 下载 embeddable Python ----
        self._check()
        self._stage("page.progress.stage.download_python")
        python_dir = work_dir / "python"
        python_mirror = resolve_python_mirror(s.mirror or "auto", PYTHON_VERSION)
        self._log(f"Python 镜像: {python_mirror}")

        python_exe, _pythonw, python_dir = install_embedded_python(
            python_dir, python_mirror,
            log=self._log, progress=self._progress,
            temp_dir=work_dir / "_dl",
        )
        if not verify_python(python_exe):
            raise RuntimeError("Python 环境验证失败")

        py_ver = get_python_version(python_exe)
        self._log(f"Python 就绪: {python_exe} ({py_ver})")
        s.python_dir = python_dir
        s.python_exe = python_exe
        s.python_exe_console = python_exe
        s.python_version = py_ver

        # ---- 2. 解压源码 ----
        self._check()
        self._stage("page.progress.stage.unpack_source")
        source_zip = _find_source_zip()
        self._log(f"源码包: {source_zip.name}")

        source_dir = work_dir / "source"
        unpack_source(source_zip, source_dir, log=self._log)
        s.source_dir = source_dir
        s.app_version = self._read_app_version(source_dir)
        self._log(f"应用版本: {s.app_version}")

        # ---- 3. 装 pip ----
        self._check()
        ensure_pip(python_exe, log=self._log, temp_dir=work_dir / "_dl")

        # ---- 4. 装主程序依赖 ----
        self._check()
        self._stage("page.progress.stage.install_deps")
        pypi_url = resolve_pypi_mirror(s.mirror or "auto")
        req_file = source_dir / "requirements.txt"
        if req_file.exists():
            install_requirements(python_exe, req_file, pypi_url, log=self._log)
            s.requirements_hash = hash_requirements(req_file)
        else:
            self._log("未找到 requirements.txt，跳过依赖安装")

        # ---- 5. 装 PyInstaller ----
        self._check()
        self._stage("page.progress.stage.install_pyinstaller")
        install_pyinstaller(python_exe, pypi_url, log=self._log)

        # ---- 6. 本地打包主程序 ----
        self._check()
        self._stage("page.progress.stage.build_main")
        dist_app_dir = build_main_program(
            source_dir, python_exe, log=self._log, timeout=1800,
        )
        s.dist_app_dir = dist_app_dir

        # ---- 7. 拷贝产物到安装目录 ----
        self._check()
        copy_dist_to_install(dist_app_dir, install_dir, log=self._log)

        # ---- 8. 释放 uninstall.exe / upgrade.exe ----
        self._check()
        self._stage("page.progress.stage.deploy_stubs")
        uninstall_src = _find_embedded_stub("uninstall.exe")
        upgrade_src = _find_embedded_stub("upgrade.exe")
        uninstall_dst = deploy_uninstaller(uninstall_src, install_dir, log=self._log)
        upgrade_dst = deploy_upgrader(upgrade_src, install_dir, log=self._log)

        # ---- 9. 快捷方式 ----
        self._check()
        self._stage("page.progress.stage.create_shortcut")
        main_exe = install_dir / "MaaAuto.exe"
        icon_path = install_dir / "resources" / "icon.ico"
        if not icon_path.exists():
            # 有些项目资源路径不同，兜底用主 exe 图标
            icon_path = main_exe

        if s.create_desktop_shortcut:
            try:
                p = create_desktop_shortcut(main_exe, install_dir,
                                            "MaaAuto", icon_path)
                if p:
                    self._log(f"桌面快捷方式: {p.name}")
            except Exception as e:
                self._log(f"创建桌面快捷方式失败: {e}")

        if s.create_startmenu_shortcut:
            try:
                p = create_startmenu_shortcut(main_exe, install_dir,
                                              "MaaAuto", icon_path)
                if p:
                    self._log(f"开始菜单快捷方式: {p.name}")
            except Exception as e:
                self._log(f"创建开始菜单快捷方式失败: {e}")

        # ---- 10. 写 manifest ----
        self._check()
        self._stage("page.progress.stage.write_manifest")
        manifest = Manifest(
            version=s.app_version,
            installer_version=self.installer_version,
            install_dir=str(install_dir),
            app_exe=str(main_exe),
            uninstall_exe=str(uninstall_dst),
            upgrade_exe=str(upgrade_dst),
            requirements_hash=s.requirements_hash,
            mirror=s.mirror or "",
            extra={},
        )
        write_manifest(install_dir, manifest)
        self._log(f"元数据: {install_dir / '.maaauto.json'}")

        # ---- 11. 清理 ----
        if s.cleanup_after_install:
            self._check()
            self._stage("page.progress.stage.cleanup")
            self._log("清理临时文件...")
            remove_work_dir(work_dir, log=self._log)
            clean_pip_cache(python_exe=python_exe, log=self._log)
            clean_system_temp(log=self._log)
        else:
            self._log(f"（跳过了清理，临时目录仍保留在: {work_dir}）")

        # ---- 12. 完成 ----
        self._stage("page.progress.stage.done")
        self._log("=" * 48)
        self._log(f"安装完成！MaaAuto {s.app_version}")
        self._log(f"安装目录: {install_dir}")
        self._log("=" * 48)
        s.success = True


# --------------------------------------------------------------------------- #
# 进度页
# --------------------------------------------------------------------------- #
class ProgressPage(BasePage):

    is_progress = True
    LOG_FLUSH_MS = 150
    LOG_MAX_BLOCKS = 4000

    def __init__(self, i18n, state, parent=None):
        super().__init__(i18n, state, parent)
        self.worker = None
        self._installed = False
        self._log_buffer = []
        self._trim_counter = 0

        self._log_timer = QTimer(self)
        self._log_timer.setInterval(self.LOG_FLUSH_MS)
        self._log_timer.timeout.connect(self._flush_logs)
        self._log_timer.setSingleShot(True)

        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(14)

        self.title = QLabel(self.i18n.t("page.progress.title"))
        self.title.setObjectName("PageHeading")
        root.addWidget(self.title)

        self.desc = QLabel(self.i18n.t("page.progress.desc"))
        self.desc.setObjectName("PageSubtitle")
        self.desc.setWordWrap(True)
        root.addWidget(self.desc)

        root.addSpacing(4)

        self.stage_label = QLabel(self.i18n.t("page.progress.stage.prepare"))
        self.stage_label.setObjectName("PageStage")
        root.addWidget(self.stage_label)

        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        root.addWidget(self.bar)

        self.eta_hint = QLabel(self.i18n.t("page.progress.eta_hint"))
        self.eta_hint.setObjectName("PageHint")
        self.eta_hint.setWordWrap(True)
        root.addWidget(self.eta_hint)

        self.log_view = QTextEdit()
        self.log_view.setObjectName("WizardLog")
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText(self.i18n.t("page.progress.log_empty"))
        self.log_view.setAcceptRichText(False)
        root.addWidget(self.log_view, 1)

    # ------------------------------------------------------------------ #
    def on_enter(self):
        if self.worker is not None and self.worker.isRunning():
            return
        if self._installed:
            return

        from installer import __version__ as installer_version
        self.worker = InstallWorker(self.state, installer_version, self)
        self.worker.log_signal.connect(self._on_log)
        self.worker.stage_signal.connect(self._on_stage)
        self.worker.progress_signal.connect(self._on_progress)
        self.worker.done_signal.connect(self._on_done)
        self.worker.start()

    def on_cancel(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.requestInterruption()

    def can_next(self):
        return self._installed

    def on_leave(self):
        return self._installed

    # ------------------------------------------------------------------ #
    # 日志缓冲
    # ------------------------------------------------------------------ #
    def _on_log(self, msg):
        self._log_buffer.append(msg)
        if not self._log_timer.isActive():
            self._log_timer.start()

    def _flush_logs(self):
        if not self._log_buffer:
            return
        lines = self._log_buffer
        self._log_buffer = []

        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        for line in lines:
            cursor.insertText(line + "\n")
        self.log_view.setTextCursor(cursor)
        self.log_view.ensureCursorVisible()

        self._trim_counter += 1
        if self._trim_counter % 5 == 0:
            self._trim_logs()

    def _trim_logs(self):
        doc = self.log_view.document()
        over = doc.blockCount() - self.LOG_MAX_BLOCKS
        if over <= 0:
            return
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        for _ in range(over):
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

    def _on_stage(self, key):
        self.stage_label.setText(self.i18n.t(key))

    def _on_progress(self, cur, total):
        if total > 0:
            self.bar.setRange(0, total)
            self.bar.setValue(cur)
        else:
            self.bar.setRange(0, 0)

    # ------------------------------------------------------------------ #
    def _on_done(self, success, error):
        self._flush_logs()
        self._installed = success
        if success:
            self.bar.setRange(0, 1)
            self.bar.setValue(1)

        w = self.window()
        if hasattr(w, "_update_buttons"):
            w._update_buttons()

        if success:
            if hasattr(w, "_on_next"):
                w._on_next()
            if self.state.launch_after_install:
                QTimer.singleShot(400, self._launch_now)
        else:
            if error == "__ABORTED__":
                self._append_line_safe(
                    "\n[已中止] 安装未完成。"
                    f"\n临时目录保留在: {self.state.work_dir}"
                )
            else:
                QMessageBox.critical(
                    self, self.i18n.t("error.title"),
                    self.i18n.t("error.msg", error=error),
                )

    def _append_line_safe(self, text):
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text + "\n")
        self.log_view.setTextCursor(cursor)
        self.log_view.ensureCursorVisible()

    def _launch_now(self):
        try:
            exe = Path(self.state.install_dir) / "MaaAuto.exe"
            if exe.exists():
                import subprocess
                subprocess.Popen(
                    [str(exe)],
                    cwd=str(self.state.install_dir),
                    creationflags=0x00000008 | 0x00000200,
                    close_fds=True,
                )
        except Exception:
            pass

    def retranslate(self):
        self.title.setText(self.i18n.t("page.progress.title"))
        self.desc.setText(self.i18n.t("page.progress.desc"))
        self.log_view.setPlaceholderText(self.i18n.t("page.progress.log_empty"))
        self.eta_hint.setText(self.i18n.t("page.progress.eta_hint"))