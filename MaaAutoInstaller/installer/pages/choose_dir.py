"""第 2 步：选择安装目录。"""

import os
from pathlib import Path

from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QFileDialog, QWidget, QMessageBox)
from PySide6.QtCore import Qt

from installer.pages.base import BasePage


def _default_install_dir() -> Path:
    for letter in ("D", "E", "C"):
        drive = Path(f"{letter}:/")
        if drive.exists():
            return drive / "MaaAuto"
    return Path.home() / "MaaAuto"


# 系统保护目录（拒绝安装）
_FORBIDDEN_PREFIXES = (
    "c:/windows", "c:/program files", "c:/program files (x86)",
    "c:/programdata",
)


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
        root.addWidget(self.dir_label)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.path_edit = QLineEdit()
        self.path_edit.setText(str(self.state.install_dir or _default_install_dir()))
        self.path_edit.textChanged.connect(self._on_text_changed)
        row.addWidget(self.path_edit, 1)

        self.btn_browse = QPushButton(self.i18n.t("page.dir.browse"))
        self.btn_browse.setCursor(Qt.PointingHandCursor)
        self.btn_browse.clicked.connect(self._on_browse)
        row.addWidget(self.btn_browse)
        root.addLayout(row)

        self.hint = QLabel(self.i18n.t("page.dir.default_hint"))
        self.hint.setObjectName("PageHint")
        self.hint.setWordWrap(True)
        root.addWidget(self.hint)

        root.addStretch()

    # ------------------------------------------------------------------ #
    def _on_text_changed(self, *_):
        self._sync_state()
        # 更新下一步按钮
        w = self.window()
        if hasattr(w, "_update_buttons"):
            w._update_buttons()

    def _on_browse(self):
        d = QFileDialog.getExistingDirectory(
            self, self.i18n.t("page.dir.title"),
            self.path_edit.text() or str(_default_install_dir()),
        )
        if d:
            self.path_edit.setText(d)

    def _sync_state(self):
        text = self.path_edit.text().strip()
        self.state.install_dir = Path(text) if text else None

    # ------------------------------------------------------------------ #
    def can_next(self) -> bool:
        text = self.path_edit.text().strip()
        if not text:
            return False
        try:
            p = Path(text).resolve()
        except Exception:
            return False
        p_str = str(p).lower().replace("\\", "/")
        # 拒绝系统目录
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
        p = Path(text).resolve()

        # 检查父目录存在 & 可写
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
        # 同步一下
        if self.state.install_dir is None:
            self.path_edit.setText(str(_default_install_dir()))
        else:
            self.path_edit.setText(str(self.state.install_dir))

    def retranslate(self):
        self.title.setText(self.i18n.t("page.dir.title"))
        self.desc.setText(self.i18n.t("page.dir.desc"))
        self.dir_label.setText(self.i18n.t("page.dir.label"))
        self.btn_browse.setText(self.i18n.t("page.dir.browse"))
        self.hint.setText(self.i18n.t("page.dir.default_hint"))