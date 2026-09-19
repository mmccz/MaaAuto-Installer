"""第 1 步：欢迎 + 语言选择。"""

from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel,
                               QComboBox, QWidget, QSizePolicy)
from PySide6.QtCore import Qt

from installer.pages.base import BasePage


class WelcomePage(BasePage):

    def __init__(self, i18n, state, parent=None):
        super().__init__(i18n, state, parent)
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(14)

        self.title = QLabel(self.i18n.t("page.welcome.title"))
        self.title.setObjectName("PageHeading")
        root.addWidget(self.title)

        self.desc = QLabel(self.i18n.t("page.welcome.desc"))
        self.desc.setObjectName("PageSubtitle")
        root.addWidget(self.desc)

        root.addSpacing(8)

        self.intro = QLabel(self.i18n.t("page.welcome.intro"))
        self.intro.setObjectName("PageBody")
        self.intro.setWordWrap(True)
        self.intro.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root.addWidget(self.intro, 1)

        # 语言选择
        lang_row = QHBoxLayout()
        lang_row.setSpacing(10)
        self.lang_label = QLabel(self.i18n.t("page.welcome.lang_label"))
        self.lang_label.setObjectName("PageFieldLabel")
        lang_row.addWidget(self.lang_label)

        self.lang_combo = QComboBox()
        for code, display in self.i18n.available():
            self.lang_combo.addItem(display, code)
        idx = self.lang_combo.findData(self.i18n.current_lang)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        self.lang_combo.currentIndexChanged.connect(self._on_lang_changed)
        lang_row.addWidget(self.lang_combo)
        lang_row.addStretch()
        root.addLayout(lang_row)

    def _on_lang_changed(self):
        code = self.lang_combo.currentData()
        if not code:
            return
        w = self.window()
        if hasattr(w, "set_language"):
            w.set_language(code)

    def retranslate(self):
        self.title.setText(self.i18n.t("page.welcome.title"))
        self.desc.setText(self.i18n.t("page.welcome.desc"))
        self.intro.setText(self.i18n.t("page.welcome.intro"))
        self.lang_label.setText(self.i18n.t("page.welcome.lang_label"))
        self.lang_combo.blockSignals(True)
        for i, (_code, display) in enumerate(self.i18n.available()):
            if i < self.lang_combo.count():
                self.lang_combo.setItemText(i, display)
        self.lang_combo.blockSignals(False)