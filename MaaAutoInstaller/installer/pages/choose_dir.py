"""第 2 步：选择安装目录。"""

import os
from pathlib import Path

from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QFileDialog, QMessageBox)
from PySide6.QtCore import Qt

from installer.pages.base import BasePage


# --------------------------------------------------------------------------- #
# 路径工具
# --------------------------------------------------------------------------- #
def _default_install_dir() -> Path:
    """默认返回 <可用盘>:\\MaaAuto，优先 D、E、C。"""
    for letter in ("D", "E", "C"):
        drive = Path(f"{letter}:\\")
        if drive.exists():
            return Path(f"{letter}:\\MaaAuto")
    return Path.home() / "MaaAuto"


_FORBIDDEN_PREFIXES = (
    "c:/windows", "c:/program files", "c:/program files (x86)",
    "c:/programdata",
)


def _normalize_user_path(text: str) -> Path:
    """
    把用户输入规范化为安装路径。

    规则：
      "E:"     → "E:\\MaaAuto"
      "E:/"    → "E:\\MaaAuto"
      "E:\\\\"   → "E:\\MaaAuto"
      "E:/foo" → "E:\\foo"
      "foo"    → 原样（后面会让用户确认）
    """
    text = text.strip().strip('"').strip("'")
    if not text:
        return Path("")

    # "E:" → "E:\"
    if len(text) == 2 and text[1] == ":":
        text = text + "\\"

    p = Path(text)

    # 盘根 → 补 MaaAuto 子目录
    try:
        parts = p.parts
        if len(parts) == 1 and parts[0].endswith((":\\", ":/")):
            p = p / "MaaAuto"
    except Exception:
        pass

    return p


# --------------------------------------------------------------------------- #
# 页面
# --------------------------------------------------------------------------- #
class ChooseDirPage(BasePage):

    def __init__(self, i18n, state, parent=None):
        super().__init__(i18n, state, parent)
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(14)

        self.title = QLabel(self.i18n.t("page.dir.title"))
        self.title.setObjectName("PageHeading")
        root.addWidget(self.title)

        self.desc = QLabel(self.i18n.t("page.dir.desc"))
        self.desc.setObjectName("PageSubtitle")
        root.addWidget(self.desc)

        root.addSpacing(12)

        self.dir_label = QLabel(self.i18n.t("page.dir.label"))
        self.dir_label.setObjectName("PageFieldLabel")
        root.addWidget(self.dir_label)

        # ---- 输入行：输入框 + 浏览 + 恢复默认 ----
        row = QHBoxLayout()
        row.setSpacing(8)

        self.path_edit = QLineEdit()
        self.path_edit.setText(str(self.state.install_dir or _default_install_dir()))
        self.path_edit.textChanged.connect(self._on_text_changed)
        self.path_edit.editingFinished.connect(self._on_editing_finished)  # ★ 失焦纠正
        row.addWidget(self.path_edit, 1)

        self.btn_browse = QPushButton(self.i18n.t("page.dir.browse"))
        self.btn_browse.setObjectName("WizardBtnSecondary")
        self.btn_browse.setCursor(Qt.PointingHandCursor)
        self.btn_browse.clicked.connect(self._on_browse)
        row.addWidget(self.btn_browse)

        self.btn_reset = QPushButton(self.i18n.t("page.dir.reset"))
        self.btn_reset.setObjectName("WizardBtnSecondary")
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.clicked.connect(self._on_reset)
        row.addWidget(self.btn_reset)

        root.addLayout(row)

        # ---- 实时预览 ----
        self.preview = QLabel("")
        self.preview.setObjectName("PagePreview")
        self.preview.setWordWrap(True)
        root.addWidget(self.preview)

        self.hint = QLabel(self.i18n.t("page.dir.default_hint"))
        self.hint.setObjectName("PageHint")
        self.hint.setWordWrap(True)
        root.addWidget(self.hint)

        root.addStretch()

        self._update_preview()

    # ------------------------------------------------------------------ #
    # 事件
    # ------------------------------------------------------------------ #
    def _on_text_changed(self, *_):
        self._update_preview()
        self._sync_state()
        w = self.window()
        if hasattr(w, "_update_buttons"):
            w._update_buttons()

    def _on_editing_finished(self):
        """失焦 / 回车：把输入框内容规范化后回写。"""
        text = self.path_edit.text().strip()
        if not text:
            return
        p = _normalize_user_path(text)
        s = str(p)
        if s != text:
            self.path_edit.setText(s)
            self.path_edit.setCursorPosition(len(s))

    def _on_reset(self):
        d = _default_install_dir()
        self.path_edit.setText(str(d))
        self.path_edit.setCursorPosition(len(str(d)))

    def _update_preview(self):
        text = self.path_edit.text().strip()
        if not text:
            self.preview.setText("")
            return
        try:
            p = _normalize_user_path(text)
            final = str(p)
            if final != text:
                self.preview.setText(
                    self.i18n.t("page.dir.preview.changed", final=final)
                )
            else:
                self.preview.setText("")
        except Exception:
            self.preview.setText("")

    def _on_browse(self):
        """用 Qt 非原生对话框，行为可控。"""
        current = self.path_edit.text().strip() or str(_default_install_dir())

        dlg = QFileDialog(self, self.i18n.t("page.dir.browse_title"), current)
        dlg.setFileMode(QFileDialog.Directory)
        dlg.setOption(QFileDialog.ShowDirsOnly, True)
        dlg.setOption(QFileDialog.DontUseNativeDialog, True)   # ★ 关键
        dlg.setOption(QFileDialog.DontResolveSymlinks, True)
        dlg.setLabelText(QFileDialog.LookIn,
                         self.i18n.t("page.dir.dialog.look_in"))
        dlg.setLabelText(QFileDialog.FileName,
                         self.i18n.t("page.dir.dialog.filename"))
        dlg.setLabelText(QFileDialog.FileType,
                         self.i18n.t("page.dir.dialog.filetype"))
        dlg.setLabelText(QFileDialog.Reject,
                         self.i18n.t("page.dir.dialog.reject"))
        dlg.setLabelText(QFileDialog.Accept,
                         self.i18n.t("page.dir.dialog.accept"))
        
        if dlg.exec() != QFileDialog.Accepted:
            return
        files = dlg.selectedFiles()
        if not files:
            return

        chosen = files[0]
        p = _normalize_user_path(chosen)
        s = str(p)
        self.path_edit.setText(s)
        self.path_edit.setCursorPosition(len(s))
        self.path_edit.setFocus()

    def _sync_state(self):
        text = self.path_edit.text().strip()
        self.state.install_dir = _normalize_user_path(text) if text else None

    # ------------------------------------------------------------------ #
    # 校验
    # ------------------------------------------------------------------ #
    def can_next(self) -> bool:
        text = self.path_edit.text().strip()
        if not text:
            return False
        try:
            p = _normalize_user_path(text).resolve()
        except Exception:
            return False
        p_str = str(p).lower().replace("\\", "/")
        for prefix in _FORBIDDEN_PREFIXES:
            if p_str.startswith(prefix):
                return False
        return True

    def on_leave(self):
        text = self.path_edit.text().strip()
        if not text:
            QMessageBox.warning(self, self.i18n.t("common.warning"),
                                self.i18n.t("page.dir.error.empty"))
            return False

        p = _normalize_user_path(text)
        if str(p) != text:
            self.path_edit.setText(str(p))

        try:
            p = p.resolve()
        except Exception:
            QMessageBox.warning(self, self.i18n.t("common.warning"),
                                self.i18n.t("page.dir.error.not_writable"))
            return False

        try:
            p.mkdir(parents=True, exist_ok=True)
            test_file = p / ".maaauto_write_test"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink()
        except Exception:
            QMessageBox.warning(self, self.i18n.t("common.warning"),
                                self.i18n.t("page.dir.error.not_writable"))
            return False

        self.state.install_dir = p
        return True

    def on_enter(self):
        if self.state.install_dir is None:
            default = _default_install_dir()
            self.state.install_dir = default
            self.path_edit.setText(str(default))
        else:
            self.path_edit.setText(str(self.state.install_dir))
        self.path_edit.setCursorPosition(len(self.path_edit.text()))
        self._update_preview()

    def retranslate(self):
        self.title.setText(self.i18n.t("page.dir.title"))
        self.desc.setText(self.i18n.t("page.dir.desc"))
        self.dir_label.setText(self.i18n.t("page.dir.label"))
        self.btn_browse.setText(self.i18n.t("page.dir.browse"))
        self.btn_reset.setText(self.i18n.t("page.dir.reset"))
        self.hint.setText(self.i18n.t("page.dir.default_hint"))
        self._update_preview()