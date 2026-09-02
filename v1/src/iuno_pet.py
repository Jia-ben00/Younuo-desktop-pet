# -*- coding: utf-8 -*-
"""
鸣潮 · 尤诺团子 桌面宠物

功能：
  * 窗口透明、无边框、始终置顶、不进任务栏、不抢输入焦点
  * 鼠标左键按住可拖动位置
  * 默认跟随鼠标光标移动（可在右键菜单中关闭）
  * 鼠标滚轮在桌宠上滚动可调整大小
  * 任意键盘按键触发跳跃动画（全局键盘钩子同步）
  * 右键菜单：调整大小 / 始终置顶 / 跟随鼠标 / 退出程序

打包：pyinstaller --onefile --windowed --add-data "assets/iuno_pet.png;assets" iuno_pet.py
注意事项：
 1) 项目路径含中文时，PyInstaller 的 Qt 钩子可能因编码问题失败，请把源码与虚拟环境
    放到纯英文路径下构建，产物再拷回项目目录。
 2) 若使用 anaconda 的 conda Python，需把 libffi 一并打包，否则运行时报
    "DLL load failed while importing _ctypes"：
    --add-binary "<anaconda>\\Library\\bin\\ffi.dll;."
 3) 建议在独立 venv 中 pip 安装 PyQt5 + pyinstaller（避免 conda 变体 Qt 的
    Qt5Core_conda.dll 命名问题）。
"""
import sys
import os
import math
import ctypes
import ctypes.wintypes
import threading
import queue

from PyQt5.QtCore import Qt, QTimer, QPoint
from PyQt5.QtGui import QPainter, QPixmap, QGuiApplication, QCursor
from PyQt5.QtWidgets import QApplication, QWidget, QMenu


def resource_path(rel):
    """兼容 PyInstaller 打包后的资源路径，也兼容源码运行时。"""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, rel)
    base = os.path.dirname(os.path.abspath(__file__))
    if not os.path.exists(os.path.join(base, rel)):
        base = os.path.dirname(base)  # 源码模式下 assets 在项目根目录
    return os.path.join(base, rel)


# ---------------- 全局键盘钩子 ----------------
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.c_uint32),
        ("scanCode", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("time", ctypes.c_uint32),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int,
                              ctypes.c_ulong, ctypes.c_ulong)


class GlobalKeyboardHook:
    """低层全局键盘钩子：任意按键按下时回调（运行在独立线程）。"""

    def __init__(self, on_key):
        self.on_key = on_key
        self._hook = None
        self._proc = None
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._proc = HOOKPROC(self._callback)
        self._hook = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, self._proc, kernel32.GetModuleHandleW(None), 0)
        if not self._hook:
            return
        msg = ctypes.wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        user32.UnhookWindowsHookEx(self._hook)

    def _callback(self, nCode, wParam, lParam):
        if nCode >= 0 and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
            try:
                self.on_key()
            except Exception:
                pass
        return ctypes.windll.user32.CallNextHookEx(
            self._hook, nCode, wParam, lParam)


# ---------------- 桌宠窗口 ----------------
class PetWindow(QWidget):
    # 预设尺寸（显示高度，像素）
    PRESET_SIZES = [("小", 120), ("中", 180), ("大", 240), ("超大", 320)]
    MIN_H = 80
    MAX_H = 900
    FOLLOW_OFF = QPoint(48, 56)   # 跟随时光标与桌宠左上角的偏移
    EASE = 0.18                   # 跟随平滑系数

    def __init__(self, image_path):
        super().__init__(None)
        self.base = QPixmap(image_path)
        if self.base.isNull():
            raise RuntimeError("无法加载图片: %s" % image_path)
        self.base_w = self.base.width()
        self.base_h = self.base.height()

        # 窗口标志：无边框 + 始终置顶 + 工具窗口（不进任务栏）+ 不抢焦点
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        # 状态
        self.always_on_top = True
        self.follow = True
        self.dragging = False
        self.drag_offset = QPoint(0, 0)
        self.base_pos = QPoint(0, 0)   # 跳跃/动画的基准位置

        # 动画状态
        self.bouncing = False
        self.bounce_p = 0.0
        self.bounce_timer = QTimer(self)
        self.bounce_timer.setInterval(16)
        self.bounce_timer.timeout.connect(self._bounce_tick)

        # 显示尺寸
        self.display_h = 220
        self.scaled = self.base.scaled(
            int(self.base_w * self.display_h / self.base_h),
            self.display_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setFixedSize(self.scaled.size())

        # 跟随定时器
        self.follow_timer = QTimer(self)
        self.follow_timer.setInterval(16)
        self.follow_timer.timeout.connect(self._follow_tick)
        self.follow_timer.start()

        # 键盘事件轮询（钩子线程 -> 队列 -> 主线程）
        self.key_q = queue.Queue()
        self.key_poll = QTimer(self)
        self.key_poll.setInterval(50)
        self.key_poll.timeout.connect(self._poll_keys)
        self.key_poll.start()
        self.hook = GlobalKeyboardHook(lambda: self.key_q.put(1))
        self.hook.start()

        # 初始位置：屏幕右下角
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.base_pos = QPoint(screen.right() - self.width() - 40,
                               screen.bottom() - self.height() - 10)
        self.move(self.base_pos)
        self.show()

    # ---------------- 尺寸 ----------------
    def set_preset_size(self, h):
        self.display_h = max(self.MIN_H, min(self.MAX_H, h))
        self._apply_size()

    def wheelEvent(self, e):
        delta = e.angleDelta().y()
        if delta == 0:
            return
        factor = 1.12 if delta > 0 else 1.0 / 1.12
        self.display_h = int(self.display_h * factor)
        self.display_h = max(self.MIN_H, min(self.MAX_H, self.display_h))
        self._apply_size(anchor=True)
        e.accept()

    def _apply_size(self, anchor=False):
        """按 display_h 等比缩放，锚定光标位置（可选），并保持可见。"""
        old_geo = self.frameGeometry()
        w = max(1, int(self.base_w * self.display_h / self.base_h))
        self.scaled = self.base.scaled(w, self.display_h, Qt.KeepAspectRatio,
                                       Qt.SmoothTransformation)
        self.setFixedSize(self.scaled.size())
        if anchor:
            c = QCursor.pos()
            rx = (c.x() - old_geo.x()) / old_geo.width() if old_geo.width() else 0.5
            ry = (c.y() - old_geo.y()) / old_geo.height() if old_geo.height() else 0.5
            nx = c.x() - int(w * rx)
            ny = c.y() - int(self.display_h * ry)
        else:
            nx, ny = self.x(), self.y()
        self._clamp_and_move(nx, ny)
        self.base_pos = self.pos()
        self.update()

    def _clamp_and_move(self, x, y):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        x = min(max(x, screen.left()), max(screen.left(), screen.right() - self.width() + 8))
        y = min(max(y, screen.top()), max(screen.top(), screen.bottom() - self.height() + 8))
        self.move(x, y)

    # ---------------- 拖动 ----------------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.dragging = True
            self.drag_offset = e.globalPos() - self.frameGeometry().topLeft()
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self.dragging and (e.buttons() & Qt.LeftButton):
            self.move(e.globalPos() - self.drag_offset)
            self.base_pos = self.pos()
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.dragging = False
            e.accept()
            return
        super().mouseReleaseEvent(e)

    # ---------------- 跟随鼠标 ----------------
    def _follow_tick(self):
        if not self.follow or self.dragging or self.bouncing:
            return
        cursor = QCursor.pos()
        # 光标已到桌宠上/附近时暂停跟随，方便交互
        if self.frameGeometry().contains(cursor):
            return
        target = cursor + self.FOLLOW_OFF
        screen = QGuiApplication.primaryScreen().availableGeometry()
        tx = min(max(target.x(), screen.left()),
                 max(screen.left(), screen.right() - self.width()))
        ty = min(max(target.y(), screen.top()),
                 max(screen.top(), screen.bottom() - self.height()))
        cur = self.pos()
        nx = cur.x() + (tx - cur.x()) * self.EASE
        ny = cur.y() + (ty - cur.y()) * self.EASE
        if abs(nx - cur.x()) < 1 and abs(ny - cur.y()) < 1:
            return
        self.move(int(nx), int(ny))
        self.base_pos = self.pos()

    # ---------------- 键盘 -> 跳跃 ----------------
    def _poll_keys(self):
        if self.key_q.empty():
            return
        self.key_q.queue.clear()
        if not self.bouncing:
            self.bouncing = True
            self.bounce_p = 0.0
            self.bounce_timer.start()

    def _bounce_tick(self):
        self.bounce_p += 0.035
        if self.bounce_p >= 1.0:
            self.bounce_timer.stop()
            self.bouncing = False
            self.move(self.base_pos)
            self.update()
            return
        p = self.bounce_p
        jump = int(70 * math.sin(math.pi * p))
        self.move(self.base_pos.x(), self.base_pos.y() - jump)
        self.update()

    # ---------------- 绘制 ----------------
    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        if self.bouncing:
            p = self.bounce_p
            s = 0.10 * math.sin(math.pi * p)
            w = max(1, int(self.scaled.width() * (1.0 + s)))
            h = max(1, int(self.scaled.height() * (1.0 - s)))
            img = self.scaled.scaled(w, h, Qt.IgnoreAspectRatio,
                                     Qt.SmoothTransformation)
            painter.drawPixmap((self.width() - img.width()) // 2,
                               self.height() - img.height(), img)
        else:
            painter.drawPixmap(0, 0, self.scaled)

    # ---------------- 右键菜单 ----------------
    def contextMenuEvent(self, e):
        menu = QMenu(self)
        sub = menu.addMenu("调整大小")
        for name, h in self.PRESET_SIZES:
            act = sub.addAction(name)
            act.triggered.connect(lambda _=False, hh=h: self.set_preset_size(hh))
        act_top = menu.addAction("始终置顶")
        act_top.setCheckable(True)
        act_top.setChecked(self.always_on_top)
        act_top.toggled.connect(self.toggle_topmost)
        act_follow = menu.addAction("跟随鼠标")
        act_follow.setCheckable(True)
        act_follow.setChecked(self.follow)
        act_follow.toggled.connect(self.set_follow)
        menu.addSeparator()
        act_quit = menu.addAction("退出程序")
        act_quit.triggered.connect(self.quit_app)
        menu.exec_(e.globalPos())

    def toggle_topmost(self, on):
        self.always_on_top = on
        try:
            hwnd = int(self.winId())
            ctypes.windll.user32.SetWindowPos(
                hwnd, HWND_TOPMOST if on else HWND_NOTOPMOST,
                0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        except Exception:
            pass

    def set_follow(self, on):
        self.follow = on

    def quit_app(self):
        self.close()
        QApplication.instance().quit()


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    image_path = resource_path(os.path.join("assets", "iuno_pet.png"))
    try:
        win = PetWindow(image_path)
    except Exception as ex:
        ctypes.windll.user32.MessageBoxW(0, str(ex), "尤诺桌宠", 0x10)
        return 1

    # 自检模式：固定位置、关闭跟随、短暂运行后自动退出（用于验证程序可运行）
    if "--selftest" in sys.argv:
        win.follow = False
        screen = QGuiApplication.primaryScreen().availableGeometry()
        win._clamp_and_move(screen.center().x() - win.width() // 2,
                            screen.center().y() - win.height() // 2)
        QTimer.singleShot(2500, app.quit)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
