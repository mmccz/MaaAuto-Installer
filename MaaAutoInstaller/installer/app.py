"""安装器 QApplication 入口。"""

import os
import sys
import ctypes
import logging

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from installer.i18n import I18n
from installer.wizard import Wizard
from pathlib import Path

LOG = logging.getLogger("MaaAutoInstaller")


# --------------------------------------------------------------------------- #
# 主题调色板
# --------------------------------------------------------------------------- #
LIGHT_PALETTE = {
    "bg":           "#F7F8FA",
    "surface":      "#FFFFFF",
    "border":       "#E5E7EB",
    "border_in":    "#D1D5DB",
    "border_hover": "#9CA3AF",
    "hover":        "#F3F4F6",
    "pressed":      "#E5E7EB",
    "text":         "#111827",
    "text_sub":     "#6B7280",
    "text_hint":    "#9CA3AF",
    "text_field":   "#374151",
    "primary":      "#2563EB",
    "primary_h":    "#1D4ED8",
    "primary_p":    "#1E40AF",
    "primary_d":    "#BFDBFE",
    "input_bg":     "#FFFFFF",
    "input_focus":  "#2563EB",
    "bar_bg":       "#E5E7EB",
    "bar_1":        "#60A5FA",
    "bar_2":        "#2563EB",
    "log_bg":       "#0F172A",
    "log_fg":       "#CBD5E1",
    "log_border":   "#1E293B",
    "scroll":       "#CBD5E1",
    "scroll_h":     "#94A3B8",
    "selection_bg": "#BFDBFE",
    "selection_fg": "#1E3A8A",
}

DARK_PALETTE = {
    "bg":           "#1A1D21",
    "surface":      "#23262B",
    "border":       "#343A40",
    "border_in":    "#3F454D",
    "border_hover": "#6B7280",
    "hover":        "#2E3339",
    "pressed":      "#3A4048",
    "text":         "#F3F4F6",
    "text_sub":     "#9CA3AF",
    "text_hint":    "#6B7280",
    "text_field":   "#D1D5DB",
    "primary":      "#3B82F6",
    "primary_h":    "#2563EB",
    "primary_p":    "#1D4ED8",
    "primary_d":    "#1E3A8A",
    "input_bg":     "#2A2E34",
    "input_focus":  "#3B82F6",
    "bar_bg":       "#2E3339",
    "bar_1":        "#60A5FA",
    "bar_2":        "#3B82F6",
    "log_bg":       "#0F172A",
    "log_fg":       "#CBD5E1",
    "log_border":   "#1E293B",
    "scroll":       "#4B5563",
    "scroll_h":     "#6B7280",
    "selection_bg": "#1E40AF",
    "selection_fg": "#FFFFFF",
}


# --------------------------------------------------------------------------- #
# QSS 模板（用 @key@ 占位，由 build_qss 替换）
# --------------------------------------------------------------------------- #
_QSS_TEMPLATE = """
/* ===== 全局 ===== */
QDialog { background: @bg@; }
QWidget {
    font-family: "Segoe UI", "Microsoft YaHei UI", "PingFang SC", sans-serif;
    font-size: 13px;
}
QLabel {
    color: @text@;
    background: transparent;
}

/* ===== 顶栏 ===== */
QWidget#WizardHeader { background: @surface@; }
QLabel#WizardTitle  { font-size: 17px; font-weight: 600; color: @text@; }
QLabel#WizardStepLabel { font-size: 12px; color: @text_hint@; }

/* ===== 分隔线 ===== */
QFrame#WizardLine { background: @border@; border: none; }

/* ===== 底栏 ===== */
QWidget#WizardFooter { background: @surface@; }

/* ===== 主按钮 ===== */
QPushButton#WizardBtnPrimary {
    background: @primary@;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 9px 22px;
    font-size: 13px;
    font-weight: 500;
    min-width: 88px;
}
QPushButton#WizardBtnPrimary:hover   { background: @primary_h@; }
QPushButton#WizardBtnPrimary:pressed { background: @primary_p@; }
QPushButton#WizardBtnPrimary:disabled{ background: @primary_d@; color: #F0F9FF; }

/* ===== 次按钮 ===== */
QPushButton#WizardBtnSecondary {
    background: @surface@;
    color: @text_field@;
    border: 1px solid @border_in@;
    border-radius: 6px;
    padding: 9px 20px;
    font-size: 13px;
    min-width: 72px;
}
QPushButton#WizardBtnSecondary:hover   { background: @hover@; border-color: @border_hover@; }
QPushButton#WizardBtnSecondary:pressed { background: @pressed@; }
QPushButton#WizardBtnSecondary:disabled{
    color: @text_hint@; background: @bg@; border-color: @border@;
}

/* ===== 页面文字 ===== */
QLabel#PageHeading  { font-size: 20px; font-weight: 600; color: @text@; }
QLabel#PageSubtitle { font-size: 13px; color: @text_sub@; }
QLabel#PageBody     { font-size: 13px; color: @text_field@; }
QLabel#PageHint     { font-size: 12px; color: @text_hint@; }
QLabel#PageStage    { font-size: 13px; font-weight: 500; color: @text@; }
QLabel#PagePct      { font-size: 13px; font-weight: 600; color: @primary@; }
QLabel#PageFieldLabel { font-size: 13px; font-weight: 500; color: @text@; }
QLabel#PagePreview  { font-size: 12px; font-weight: 500; color: @primary@; padding: 2px 0; min-height: 16px; }

/* ===== 进度条 ===== */
QProgressBar#MainProgress {
    background: @bar_bg@;
    border: none;
    border-radius: 5px;
    height: 10px;
}
QProgressBar#MainProgress::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 @bar_1@, stop:1 @bar_2@);
    border-radius: 5px;
}

/* ===== 输入框 ===== */
QLineEdit {
    background: @input_bg@;
    border: 1px solid @border_in@;
    border-radius: 6px;
    padding: 8px 10px;
    font-size: 13px;
    color: @text@;
    selection-background-color: @selection_bg@;
    selection-color: @selection_fg@;
}
QLineEdit:focus { border-color: @input_focus@; }

/* ===== 下拉框 ===== */
QComboBox {
    background: @input_bg@;
    border: 1px solid @border_in@;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    color: @text@;
    min-height: 20px;
}
QComboBox:hover { border-color: @border_hover@; }
QComboBox:focus { border-color: @input_focus@; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    border: 1px solid @border_in@;
    background: @input_bg@;
    color: @text@;
    selection-background-color: @selection_bg@;
    selection-color: @selection_fg@;
    outline: none;
    padding: 4px;
}

/* ===== 复选框 ===== */
QCheckBox {
    font-size: 13px;
    color: @text_field@;
    spacing: 8px;
    padding: 3px 0;
    background: transparent;
}
QCheckBox:hover { color: @text@; }

/* ===== 日志区 ===== */
QTextEdit#WizardLog {
    background: @log_bg@;
    color: @log_fg@;
    border: 1px solid @log_border@;
    border-radius: 8px;
    font-family: "Cascadia Mono", "Consolas", "Courier New", monospace;
    font-size: 12px;
    padding: 10px;
    selection-background-color: @selection_bg@;
    selection-color: @selection_fg@;
}

/* ===== 滚动条 ===== */
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


# --------------------------------------------------------------------------- #
# 系统深浅色探测
# --------------------------------------------------------------------------- #
def detect_dark_mode() -> bool:
    """读注册表 AppsUseLightTheme（1=浅色，0=深色）。非 Windows 默认浅色。"""
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


# --------------------------------------------------------------------------- #
# 路径
# --------------------------------------------------------------------------- #
def resource_path(relative: str) -> str:
    """PyInstaller 兼容的资源路径。"""
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        base = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(base, relative)


# --------------------------------------------------------------------------- #
# DPI
# --------------------------------------------------------------------------- #
def set_dpi_awareness():
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
        return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# 语言探测
# --------------------------------------------------------------------------- #
def detect_system_language() -> str:
    try:
        lid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        if lid in (0x0804, 0x0404, 0x0C04, 0x1004, 0x1404):
            return "zh_CN"
        return "en_US"
    except Exception:
        return "zh_CN"


# --------------------------------------------------------------------------- #
# 日志
# --------------------------------------------------------------------------- #
def setup_logging(debug: bool):
    fmt = "%(asctime)s - %(levelname)s - %(message)s"
    if debug:
        logging.basicConfig(level=logging.DEBUG, format=fmt)
    else:
        logging.basicConfig(level=logging.INFO, format=fmt,
                            handlers=[logging.NullHandler()])


# --------------------------------------------------------------------------- #
# 卸载模式判断
# --------------------------------------------------------------------------- #
def _is_uninstall_mode() -> bool:
    try:
        exe = Path(sys.executable).stem.lower()
    except Exception:
        return False
    return exe.startswith("uninstall")


# --------------------------------------------------------------------------- #
# 主入口
# --------------------------------------------------------------------------- #
def run(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)

    debug = "--debug" in argv
    if debug:
        argv.remove("--debug")

    setup_logging(debug)
    LOG.info("MaaAuto Installer 启动")

    set_dpi_awareness()
    app = QApplication(argv)
    app.setApplicationName("MaaAuto Setup")
    app.setOrganizationName("MaaAuto")
    app.setQuitOnLastWindowClosed(True)

    # 根据系统深浅色选择 QSS
    dark = detect_dark_mode()
    LOG.info("系统深浅色: %s", "dark" if dark else "light")
    app.setStyleSheet(build_qss(DARK_PALETTE if dark else LIGHT_PALETTE))

    # 窗口图标
    icon_path = resource_path("resources/icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # i18n
    i18n = I18n(resource_path("installer/i18n"))
    lang = detect_system_language()
    if not i18n.load(lang):
        i18n.load("zh_CN")

    # 卸载模式（独立 stub 自带 main()，一般不会走到这里）
    if _is_uninstall_mode():
        LOG.info("检测到卸载模式 (exe 名: %s)", os.path.basename(sys.executable))
        try:
            from installer.uninstall_mode import run_uninstall_gui
            return run_uninstall_gui(i18n)
        except ImportError:
            LOG.warning("未找到 uninstall_mode 模块，按普通安装流程继续")

    # 正常安装向导
    wizard = Wizard(i18n)
    wizard.show()

    rc = app.exec()
    LOG.info("MaaAuto Installer 退出 (code=%d)", rc)
    return rc