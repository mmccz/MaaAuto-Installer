"""第 3 步：安装选项。（新方案：不再让用户选 Python 环境）"""

from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                               QCheckBox, QFrame)
from PySide6.QtCore import Qt

from installer.pages.base import BasePage


class OptionsPage(BasePage):

    def __init__(self, i18n, state, parent=None):
        super().__init__(i18n, state, parent)
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(14)

        self.title = QLabel(self.i18n.t("page.options.title"))
        self.title.setObjectName("PageHeading")
        root.addWidget(self.title)

        self.desc = QLabel(self.i18n.t("page.options.desc"))
        self.desc.setObjectName("PageSubtitle")
        root.addWidget(self.desc)

        root.addSpacing(12)

        # ---- 下载源 ----
        row_mirror = QHBoxLayout()
        row_mirror.setSpacing(10)
        self.lbl_mirror = QLabel(self.i18n.t("page.options.mirror"))
        self.lbl_mirror.setFixedWidth(120)
        row_mirror.addWidget(self.lbl_mirror)

        self.mirror_combo = QComboBox()
        self._mirror_items = [
            ("auto",   "page.options.mirror.auto"),
            ("tuna",   "page.options.mirror.tuna"),
            ("aliyun", "page.options.mirror.aliyun"),
            ("ustc",   "page.options.mirror.ustc"),
            ("pypi",   "page.options.mirror.pypi"),
        ]
        for data, key in self._mirror_items:
            self.mirror_combo.addItem(self.i18n.t(key), data)
        self.mirror_combo.currentIndexChanged.connect(self._on_changed)
        row_mirror.addWidget(self.mirror_combo, 1)
        root.addLayout(row_mirror)

        # ---- 分隔线 ----
        line = QFrame()
        line.setObjectName("WizardLine")
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        root.addWidget(line)

        # ---- 开关 ----
        self.chk_desktop = QCheckBox(self.i18n.t("page.options.shortcut.desktop"))
        self.chk_desktop.setChecked(True)
        self.chk_desktop.toggled.connect(self._on_changed)
        root.addWidget(self.chk_desktop)

        self.chk_startmenu = QCheckBox(self.i18n.t("page.options.shortcut.startmenu"))
        self.chk_startmenu.setChecked(True)
        self.chk_startmenu.toggled.connect(self._on_changed)
        root.addWidget(self.chk_startmenu)

        self.chk_cleanup = QCheckBox(self.i18n.t("page.options.cleanup"))
        self.chk_cleanup.setChecked(True)
        self.chk_cleanup.toggled.connect(self._on_changed)
        root.addWidget(self.chk_cleanup)

        self.chk_launch = QCheckBox(self.i18n.t("page.options.launch"))
        self.chk_launch.setChecked(True)
        self.chk_launch.toggled.connect(self._on_changed)
        root.addWidget(self.chk_launch)

        root.addStretch()

    # ------------------------------------------------------------------ #
    def _on_changed(self, *_):
        self._sync_state()
        w = self.window()
        if hasattr(w, "_update_buttons"):
            w._update_buttons()

    def _sync_state(self):
        self.state.mirror = self.mirror_combo.currentData() or "auto"
        self.state.create_desktop_shortcut = self.chk_desktop.isChecked()
        self.state.create_startmenu_shortcut = self.chk_startmenu.isChecked()
        self.state.cleanup_after_install = self.chk_cleanup.isChecked()
        self.state.launch_after_install = self.chk_launch.isChecked()

    def on_enter(self):
        self._sync_state()

    def retranslate(self):
        self.title.setText(self.i18n.t("page.options.title"))
        self.desc.setText(self.i18n.t("page.options.desc"))
        self.lbl_mirror.setText(self.i18n.t("page.options.mirror"))

        self.mirror_combo.blockSignals(True)
        for i, (_data, key) in enumerate(self._mirror_items):
            if i < self.mirror_combo.count():
                self.mirror_combo.setItemText(i, self.i18n.t(key))
        self.mirror_combo.blockSignals(False)

        self.chk_desktop.setText(self.i18n.t("page.options.shortcut.desktop"))
        self.chk_startmenu.setText(self.i18n.t("page.options.shortcut.startmenu"))
        self.chk_cleanup.setText(self.i18n.t("page.options.cleanup"))
        self.chk_launch.setText(self.i18n.t("page.options.launch"))