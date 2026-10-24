"""纯 ctypes/Win32 的升级进度窗 —— 不依赖 PySide6 / PyQt / tkinter。

为什么要自己写：

* ``upgrade.exe`` 只是安装包里顺带的一个小工具，PySide6 会把单文件 exe
  从 ~10 MB 撑到 40+ MB，用户下载 payload 时纯属浪费；
* 升级流程跑在工作线程，Win32 控件不是线程安全的。历史上在工作线程里
  直接 ``SetWindowTextW`` 更新进度，偶发 0xC0000005（访问冲突）崩溃。
  所以这里沿用了 Qt 信号那套思路：工作线程只往窗口线程 ``PostMessageW``
  投递通知，真正的控件操作全部在窗口过程（主线程的 ``GetMessageW``
  循环）里串行执行 —— 跨线程直接改 UI 是绝对不能碰的。

对外只暴露一个类 :class:`NativeProgressWindow`，它是纯 Win32 的，可以
脱离升级流程单独测试。
"""

import ctypes
import threading
from collections import deque
from ctypes import wintypes

# --------------------------------------------------------------------------- #
# Win32 常量 / 类型
# --------------------------------------------------------------------------- #
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_SETFONT = 0x0030
WM_COMMAND = 0x0111
WM_TIMER = 0x0113
WM_USER = 0x0400
WM_APP = 0x8000

# 自定义消息统一取 WM_APP+n（应用私有区间，不会和系统消息/控件通知冲突；
# 即任务里说的「WM_USER+n」私有消息，WM_APP 是官方推荐给应用自己的那一档）。
WM_APP_STAGE = WM_APP + 1       # 切换阶段文案
WM_APP_PROGRESS = WM_APP + 2    # 更新进度条
WM_APP_MESSAGE = WM_APP + 3     # 追加一行日志
WM_APP_DONE = WM_APP + 4        # 工作线程结束，携带返回码

WS_CHILD = 0x40000000
WS_VISIBLE = 0x10000000
WS_CLIPCHILDREN = 0x02000000
WS_CAPTION = 0x00C00000
WS_SYSMENU = 0x00080000
WS_MINIMIZEBOX = 0x00020000
WS_VSCROLL = 0x00200000
WS_EX_CLIENTEDGE = 0x00000200

ES_MULTILINE = 0x0004
ES_READONLY = 0x0800
ES_AUTOVSCROLL = 0x0040
EM_SETSEL = 0x00B1
EM_SCROLLCARET = 0x00B7

SS_LEFT = 0x00000000
BS_PUSHBUTTON = 0x00000000

SW_SHOW = 5
SW_SHOWNORMAL = 1
COLOR_WINDOW = 5
IDI_APPLICATION = 32512
DEFAULT_CHARSET = 1
CLEARTYPE_QUALITY = 5
FW_NORMAL = 400
FW_SEMIBOLD = 600

PBM_SETPOS = WM_USER + 2
PBM_SETRANGE32 = WM_USER + 6

SPI_GETWORKAREA = 0x0030
SM_CXSCREEN = 0
SM_CYSCREEN = 1
LOGPIXELSX = 88

ICC_PROGRESS_CLASS = 0x0020
ID_CANCEL = 1001
ID_TIMER_CLOSE = 1

LPARAM = ctypes.c_size_t      # 按无符号透传，避免指针最高位为 1 时溢出
WPARAM = ctypes.c_size_t
LRESULT = ctypes.c_ssize_t
HANDLE = ctypes.c_void_p


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", HANDLE),          # 真实类型是 WNDPROC，调用时另行转换
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", HANDLE),
        ("hIcon", HANDLE),
        ("hCursor", HANDLE),
        ("hbrBackground", HANDLE),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", HANDLE),
        ("message", wintypes.UINT),
        ("wParam", WPARAM),
        ("lParam", LPARAM),
        ("time", wintypes.DWORD),
        ("pt", POINT),
    ]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class INITCOMMONCONTROLSEX(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("dwICC", wintypes.DWORD)]


WNDPROC = ctypes.WINFUNCTYPE(LRESULT, HANDLE, wintypes.UINT, WPARAM, LPARAM)

# 句柄 → 实例。窗口过程是模块级的，靠 hwnd 找回实例。
_WINDOWS = {}
_WINDOWS_LOCK = threading.Lock()
_HINSTANCE = None
_CLASS_NAME = "MaaAutoUpgradeProgressWnd"
_CLASS_REGISTERED = False
_DPI_DONE = False


_USER32 = None
_KERNEL32 = None
_GDI32 = None
_COMCTL32 = None


def _user32():
    # 注意：WinDLL 每次调用都会返回新的对象，argtypes 不会跨对象保留，
    # 所以这里必须缓存单例 —— 否则后面拿到的函数又退回默认的 c_int 原型，
    # 64 位下 lParam 直接 OverflowError。
    global _USER32
    if _USER32 is None:
        _USER32 = ctypes.WinDLL("user32", use_last_error=True)
    return _USER32


def _kernel32():
    global _KERNEL32
    if _KERNEL32 is None:
        _KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
    return _KERNEL32


def _gdi32():
    global _GDI32
    if _GDI32 is None:
        _GDI32 = ctypes.WinDLL("gdi32", use_last_error=True)
    return _GDI32


def _comctl32():
    global _COMCTL32
    if _COMCTL32 is None:
        _COMCTL32 = ctypes.WinDLL("comctl32", use_last_error=True)
    return _COMCTL32


# --------------------------------------------------------------------------- #
# 原型声明（64 位下句柄/尺寸必须显式声明，否则默认 int 会截断指针）
# --------------------------------------------------------------------------- #
def _setup_prototypes():
    u = _user32()
    k = _kernel32()
    g = _gdi32()

    u.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
    u.RegisterClassW.restype = wintypes.WORD
    u.CreateWindowExW.argtypes = [
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        HANDLE, HANDLE, HANDLE, HANDLE,
    ]
    u.CreateWindowExW.restype = HANDLE
    u.DefWindowProcW.argtypes = [HANDLE, wintypes.UINT, WPARAM, LPARAM]
    u.DefWindowProcW.restype = LRESULT
    u.DestroyWindow.argtypes = [HANDLE]
    u.DestroyWindow.restype = wintypes.BOOL
    u.ShowWindow.argtypes = [HANDLE, ctypes.c_int]
    u.ShowWindow.restype = wintypes.BOOL
    u.UpdateWindow.argtypes = [HANDLE]
    u.UpdateWindow.restype = wintypes.BOOL
    u.SetForegroundWindow.argtypes = [HANDLE]
    u.SetForegroundWindow.restype = wintypes.BOOL
    u.SetWindowTextW.argtypes = [HANDLE, wintypes.LPCWSTR]
    u.SetWindowTextW.restype = wintypes.BOOL
    u.GetWindowTextLengthW.argtypes = [HANDLE]
    u.GetWindowTextLengthW.restype = ctypes.c_int
    u.SendMessageW.argtypes = [HANDLE, wintypes.UINT, WPARAM, LPARAM]
    u.SendMessageW.restype = LRESULT
    u.PostMessageW.argtypes = [HANDLE, wintypes.UINT, WPARAM, LPARAM]
    u.PostMessageW.restype = wintypes.BOOL
    u.GetMessageW.argtypes = [ctypes.POINTER(MSG), HANDLE, wintypes.UINT, wintypes.UINT]
    u.GetMessageW.restype = wintypes.BOOL       # 可能是 -1，故用 BOOL
    u.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
    u.TranslateMessage.restype = wintypes.BOOL
    u.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
    u.DispatchMessageW.restype = LRESULT
    u.PostQuitMessage.argtypes = [ctypes.c_int]
    u.PostQuitMessage.restype = None
    u.SetTimer.argtypes = [HANDLE, ctypes.c_size_t, wintypes.UINT, HANDLE]
    u.SetTimer.restype = ctypes.c_size_t
    u.KillTimer.argtypes = [HANDLE, ctypes.c_size_t]
    u.KillTimer.restype = wintypes.BOOL
    u.EnableWindow.argtypes = [HANDLE, wintypes.BOOL]
    u.EnableWindow.restype = wintypes.BOOL
    u.LoadIconW.argtypes = [HANDLE, HANDLE]
    u.LoadIconW.restype = HANDLE
    u.LoadCursorW.argtypes = [HANDLE, HANDLE]
    u.LoadCursorW.restype = HANDLE
    u.GetClientRect.argtypes = [HANDLE, ctypes.POINTER(RECT)]
    u.GetClientRect.restype = wintypes.BOOL
    u.MoveWindow.argtypes = [HANDLE, ctypes.c_int, ctypes.c_int,
                             ctypes.c_int, ctypes.c_int, wintypes.BOOL]
    u.MoveWindow.restype = wintypes.BOOL
    u.AdjustWindowRectEx.argtypes = [ctypes.POINTER(RECT), wintypes.DWORD,
                                     wintypes.BOOL, wintypes.DWORD]
    u.AdjustWindowRectEx.restype = wintypes.BOOL
    u.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT,
                                        ctypes.POINTER(RECT), wintypes.UINT]
    u.SystemParametersInfoW.restype = wintypes.BOOL
    u.GetSystemMetrics.argtypes = [ctypes.c_int]
    u.GetSystemMetrics.restype = ctypes.c_int
    u.GetDC.argtypes = [HANDLE]
    u.GetDC.restype = HANDLE
    u.ReleaseDC.argtypes = [HANDLE, HANDLE]
    u.ReleaseDC.restype = ctypes.c_int

    k.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    k.GetModuleHandleW.restype = HANDLE

    g.CreateFontW.argtypes = [
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
        wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
        wintypes.LPCWSTR,
    ]
    g.CreateFontW.restype = HANDLE
    g.DeleteObject.argtypes = [HANDLE]
    g.DeleteObject.restype = wintypes.BOOL
    g.GetDeviceCaps.argtypes = [HANDLE, ctypes.c_int]
    g.GetDeviceCaps.restype = ctypes.c_int


_setup_prototypes()


def _init_dpi_awareness() -> None:
    """开 DPI 感知，否则 125%/150% 缩放下字体被系统位图拉伸发虚。

    优先 Per-Monitor V2（Win10 1703+），失败退到系统级 shcore，再退到
    最老的 ``SetProcessDPIAware``。
    """
    global _DPI_DONE
    if _DPI_DONE:
        return
    _DPI_DONE = True
    u = _user32()
    try:
        fn = u.SetProcessDpiAwarenessContext
        fn.argtypes = [HANDLE]
        fn.restype = wintypes.BOOL
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 == (HANDLE)-4
        if fn(HANDLE(-4)):
            return
    except Exception:
        pass
    try:
        shcore = ctypes.WinDLL("shcore", use_last_error=True)
        shcore.SetProcessDpiAwareness.argtypes = [ctypes.c_int]
        shcore.SetProcessDpiAwareness.restype = ctypes.c_int
        if shcore.SetProcessDpiAwareness(2) == 0:
            return
    except Exception:
        pass
    try:
        u.SetProcessDPIAware.argtypes = []
        u.SetProcessDPIAware.restype = wintypes.BOOL
        u.SetProcessDPIAware()
    except Exception:
        pass


def _system_dpi() -> int:
    try:
        hdc = _user32().GetDC(None)
        if hdc:
            try:
                dpi = _gdi32().GetDeviceCaps(hdc, LOGPIXELSX)
            finally:
                _user32().ReleaseDC(None, hdc)
            if dpi:
                return int(dpi)
    except Exception:
        pass
    return 96


def _wnd_proc(hwnd, msg, wparam, lparam):
    """模块级窗口过程：找回实例后交给它的处理函数。

    这里运行在窗口线程（主线程）上，所有控件操作都在这个上下文里做，
    不会出现跨线程改 UI 导致的崩溃。
    """
    with _WINDOWS_LOCK:
        inst = _WINDOWS.get(int(hwnd or 0))
    if inst is not None:
        try:
            return inst._handle_message(hwnd, msg, wparam, lparam)
        except Exception:
            return 0
    return _user32().DefWindowProcW(hwnd, msg, wparam, lparam)


# 关键：WNDPROC 对象必须一直持有，否则被 GC 掉后窗口过程变成野指针 → 崩。
_WNDPROC_REF = WNDPROC(_wnd_proc)


def _register_class() -> None:
    global _CLASS_REGISTERED, _HINSTANCE
    if _CLASS_REGISTERED:
        return
    u = _user32()
    k = _kernel32()
    _HINSTANCE = k.GetModuleHandleW(None)
    wc = WNDCLASSW()
    wc.style = 0
    wc.lpfnWndProc = ctypes.cast(_WNDPROC_REF, HANDLE)
    wc.cbClsExtra = 0
    wc.cbWndExtra = 0
    wc.hInstance = _HINSTANCE
    wc.hIcon = u.LoadIconW(None, HANDLE(IDI_APPLICATION))
    wc.hCursor = u.LoadCursorW(None, HANDLE(32512))       # IDC_ARROW
    wc.hbrBackground = HANDLE(COLOR_WINDOW + 1)
    wc.lpszMenuName = None
    wc.lpszClassName = _CLASS_NAME
    if not u.RegisterClassW(ctypes.byref(wc)):
        err = ctypes.get_last_error()
        # 1410 = ERROR_CLASS_ALREADY_EXISTS（同一进程重复注册），可忽略
        if err not in (0, 1410):
            raise ctypes.WinError(err)
    _CLASS_REGISTERED = True


class NativeProgressWindow:
    """Win32 原生进度窗。

    用法::

        win = NativeProgressWindow(title="…", silent=False)
        flow = UpgradeFlow(..., on_stage=win.post_stage,
                           on_progress=win.post_progress,
                           on_message=win.post_message,
                           cancel_check=win.is_cancelled)
        code = win.run(lambda: flow.run_full())

    ``run`` 会创建窗口、起工作线程、跑消息循环，返回流程的退出码
    （线程异常时由调用方转成 2）。
    """

    def __init__(self, title: str, silent: bool = False,
                 stage_text=None, close_delay_ms: int = 2500,
                 check_only: bool = False):
        self.title = title
        self.silent = silent
        self.stage_text = dict(stage_text or {})
        self.close_delay_ms = int(close_delay_ms)
        self.check_only = check_only

        self.hwnd = None
        self._hwnd_stage = None
        self._hwnd_bar = None
        self._hwnd_log = None
        self._hwnd_btn = None
        self._font = None
        self._font_title = None
        self._scale = 1.0

        self._thread = None
        self._code = None
        self._closed = False
        self._cancel_evt = threading.Event()
        self._lock = threading.Lock()

        # 工作线程只负责把「最新值」塞进这些槽位，然后 PostMessage 通知。
        # 阶段/日志用队列，保证每个阶段都显示；进度只留最新值（刷得太快）。
        self._pending_stages = deque()
        self._pending_progress = None
        self._pending_msgs = deque()
        self._stage_posted = False
        self._progress_posted = False
        self._msg_posted = False
        self._log_text = ""

    # ------------------------------------------------------------------ #
    # 给工作线程用的投递接口（只投递，不碰控件）
    # ------------------------------------------------------------------ #
    def post_stage(self, key):
        text = self.stage_text.get(key, key)
        with self._lock:
            self._pending_stages.append(text)
            already = self._stage_posted
            self._stage_posted = True
        if not already:
            self._post(WM_APP_STAGE)

    def post_progress(self, cur, total):
        with self._lock:
            self._pending_progress = (int(cur), int(total))
            already = self._progress_posted
            self._progress_posted = True
        if not already:
            self._post(WM_APP_PROGRESS)

    def post_message(self, text, level="info"):
        with self._lock:
            self._pending_msgs.append(str(text))
            already = self._msg_posted
            self._msg_posted = True
        if not already:
            self._post(WM_APP_MESSAGE)

    def is_cancelled(self) -> bool:
        return self._cancel_evt.is_set()

    def _post(self, msg, wparam=0, lparam=0):
        hwnd = self.hwnd
        if not hwnd or self._closed:
            return
        # 只投递消息；控件操作留到窗口线程，绝不在工作线程直接改 UI。
        _user32().PostMessageW(HANDLE(hwnd), msg, WPARAM(wparam), LPARAM(lparam))

    # ------------------------------------------------------------------ #
    # 窗口创建 / 布局
    # ------------------------------------------------------------------ #
    def _create(self):
        _init_dpi_awareness()
        _register_class()
        self._scale = max(1.0, _system_dpi() / 96.0)

        u = _user32()
        k = _kernel32()
        try:
            icc = INITCOMMONCONTROLSEX(ctypes.sizeof(INITCOMMONCONTROLSEX),
                                       ICC_PROGRESS_CLASS)
            _comctl32().InitCommonControlsEx.argtypes = [
                ctypes.POINTER(INITCOMMONCONTROLSEX)]
            _comctl32().InitCommonControlsEx.restype = wintypes.BOOL
            _comctl32().InitCommonControlsEx(ctypes.byref(icc))
        except Exception:
            pass

        style = WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX | WS_CLIPCHILDREN
        ex_style = 0
        rect = RECT(0, 0, self._px(560), self._px(420))
        u.AdjustWindowRectEx(ctypes.byref(rect), style, False, ex_style)

        x, y = self._center(rect.right - rect.left, rect.bottom - rect.top)
        self.hwnd = u.CreateWindowExW(
            ex_style, _CLASS_NAME, self.title, style,
            x, y, rect.right - rect.left, rect.bottom - rect.top,
            None, None, _HINSTANCE or k.GetModuleHandleW(None), None,
        )
        if not self.hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        with _WINDOWS_LOCK:
            _WINDOWS[int(self.hwnd)] = self

        self._font = self._make_font(self._px(15), FW_NORMAL)
        self._font_title = self._make_font(self._px(17), FW_SEMIBOLD)

        self._hwnd_stage = self._make_control(
            "STATIC", "", WS_CHILD | WS_VISIBLE | SS_LEFT)
        self._hwnd_bar = self._make_control("msctls_progress32", "",
                                            WS_CHILD | WS_VISIBLE)
        self._hwnd_log = self._make_control(
            "EDIT", "",
            WS_CHILD | WS_VISIBLE | WS_VSCROLL | ES_MULTILINE | ES_READONLY
            | ES_AUTOVSCROLL, ex_style=WS_EX_CLIENTEDGE)
        # 控件的 hMenu 参数就是控件 ID，必须显式传，否则都是 0，
        # WM_COMMAND 里就分不清是哪个按钮（取消会失效）。
        self._hwnd_btn = self._make_control(
            "BUTTON", "后台升级中…" if self.silent else "取消",
            WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON, ctrl_id=ID_CANCEL)

        self._set_font(self._hwnd_stage, self._font_title)
        self._set_font(self._hwnd_log, self._font)
        self._set_font(self._hwnd_bar, self._font)
        self._set_font(self._hwnd_btn, self._font)

        u.SendMessageW(HANDLE(self._hwnd_bar), PBM_SETRANGE32, WPARAM(0),
                       LPARAM(100))
        u.SendMessageW(HANDLE(self._hwnd_bar), PBM_SETPOS, WPARAM(0), LPARAM(0))
        u.SetWindowTextW(HANDLE(self._hwnd_stage), "准备中…")
        if self.silent:
            # silent 语义：不可交互，按钮只作为状态提示
            u.EnableWindow(HANDLE(self._hwnd_btn), False)

        self._layout()
        u.ShowWindow(HANDLE(self.hwnd), SW_SHOW)
        u.UpdateWindow(HANDLE(self.hwnd))
        try:
            u.SetForegroundWindow(HANDLE(self.hwnd))
        except Exception:
            pass

    def _make_font(self, height_px, weight):
        h = -max(9, int(round(height_px)))
        face = "Microsoft YaHei UI"
        font = _gdi32().CreateFontW(
            h, 0, 0, 0, weight, 0, 0, 0, DEFAULT_CHARSET, 0, 0,
            CLEARTYPE_QUALITY, 0, face,
        )
        if not font:
            font = _gdi32().CreateFontW(
                h, 0, 0, 0, weight, 0, 0, 0, DEFAULT_CHARSET, 0, 0,
                CLEARTYPE_QUALITY, 0, "Segoe UI",
            )
        return font

    def _make_control(self, cls, text, style, ex_style=0, ctrl_id=0):
        hwnd = _user32().CreateWindowExW(
            ex_style, cls, text, style, 0, 0, 10, 10,
            HANDLE(self.hwnd), HANDLE(ctrl_id) if ctrl_id else None,
            _HINSTANCE, None,
        )
        if not hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        return hwnd

    def _set_font(self, hwnd, font):
        if hwnd and font:
            _user32().SendMessageW(HANDLE(hwnd), WM_SETFONT, WPARAM(int(font)),
                                   LPARAM(1))

    def _px(self, v):
        return int(round(v * self._scale))

    def _center(self, w, h):
        rect = RECT()
        ok = _user32().SystemParametersInfoW(SPI_GETWORKAREA, 0,
                                             ctypes.byref(rect), 0)
        if not ok:
            rect.left, rect.top = 0, 0
            rect.right = _user32().GetSystemMetrics(SM_CXSCREEN)
            rect.bottom = _user32().GetSystemMetrics(SM_CYSCREEN)
        x = rect.left + max(0, ((rect.right - rect.left) - w) // 2)
        y = rect.top + max(0, ((rect.bottom - rect.top) - h) // 3)
        return x, y

    def _layout(self):
        rc = RECT()
        if not self._user32_get_client(rc):
            return
        u = _user32()
        m = self._px(18)
        w = max(1, rc.right - rc.left - 2 * m)
        stage_h = self._px(24)
        bar_h = self._px(20)
        btn_w, btn_h = self._px(110), self._px(32)

        y = m
        self._move(self._hwnd_stage, m, y, w, stage_h)
        y += stage_h + self._px(10)
        self._move(self._hwnd_bar, m, y, w, bar_h)
        y += bar_h + self._px(14)
        bottom = rc.bottom - m - btn_h - self._px(12)
        log_h = max(self._px(60), bottom - y)
        self._move(self._hwnd_log, m, y, w, log_h)

        btn_y = rc.bottom - m - btn_h
        self._move(self._hwnd_btn, rc.right - m - btn_w, btn_y, btn_w, btn_h)

    def _user32_get_client(self, rc):
        if not self.hwnd:
            return False
        return bool(_user32().GetClientRect(HANDLE(self.hwnd), ctypes.byref(rc)))

    def _move(self, hwnd, x, y, w, h):
        if hwnd:
            _user32().MoveWindow(HANDLE(hwnd), x, y, w, h, True)

    # ------------------------------------------------------------------ #
    # 窗口线程的消息处理
    # ------------------------------------------------------------------ #
    def _handle_message(self, hwnd, msg, wparam, lparam):
        u = _user32()
        if msg == WM_APP_STAGE:
            with self._lock:
                texts = list(self._pending_stages)
                self._pending_stages.clear()
                self._stage_posted = False
            if texts:
                u.SetWindowTextW(HANDLE(self._hwnd_stage), texts[-1])
                for text in texts:
                    self._append_log_line(f"· {text}")
            return 0
        if msg == WM_APP_PROGRESS:
            with self._lock:
                val = self._pending_progress
                self._progress_posted = False
            if val:
                cur, total = val
                total = max(1, total)
                u.SendMessageW(HANDLE(self._hwnd_bar), PBM_SETRANGE32,
                               WPARAM(0), LPARAM(total))
                u.SendMessageW(HANDLE(self._hwnd_bar), PBM_SETPOS,
                               WPARAM(max(0, cur)), LPARAM(0))
            return 0
        if msg == WM_APP_MESSAGE:
            with self._lock:
                lines = []
                while self._pending_msgs:
                    lines.append(self._pending_msgs.popleft())
                self._msg_posted = False
            for line in lines:
                self._append_log_line(line)
            return 0
        if msg == WM_APP_DONE:
            self._on_done(int(wparam))
            return 0
        if msg == WM_COMMAND:
            if (wparam & 0xFFFF) == ID_CANCEL and ((wparam >> 16) & 0xFFFF) == 0:
                self._on_cancel()
                return 0
            return 0
        if msg == WM_TIMER:
            if int(wparam) == ID_TIMER_CLOSE:
                u.KillTimer(HANDLE(hwnd), ID_TIMER_CLOSE)
                self._destroy()
            return 0
        if msg == WM_CLOSE:
            if self.silent:
                # silent 模式不允许用户关窗打断升级（与 2.x 语义一致）
                return 0
            if self._code is None:
                # 用户提前关窗：置取消标志并退出，返回码沿用「未完成 → 2」
                self._cancel_evt.set()
            self._destroy()
            return 0
        if msg == WM_DESTROY:
            with _WINDOWS_LOCK:
                _WINDOWS.pop(int(hwnd or 0), None)
            self._cleanup()
            u.PostQuitMessage(0)
            return 0
        return u.DefWindowProcW(HANDLE(hwnd), msg, WPARAM(wparam), LPARAM(lparam))

    def _on_cancel(self):
        self._cancel_evt.set()
        _user32().EnableWindow(HANDLE(self._hwnd_btn), False)
        _user32().SetWindowTextW(HANDLE(self._hwnd_stage), "正在取消…")

    def _on_done(self, code):
        self._code = code
        u = _user32()
        if code == 0:
            u.SetWindowTextW(HANDLE(self._hwnd_stage), "升级完成，正在重启…")
            u.SendMessageW(HANDLE(self._hwnd_bar), PBM_SETPOS, WPARAM(100),
                           LPARAM(0))
        elif code == 1:
            u.SetWindowTextW(HANDLE(self._hwnd_stage), "已是最新版本")
        else:
            u.SetWindowTextW(HANDLE(self._hwnd_stage), "升级失败，详见日志")
        if self._hwnd_btn and not self.silent:
            u.EnableWindow(HANDLE(self._hwnd_btn), False)
        # 延迟关闭用 SetTimer，绝不在窗口线程 sleep —— sleep 会阻塞消息循环，
        # 窗口会假死（“未响应”）。
        if self.close_delay_ms > 0:
            u.SetTimer(HANDLE(self.hwnd), ID_TIMER_CLOSE,
                       self.close_delay_ms, None)
        else:
            self._destroy()

    def _append_log_line(self, text):
        if not self._hwnd_log:
            return
        # 这里用「累积文本 + SetWindowTextW」，而不是 EM_REPLACESEL：
        # 后者需要把字符串指针塞进 LPARAM，ctypes 签名得来回切换，容易出错。
        # 升级日志量很小（几十行），整块重设完全够用。
        self._log_text += ("\r\n" if self._log_text else "") + str(text)
        u = _user32()
        u.SetWindowTextW(HANDLE(self._hwnd_log), self._log_text)
        # 光标移到末尾并滚动，读到最新一行
        end = WPARAM(0xFFFFFFFFFFFFFFFF)
        u.SendMessageW(HANDLE(self._hwnd_log), EM_SETSEL, end,
                       LPARAM(0xFFFFFFFFFFFFFFFF))
        u.SendMessageW(HANDLE(self._hwnd_log), EM_SCROLLCARET, WPARAM(0),
                       LPARAM(0))

    def _destroy(self):
        if self._closed:
            return
        self._closed = True
        if self.hwnd:
            try:
                _user32().KillTimer(HANDLE(self.hwnd), ID_TIMER_CLOSE)
            except Exception:
                pass
            _user32().DestroyWindow(HANDLE(self.hwnd))
            self.hwnd = None

    def _cleanup(self):
        for font in (self._font, self._font_title):
            if font:
                try:
                    _gdi32().DeleteObject(HANDLE(font))
                except Exception:
                    pass
        self._font = self._font_title = None

    # ------------------------------------------------------------------ #
    # 主入口
    # ------------------------------------------------------------------ #
    def _worker_main(self, task):
        try:
            code = int(task())
        except Exception:
            code = 2
        self._post(WM_APP_DONE, wparam=code)
        # 若窗口已被用户提前关掉，_post 会静默失败，流程线程自行结束即可。

    def run(self, task) -> int:
        """创建窗口、起工作线程、跑消息循环，返回流程退出码。"""
        self._create()
        self._thread = threading.Thread(target=self._worker_main, args=(task,),
                                        name="upgrade-flow", daemon=True)
        self._thread.start()

        u = _user32()
        msg = MSG()
        while True:
            ret = u.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret is None:
                return 2
            if ret == 0 or ret == -1:
                break
            u.TranslateMessage(ctypes.byref(msg))
            u.DispatchMessageW(ctypes.byref(msg))

        # 和原 Qt 实现一致：窗口先关了也等工作线程最多 3 秒
        try:
            if self._thread.is_alive():
                self._thread.join(3.0)
        except Exception:
            pass
        return self._code if self._code is not None else 2
