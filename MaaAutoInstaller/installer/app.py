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
    """
    判断是否以卸载器身份运行。
    PyInstaller onefile 下 sys.executable 就是 exe 本身的原始路径。
    源码运行时 sys.executable 是 python.exe，不会误触发。
    """
    try:
        exe = Path(sys.executable).stem.lower()
    except Exception:
        return False
    # uninstall.exe / uninstall (1).exe / Uninstall.exe 都算
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

    # 窗口图标
    icon_path = resource_path("resources/icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # i18n
    i18n = I18n(resource_path("installer/i18n"))
    lang = detect_system_language()
    if not i18n.load(lang):
        i18n.load("zh_CN")

    # 卸载模式
    if _is_uninstall_mode():
        LOG.info("检测到卸载模式 (exe 名: %s)", os.path.basename(sys.executable))
        from installer.uninstall_mode import run_uninstall_gui
        return run_uninstall_gui(i18n)

    # 正常安装向导
    wizard = Wizard(i18n)
    wizard.show()

    rc = app.exec()
    LOG.info("MaaAuto Installer 退出 (code=%d)", rc)
    return rc


