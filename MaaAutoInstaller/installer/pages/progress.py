"""第 4 步：安装进度（新流程：用户本地打包主程序）。"""

import os
import re
import sys
import ctypes
import tempfile
import traceback
from pathlib import Path
from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
                               QTextEdit, QMessageBox)
from PySide6.QtCore import QThread, Signal, QTimer, Qt
from PySide6.QtGui import QTextCursor

from installer.pages.base import BasePage
from installer.core import (resolve_pypi_mirror, resolve_python_mirror,
                            unpack_source, hash_requirements,
                            install_embedded_python, verify_python,
                            get_python_version, PYTHON_VERSION,
                            ensure_pip, install_requirements, install_pyinstaller,
                            build_main_program, copy_dist_to_install,
                            deploy_uninstaller, deploy_upgrader,
                            create_desktop_shortcut, create_startmenu_shortcut,
                            Manifest, write_manifest,
                            remove_work_dir, clean_pip_cache, clean_system_temp,
                            build_all_stubs, unpack_stubs_source,register_all)


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
    """
    查找 source.zip（按优先级）：
      ① 打包后：_MEIPASS/_embedded/source.zip（内嵌）
      ② 开发时：<exe同级>/_embedded/source.zip
      ③ 兼容旧版：<exe同级>/MaaAuto_Source.zip
    """
    # ① 内嵌（打包后）
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        p = Path(meipass) / "_embedded" / "source.zip"
        if p.exists():
            return p

    # ② 开发：<exe同级>/_embedded/source.zip
    p = _exe_dir() / "_embedded" / "source.zip"
    if p.exists():
        return p

    # ③ 兼容旧版布局
    p = _exe_dir() / "MaaAuto_Source.zip"
    if p.exists():
        return p

    raise FileNotFoundError(
        "找不到 source.zip。\n"
        "若从源码运行，请确保 _embedded/source.zip 存在；\n"
        "若运行打包好的 exe，说明打包时内嵌失败，请重新构建。"
    )


def _find_stubs_source() -> Path:
    """
    查找 stubs_source.zip（按优先级）：
      ① 打包后：_MEIPASS/_embedded/stubs_source.zip
      ② 开发时：<exe同级>/_embedded/stubs_source.zip
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        p = Path(meipass) / "_embedded" / "stubs_source.zip"
        if p.exists():
            return p

    p = _exe_dir() / "_embedded" / "stubs_source.zip"
    if p.exists():
        return p

    raise FileNotFoundError(
        "找不到 stubs_source.zip。\n"
        "若从源码运行，请先跑一次 build_installer.py 生成；\n"
        "若运行打包好的 exe，说明打包时内嵌失败。"
    )

def _set_hidden(path: Path):
    """把目录设为隐藏（Windows 资源管理器默认看不到）。"""
    try:
        FILE_ATTRIBUTE_HIDDEN = 0x02
        ctypes.windll.kernel32.SetFileAttributesW(str(path),
                                                  FILE_ATTRIBUTE_HIDDEN)
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# 中断异常
# --------------------------------------------------------------------------- #
class _InterruptedError(Exception):
    pass


# --------------------------------------------------------------------------- #
# 后台安装 Worker
# --------------------------------------------------------------------------- #
class InstallWorker(QThread):
    """
    安装工作线程。

    进度模型：把整个安装切成若干"阶段"，每个阶段有固定权重（加起来 = 100）。
    阶段内部有一个 0.0~1.0 的子进度，最终百分比 = 阶段起点 + 权重 * 子进度。
    """
    log_signal = Signal(str)
    stage_signal = Signal(str)
    overall_signal = Signal(int)
    pip_count_signal = Signal(int, int)
    done_signal = Signal(bool, str)

    STAGE_LAYOUT = [
        ("page.progress.stage.prepare",              2),
        ("page.progress.stage.download_python",      8),
        ("page.progress.stage.unpack_source",        2),
        ("page.progress.stage.install_deps",        28),
        ("page.progress.stage.install_pyinstaller",  5),
        ("page.progress.stage.build_main",          28),
        ("page.progress.stage.build_stubs",         15),
        ("page.progress.stage.deploy_stubs",         2),
        ("page.progress.stage.create_shortcut",      2),
        ("page.progress.stage.write_manifest",       2),
        ("page.progress.stage.write_registry",       2),   # ★ 新增
        ("page.progress.stage.cleanup",              3),
        ("page.progress.stage.done",                 1),
    ]

    def __init__(self, state, installer_version: str, parent=None):
        super().__init__(parent)
        self.state = state
        self.installer_version = installer_version

        self._bounds = {}
        running = 0
        for key, weight in self.STAGE_LAYOUT:
            self._bounds[key] = (running, weight)
            running += weight

        self._cur_key = None
        self._cur_frac = 0.0
        self._last_pct = -1

        self._pip_seen = set()
        self._pip_collected = 0
        self._pip_estimate = 40

        self._build_lines = 0

    # ---- 便捷回调 ----
    def _log(self, msg):
        self.log_signal.emit(str(msg))

    def _stage(self, key: str):
        self._cur_key = key
        self._cur_frac = 0.0
        self.stage_signal.emit(key)
        self._emit_overall()

    def _sub(self, frac: float):
        self._cur_frac = max(0.0, min(1.0, float(frac)))
        self._emit_overall()

    def _advance(self):
        self._cur_frac = 1.0
        self._emit_overall()

    def _emit_overall(self):
        if self._cur_key is None:
            return
        start, weight = self._bounds.get(self._cur_key, (0, 0))
        pct = int(round(start + weight * self._cur_frac))
        if pct == self._last_pct:
            return
        self._last_pct = pct
        self.overall_signal.emit(pct)

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

    @staticmethod
    def _estimate_pip_total(req_file: Path) -> int:
        try:
            text = req_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return 40
        n = 0
        for ln in text.splitlines():
            s = ln.strip()
            if not s or s.startswith("#") or s.startswith("-"):
                continue
            n += 1
        return max(20, n * 3)

    def _on_download_progress(self, cur, total):
        if total > 0:
            self._sub(cur / total)

    def _pip_log(self, line):
        self._log(line)
        s = line.strip()
        if s.startswith("Collecting "):
            rest = s[len("Collecting "):].strip()
            pkg = rest.split()[0] if rest else ""
            if pkg and pkg not in self._pip_seen:
                self._pip_seen.add(pkg)
                self._pip_collected = len(self._pip_seen)
                if self._pip_estimate > 0:
                    self._sub(min(0.9, self._pip_collected / self._pip_estimate))
                    self.pip_count_signal.emit(self._pip_collected,
                                               self._pip_estimate)

    def _build_log(self, line):
        self._log(line)
        self._build_lines += 1
        self._sub(min(0.9, self._build_lines / 300))

    # ------------------------------------------------------------------ #
    def _do_install(self):
        s = self.state
        install_dir = Path(s.install_dir).resolve()
        install_dir.mkdir(parents=True, exist_ok=True)

        work_dir: Path | None = None
        try:
            # ---- 0. 准备 ----
            self._check()
            self._stage("page.progress.stage.prepare")
            self._log(f"安装目录: {install_dir}")

            work_dir = Path(tempfile.mkdtemp(
                prefix="MaaAuto_build_",
                dir=str(install_dir.parent),
            ))
            _set_hidden(work_dir)
            s.work_dir = work_dir
            self._log(f"临时工作目录: {work_dir}")
            self._log(f"安装器版本: {self.installer_version}")
            self._advance()

            # ---- 1. 下载 embeddable Python ----
            self._check()
            self._stage("page.progress.stage.download_python")
            python_dir = work_dir / "python"
            python_mirror = resolve_python_mirror(s.mirror or "auto",
                                                  PYTHON_VERSION)
            self._log(f"Python 镜像: {python_mirror}")

            python_exe, _pythonw, python_dir = install_embedded_python(
                python_dir, python_mirror,
                log=self._log, progress=self._on_download_progress,
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
            self._advance()

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
            self._advance()

            # ---- 3 + 4. 装 pip + 装主程序依赖 ----
            self._check()
            self._stage("page.progress.stage.install_deps")

            req_file = source_dir / "requirements.txt"
            self._pip_estimate = self._estimate_pip_total(req_file)
            self._pip_collected = 0
            self._pip_seen = set()

            ensure_pip(python_exe, log=self._log, temp_dir=work_dir / "_dl")

            pypi_url = resolve_pypi_mirror(s.mirror or "auto")
            if req_file.exists():
                install_requirements(python_exe, req_file, pypi_url,
                                     log=self._pip_log)
                s.requirements_hash = hash_requirements(req_file)
            else:
                self._log("未找到 requirements.txt，跳过依赖安装")
            self._advance()

            # ---- 5. 装 PyInstaller ----
            self._check()
            self._stage("page.progress.stage.install_pyinstaller")
            install_pyinstaller(python_exe, pypi_url, log=self._log)
            self._advance()

            # ---- 6 + 7. 打包主程序 + 拷贝产物 ----
            self._check()
            self._stage("page.progress.stage.build_main")
            self._build_lines = 0

            dist_app_dir = build_main_program(
                source_dir, python_exe, log=self._build_log, timeout=1800,
            )
            s.dist_app_dir = dist_app_dir
            copy_dist_to_install(dist_app_dir, install_dir, log=self._log)
            self._advance()

            # ---- 8. 本地打包 stub ----
            self._check()
            self._stage("page.progress.stage.build_stubs")
            stubs_source_zip = _find_stubs_source()
            self._log(f"stub 源码包: {stubs_source_zip.name}")

            stubs_dir = work_dir / "stubs"
            unpack_stubs_source(stubs_source_zip, stubs_dir, log=self._log)

            self._log("本地打包卸载器（~30 秒）...")
            self._log("本地打包升级器（含 PySide6，需 2-4 分钟）...")
            stub_out = work_dir / "stub_out"
            uninstall_exe, upgrade_exe = build_all_stubs(
                python_exe=python_exe,
                stub_source_dir=stubs_dir,
                out_dir=stub_out,
                log=self._log,
            )
            self._advance()

            # ---- 9. 释放 stub 到安装目录 ----
            self._check()
            self._stage("page.progress.stage.deploy_stubs")
            uninstall_dst = deploy_uninstaller(uninstall_exe, install_dir,
                                               log=self._log)
            upgrade_dst = deploy_upgrader(upgrade_exe, install_dir,
                                          log=self._log)
            self._advance()

            # ---- 10. 快捷方式 ----
            self._check()
            self._stage("page.progress.stage.create_shortcut")

            main_exe = install_dir / "MaaAuto.exe"          # ★ 补回这行
            icon_path = install_dir / "resources" / "icon.ico"
            if not icon_path.exists():
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
            self._advance()

            # ---- 11. 写 manifest ----
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
                release_channel="stable",
                # extra 用 Manifest 默认值（见 installer/core/manifest.py）
                # 这里显式传，双保险
                extra={
                    "github_url": "https://github.com/mmccz/MaaAuto-Tool-works",
                    "update_api": "https://api.github.com/repos/mmccz/MaaAuto-Tool-works/releases/latest",
                    "release_channel": "stable",
                    "launch_args": [],
                    "source_asset_name": "MaaAuto_Source.zip",
                    "online_asset_pattern": "MaaAuto_Online_*-Windows-x64.exe",
                    "min_installer_version": "1.0.0",
                },
            )
            write_manifest(install_dir, manifest)
            self._log(f"元数据: {install_dir / '.maaauto.json'}")
            self._advance()

            # ---- 12. 写注册表 ----
            self._check()
            self._stage("page.progress.stage.write_registry")
            try:
                register_all(install_dir, s.app_version,
                             set_admin=True, log=self._log)
                self._log("注册表写入完成")
            except Exception as e:
                self._log(f"注册表写入失败（非致命）: {e}")
            self._advance()

            # ---- 13. 完成 ----
            self._stage("page.progress.stage.done")
            self._log("=" * 48)
            self._log(f"安装完成！MaaAuto {s.app_version}")
            self._log(f"安装目录: {install_dir}")
            self._log("=" * 48)
            s.success = True
            self._advance()

        finally:
            # ★ 无论成功 / 失败 / 被中止，都尝试清理临时工作目录
            if work_dir is not None and work_dir.exists():
                if s.cleanup_after_install:
                    self._stage("page.progress.stage.cleanup")
                    self._log("清理临时文件...")
                    # pip 缓存需要 python.exe 还在，先做
                    try:
                        if s.python_exe and Path(s.python_exe).exists():
                            clean_pip_cache(python_exe=s.python_exe, log=self._log)
                    except Exception as e:
                        self._log(f"清理 pip 缓存失败: {e}")
                    # 删工作目录
                    try:
                        remove_work_dir(work_dir, log=self._log)
                        s.work_dir_cleaned = not work_dir.exists()
                    except Exception as e:
                        self._log(f"清理临时目录失败: {e}")
                    # 清系统临时目录
                    try:
                        clean_system_temp(log=self._log)
                    except Exception:
                        pass
                else:
                    self._log(f"（跳过了清理，临时目录仍保留在: {work_dir}）")


# --------------------------------------------------------------------------- #
# 进度页
# --------------------------------------------------------------------------- #
class ProgressPage(BasePage):

    is_progress = True
    LOG_FLUSH_MS = 150
    LOG_MAX_BLOCKS = 4000
    ANIM_INTERVAL_MS = 30

    def __init__(self, i18n, state, parent=None):
        super().__init__(i18n, state, parent)
        self.worker = None
        self._installed = False
        self._aborting = False
        self._log_buffer = []
        self._trim_counter = 0

        self._display_pct = 0
        self._target_pct = 0

        self._log_timer = QTimer(self)
        self._log_timer.setInterval(self.LOG_FLUSH_MS)
        self._log_timer.timeout.connect(self._flush_logs)
        self._log_timer.setSingleShot(True)

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(self.ANIM_INTERVAL_MS)
        self._anim_timer.timeout.connect(self._anim_tick)

        self._setup_ui()
        self._anim_timer.start()

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

        stage_row = QHBoxLayout()
        stage_row.setSpacing(10)
        self.stage_label = QLabel(self.i18n.t("page.progress.stage.prepare"))
        self.stage_label.setObjectName("PageStage")
        stage_row.addWidget(self.stage_label, 1)

        self.pct_label = QLabel("0%")
        self.pct_label.setObjectName("PagePct")
        self.pct_label.setFixedWidth(48)
        self.pct_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        stage_row.addWidget(self.pct_label)
        root.addLayout(stage_row)

        self.bar = QProgressBar()
        self.bar.setObjectName("MainProgress")
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(10)
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
        self.eta_hint = QLabel("")
        self.eta_hint.setObjectName("PageHint")
        self.eta_hint.setWordWrap(True)
        self.eta_hint.setVisible(False)
        root.addWidget(self.eta_hint)

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
        self.worker.overall_signal.connect(self._on_overall)
        self.worker.pip_count_signal.connect(self._on_pip_count)
        self.worker.done_signal.connect(self._on_done)
        self.worker.start()

    def is_aborting(self) -> bool:
        return self._aborting

    def on_cancel(self):
        """用户点中止/关窗口。只发信号，等 worker 结束再关窗口。"""
        if self._aborting:
            return
        self._aborting = True
        # 更新中止按钮文字
        w = self.window()
        if hasattr(w, "set_cancel_text"):
            w.set_cancel_text(self.i18n.t("wizard.aborting"))
        if self.worker is not None and self.worker.isRunning():
            self.worker.requestInterruption()
            self._append_line_safe(
                self.i18n.t("page.progress.aborting_log")
            )
        else:
            # worker 已结束，直接关闭
            QTimer.singleShot(0, lambda: self.window().reject())

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

    # ------------------------------------------------------------------ #
    # 进度
    # ------------------------------------------------------------------ #
    def _on_stage(self, key):
        self.stage_label.setText(self.i18n.t(key))
        # ★ 提示随阶段变化；没定义则隐藏
        hint_key = f"{key}.hint"
        hint = self.i18n.t(hint_key)
        if hint == hint_key:
            self.eta_hint.setVisible(False)
        else:
            self.eta_hint.setText(hint)
            self.eta_hint.setVisible(True)

    def _on_pip_count(self, current, total):
        if self.worker is not None and self.worker._cur_key == \
                "page.progress.stage.install_deps":
            key = "page.progress.stage.install_deps.with_count"
            self.stage_label.setText(
                self.i18n.t(key, current=current, total=total)
            )

    def _on_overall(self, pct):
        self._target_pct = max(0, min(100, int(pct)))

    def _anim_tick(self):
        if self._display_pct == self._target_pct:
            return
        diff = self._target_pct - self._display_pct
        if diff > 0:
            step = max(1, diff // 6)
            self._display_pct = min(self._target_pct,
                                    self._display_pct + step)
        else:
            self._display_pct = self._target_pct
        self.bar.setValue(self._display_pct)
        self.pct_label.setText(f"{self._display_pct}%")

    # ------------------------------------------------------------------ #
    def _on_done(self, success, error):
        self._flush_logs()
        self._installed = success
        if success:
            self._target_pct = 100

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
                if getattr(self.state, "work_dir_cleaned", False):
                    self._append_line_safe(
                        self.i18n.t("page.progress.aborted_cleaned")
                    )
                else:
                    wd = self.state.work_dir
                    self._append_line_safe(
                        self.i18n.t("page.progress.aborted_kept", dir=str(wd))
                    )
                # 中止后自动关窗口
                QTimer.singleShot(400, lambda: self.window().reject())
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
        # eta_hint 不在这设置（随阶段动态变化）