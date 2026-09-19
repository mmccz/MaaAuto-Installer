"""第 5 步：完成。"""

import os
import subprocess
from pathlib import Path

from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QWidget, QMessageBox)
from PySide6.QtCore import Qt

from installer.pages.base import BasePage


class FinishPage(BasePage):

    is_last = True

    def __init__(self, i18n, state, parent=None):
        super().__init__(i18n, state, parent)
        self._launched = False
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(14)

        self.title = QLabel(self.i18n.t("page.finish.title"))
        self.title.setObjectName("PageHeading")
        root.addWidget(self.title)

        self.desc = QLabel(self.i18n.t("page.finish.desc"))
        self.desc.setObjectName("PageSubtitle")
        root.addWidget(self.desc)

        root.addSpacing(16)

        self.success_label = QLabel(self.i18n.t("page.finish.success"))
        self.success_label.setObjectName("PageBody")
        self.success_label.setWordWrap(True)
        root.addWidget(self.success_label)

        self.hint = QLabel(self.i18n.t("page.finish.hint"))
        self.hint.setObjectName("PageHint")
        self.hint.setWordWrap(True)
        root.addWidget(self.hint)

        root.addStretch()

        btns = QHBoxLayout()
        btns.setSpacing(10)

        self.btn_open = QPushButton(self.i18n.t("page.finish.open_dir"))
        self.btn_open.setObjectName("WizardBtnSecondary")
        self.btn_open.setCursor(Qt.PointingHandCursor)
        self.btn_open.clicked.connect(self._open_dir)
        btns.addWidget(self.btn_open)

        btns.addStretch()

        self.btn_launch = QPushButton(self.i18n.t("page.finish.launch"))
        self.btn_launch.setObjectName("WizardBtnPrimary")
        self.btn_launch.setCursor(Qt.PointingHandCursor)
        self.btn_launch.clicked.connect(self._launch)
        btns.addWidget(self.btn_launch)

        root.addLayout(btns)

    # ------------------------------------------------------------------ #
    def _open_dir(self):
        try:
            os.startfile(str(self.state.install_dir))
        except Exception as e:
            QMessageBox.warning(self, self.i18n.t("common.warning"),
                                self.i18n.t("page.finish.open_dir.failed", error=str(e)))

    def _launch(self):
        if self._launched:
            return
        try:
            launcher = Path(self.state.install_dir) / "MaaAuto.exe"
            if not launcher.exists():
                raise FileNotFoundError(f"未找到: {launcher}")
            subprocess.Popen([str(launcher)], cwd=str(self.state.install_dir))
            self._launched = True
            self.btn_launch.setEnabled(False)
        except Exception as e:
            QMessageBox.warning(self, self.i18n.t("common.warning"), str(e))

    def retranslate(self):
        self.title.setText(self.i18n.t("page.finish.title"))
        self.desc.setText(self.i18n.t("page.finish.desc"))
        self.success_label.setText(self.i18n.t("page.finish.success"))
        self.hint.setText(self.i18n.t("page.finish.hint"))
        self.btn_open.setText(self.i18n.t("page.finish.open_dir"))
        self.btn_launch.setText(self.i18n.t("page.finish.launch"))