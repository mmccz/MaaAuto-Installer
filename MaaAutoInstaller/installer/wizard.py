"""向导主窗口：5 步流程。"""

import logging

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QStackedWidget, QPushButton, QWidget, QFrame,
                               QMessageBox)
from PySide6.QtCore import Qt

from installer.state import InstallState
from installer.pages.base import BasePage


LOG = logging.getLogger("MaaAutoInstaller")


class Wizard(QDialog):
    """
    安装向导主窗口。

    页面结构：
        0  欢迎
        1  选择目录
        2  选项
        3  进度
        4  完成
    """

    def __init__(self, i18n, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.state = InstallState()
        self._pages = []
        self._index = 0

        self.setWindowTitle(i18n.t("wizard.title"))
        self.setMinimumSize(640, 480)
        self.resize(700, 520)

        self._setup_ui()
        self._build_pages()
        self._show_page(0)

    # ------------------------------------------------------------------ #
    # UI 骨架
    # ------------------------------------------------------------------ #
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- 顶部标题栏 ----
        header = QWidget()
        header.setObjectName("WizardHeader")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(24, 18, 24, 14)
        hl.setSpacing(12)

        self.lbl_title = QLabel(self.i18n.t("wizard.title"))
        self.lbl_title.setObjectName("WizardTitle")
        hl.addWidget(self.lbl_title)
        hl.addStretch()

        self.lbl_step = QLabel("")
        self.lbl_step.setObjectName("WizardStepLabel")
        hl.addWidget(self.lbl_step)

        root.addWidget(header)

        line = QFrame()
        line.setObjectName("WizardLine")
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        root.addWidget(line)

        # ---- 中间内容 ----
        self.stack = QStackedWidget()
        self.stack.setObjectName("WizardStack")
        root.addWidget(self.stack, 1)

        line2 = QFrame()
        line2.setObjectName("WizardLine")
        line2.setFrameShape(QFrame.HLine)
        line2.setFixedHeight(1)
        root.addWidget(line2)

        # ---- 底部按钮栏 ----
        footer = QWidget()
        footer.setObjectName("WizardFooter")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(24, 14, 24, 14)
        fl.setSpacing(10)

        self.btn_cancel = QPushButton(self.i18n.t("wizard.cancel"))
        self.btn_cancel.setObjectName("WizardBtnSecondary")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self._on_cancel)

        self.btn_back = QPushButton(self.i18n.t("wizard.back"))
        self.btn_back.setObjectName("WizardBtnSecondary")
        self.btn_back.setCursor(Qt.PointingHandCursor)
        self.btn_back.clicked.connect(self._on_back)

        self.btn_next = QPushButton(self.i18n.t("wizard.next"))
        self.btn_next.setObjectName("WizardBtnPrimary")
        self.btn_next.setCursor(Qt.PointingHandCursor)
        self.btn_next.clicked.connect(self._on_next)

        self.btn_finish = QPushButton(self.i18n.t("wizard.finish"))
        self.btn_finish.setObjectName("WizardBtnPrimary")
        self.btn_finish.setCursor(Qt.PointingHandCursor)
        self.btn_finish.clicked.connect(self._on_finish)

        fl.addWidget(self.btn_cancel)
        fl.addStretch()
        fl.addWidget(self.btn_back)
        fl.addWidget(self.btn_next)
        fl.addWidget(self.btn_finish)
        root.addWidget(footer)

    # ------------------------------------------------------------------ #
    # 页面构建
    # ------------------------------------------------------------------ #
    def _build_pages(self):
        classes = self._import_pages()
        if classes is None:
            # 批次 4 之前用占位页兜底
            LOG.warning("installer.pages 尚未提供完整页面，使用占位页。")
            titles = ("page.welcome.title", "page.dir.title",
                      "page.options.title", "page.progress.title",
                      "page.finish.title")
            for tk in titles:
                p = _PlaceholderPage(self.i18n, self.state,
                                     self.i18n.t(tk))
                self._pages.append(p)
                self.stack.addWidget(p)
        else:
            for cls in classes:
                p = cls(self.i18n, self.state)
                self._pages.append(p)
                self.stack.addWidget(p)

    def _import_pages(self):
        try:
            from installer.pages.welcome import WelcomePage
            from installer.pages.choose_dir import ChooseDirPage
            from installer.pages.options import OptionsPage
            from installer.pages.progress import ProgressPage
            from installer.pages.finish import FinishPage
            return [WelcomePage, ChooseDirPage, OptionsPage,
                    ProgressPage, FinishPage]
        except ImportError as e:
            LOG.warning("导入页面失败: %s", e)
            return None

    # ------------------------------------------------------------------ #
    # 页面切换
    # ------------------------------------------------------------------ #
    def _show_page(self, index):
        if index < 0 or index >= len(self._pages):
            return
        self._index = index
        page = self._pages[index]
        self.stack.setCurrentWidget(page)
        self._update_step_label()
        self._update_buttons()
        try:
            page.on_enter()
        except Exception as e:
            LOG.exception("on_enter 异常: %s", e)

    def _update_step_label(self):
        cur = self._pages[self._index]
        if getattr(cur, "is_last", False) or getattr(cur, "is_progress", False):
            self.lbl_step.setText("")
            return
        total = len(self._pages)
        n = self._index + 1
        self.lbl_step.setText(self.i18n.t("wizard.step", n=n, total=total))

    def _update_buttons(self):
        if not self._pages:
            return
        page = self._pages[self._index]
        is_progress = getattr(page, "is_progress", False)
        is_last = getattr(page, "is_last", False)

        self.btn_cancel.setVisible(not is_last)
        self.btn_back.setVisible((not is_progress) and (not is_last)
                                 and self._index > 0)
        self.btn_next.setVisible((not is_progress) and (not is_last))
        self.btn_finish.setVisible(is_last)

        if is_progress:
            self.btn_cancel.setText(self.i18n.t("wizard.abort"))
        else:
            self.btn_cancel.setText(self.i18n.t("wizard.cancel"))

        if not is_progress and not is_last:
            try:
                can = page.can_next()
            except Exception:
                can = True
            self.btn_next.setEnabled(bool(can))

    # ------------------------------------------------------------------ #
    # 按钮事件
    # ------------------------------------------------------------------ #
    def _on_next(self):
        page = self._pages[self._index]
        try:
            if not page.can_next():
                return
        except Exception:
            pass

        try:
            if page.on_leave() is False:
                return
        except Exception as e:
            LOG.exception("on_leave 异常: %s", e)

        if self._index < len(self._pages) - 1:
            self._show_page(self._index + 1)

    def _on_back(self):
        if self._index > 0:
            self._show_page(self._index - 1)

    def _on_cancel(self):
        page = self._pages[self._index]
        try:
            page.on_cancel()
        except Exception:
            LOG.exception("on_cancel 异常")
        self.reject()

    def _on_finish(self):
        self.accept()

    # ------------------------------------------------------------------ #
    # 关闭事件（用户点 X）
    # ------------------------------------------------------------------ #
    def closeEvent(self, event):
        # 进度页：走中止逻辑
        if self._index < len(self._pages):
            page = self._pages[self._index]
            if getattr(page, "is_progress", False):
                self._on_cancel()
                event.accept()
                return

        reply = QMessageBox.question(
            self,
            self.i18n.t("wizard.cancel.confirm.title"),
            self.i18n.t("wizard.cancel.confirm.msg"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()

    # ------------------------------------------------------------------ #
    # 语言切换
    # ------------------------------------------------------------------ #
    def set_language(self, lang_code):
        """供欢迎页切换语言时调用。"""
        if not self.i18n.load(lang_code):
            return
        self.retranslate()
        for p in self._pages:
            try:
                p.retranslate()
            except Exception:
                LOG.exception("retranslate 异常")
        self._update_step_label()
        self._update_buttons()

    def retranslate(self):
        self.setWindowTitle(self.i18n.t("wizard.title"))
        self.lbl_title.setText(self.i18n.t("wizard.title"))
        self.btn_back.setText(self.i18n.t("wizard.back"))
        self.btn_next.setText(self.i18n.t("wizard.next"))
        self.btn_finish.setText(self.i18n.t("wizard.finish"))
        # btn_cancel 由 _update_buttons 决定文字


# --------------------------------------------------------------------------- #
# 占位页（批次 4 用真页面替换）
# --------------------------------------------------------------------------- #
class _PlaceholderPage(BasePage):
    def __init__(self, i18n, state, title):
        super().__init__(i18n, state)
        from PySide6.QtWidgets import QVBoxLayout
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 32, 32, 32)
        lbl = QLabel(f"<h2>{title}</h2><p>(not yet implemented)</p>")
        lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(lbl)