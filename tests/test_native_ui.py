"""升级器 UI 的「不许再把 PySide6 拖回来」回归测试。

背景：upgrade.exe 曾经自带整套 PySide6，体积 43 MB，而它只需要一个
进度条窗口。改成 ctypes/Win32 后降到 7.5 MB。这个测试守住这条线：

* upgrade_stub / native_ui 的源码里不能出现 PySide6/PyQt/tkinter；
* native_ui 必须能在没有 GUI 框架的环境里 import（只用 ctypes）；
* 窗口类的关键接口（post_stage / post_progress / is_cancelled / run）存在。
"""

import os
import re
import sys

import pytest

from installer.core import native_ui

APP_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "MaaAutoInstaller")
STUB = os.path.join(APP_DIR, "tools", "upgrade_stub.py")
NATIVE = os.path.join(APP_DIR, "installer", "core", "native_ui.py")


@pytest.mark.parametrize("path", [STUB, NATIVE])
@pytest.mark.parametrize("forbidden", ["PySide6", "PyQt5", "PyQt6", "tkinter"])
def test_no_gui_toolkit_imports(path, forbidden):
    """只查真正的 import 语句：注释里说「不依赖 PySide6」是允许的。"""
    pattern = re.compile(rf"^\s*(?:import|from)\s+{forbidden}\b", re.MULTILINE)
    source = open(path, encoding="utf-8").read()
    assert not pattern.search(source), \
        f"{os.path.basename(path)} 又 import 了 {forbidden}"


def test_native_ui_has_no_qt_source():
    source = open(NATIVE, encoding="utf-8").read()
    assert "import PySide6" not in source
    assert "from PySide6" not in source


def test_window_api_surface():
    cls = native_ui.NativeProgressWindow
    for method in ("run", "post_stage", "post_progress", "post_message",
                   "is_cancelled", "_handle_message"):
        assert hasattr(cls, method), f"缺少方法 {method}"


def test_message_constants_are_distinct():
    used = [native_ui.WM_APP_STAGE, native_ui.WM_APP_PROGRESS,
            native_ui.WM_APP_MESSAGE, native_ui.WM_APP_DONE]
    assert len(set(used)) == len(used)
    assert all(m > native_ui.WM_APP for m in used)


def test_struct_sizes_match_win64():
    """结构体布局必须与 64 位 Windows 对齐，否则消息参数会被截断。"""
    import ctypes

    assert ctypes.sizeof(native_ui.POINT) == 8
    assert ctypes.sizeof(native_ui.RECT) == 16
    if sys.maxsize > 2 ** 32:
        assert ctypes.sizeof(native_ui.MSG) == 48
        assert ctypes.sizeof(native_ui.WPARAM) == 8
