"""向导页基类。"""

from PySide6.QtWidgets import QWidget


class BasePage(QWidget):
    """
    向导页基类。

    子类可覆盖：
        on_enter()      进入本页时调用
        on_leave()      离开本页时调用；返回 False 阻止离开
        can_next()      返回 False → "下一步"按钮禁用
        on_cancel()     用户点"取消/中止"时调用（比如终止后台任务）
        retranslate()   语言切换时刷新文字

    类属性（用于向导判断）：
        is_progress     标记进度页（隐藏"上一步/下一步"，把"取消"改为"中止"）
        is_last         标记结束页（显示"完成"，隐藏其他按钮）
    """

    is_progress = False
    is_last = False

    def __init__(self, i18n, state, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.state = state

    # ---- 生命周期钩子（子类按需覆盖） ----
    def on_enter(self):
        pass

    def on_leave(self):
        return True

    def can_next(self):
        return True

    def on_cancel(self):
        pass

    def retranslate(self):
        pass