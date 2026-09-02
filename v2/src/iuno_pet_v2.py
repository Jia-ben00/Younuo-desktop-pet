# -*- coding: utf-8 -*-
"""
鸣潮 · 尤诺团子 桌面宠物 v2
========================================================================
在 v1（透明/无边框/置顶/拖动/跟随/滚轮缩放/键盘/右键菜单）基础上新增：
  ① 人设（角色卡）：傲娇·月相谕女团子化，行为与语气围绕人设展开
  ② 动态协议：情绪 × 动作 × 特效 的状态机（开心/生气/难过/惊讶/傲娇/平静），
     参数命名对齐 Live2D Cubism 标准参数，便于日后替换为真 Live2D 模型
  ③ 语音模块：AI TTS 风格参考生成（非真人克隆）的语气词库 + 口型联动
     + 任意文本朗读（系统 TTS 兜底，含长文本跳过规则）

------------------------------------------------------------------------
[动态协议 · 情绪 → 动作 → 特效]
  情绪      动作              特效/参数
  平静      待机呼吸           ParamBreath 0~1 循环，尾巴轻摆
  开心      转圈（±15°）       ParamBodyAngleZ 循环，脸红 ParamBlush
  生气      快速抖动           炸毛冒烟 ParamSmoke=1
  难过      缩团（0.86）+ 下沉  耳朵下垂，眼泪
  惊讶      跳起（抛物线）       ParamBodyAngleY 上移，嘴开 ParamMouthOpenY=1
  傲娇      别过头（-20°）     歪嘴 ParamMouthForm=0.5，脸红，偷瞄
  说话      ParamMouthOpenY 跟随音频电平（口型联动）
自定义参数（团子专属）：ParamTail 尾巴 / ParamEarL/R 耳朵 / ParamBlush 脸红
  / ParamSmoke 冒烟 / ParamMoon 月亮符文 / ParamHands 比心

[语音触发规则]
  - 语气词库优先级最高，命中即播：摸头→哼~ / 戳脸→呀！ / 拖拽→喂喂！
    / 喂食→吧唧吧唧 / 晚安→不准松开我
  - 说话（任意文本）：>80 字或含代码/数据标记自动跳过语音，只显示文字气泡
  - 口型联动：说话期间嘴部跟随音频电平开合

------------------------------------------------------------------------
打包（英文路径 + 独立 venv，见 v1 docs）：
  pyinstaller --onefile --windowed --name 尤诺桌宠v2 \
    --icon assets/iuno.ico \
    --add-data "assets/iuno_pet.png;assets" \
    --add-data "assets/voice;assets/voice" \
    src/iuno_pet_v2.py
  （conda Python 需追加 --add-binary "<anaconda>\\Library\\bin\\ffi.dll;."）
"""
import sys
import os
import math
import random
import wave
import array
import ctypes
import ctypes.wintypes
import threading
import queue
import subprocess
import winsound

from PyQt5.QtCore import Qt, QTimer, QPoint, QPointF, QRectF
from PyQt5.QtGui import (QPainter, QPixmap, QGuiApplication, QCursor,
                         QColor, QBrush, QPainterPath, QFont)
from PyQt5.QtWidgets import (QApplication, QWidget, QMenu, QInputDialog)


def resource_path(rel):
    """兼容 PyInstaller 打包后的资源路径，也兼容源码运行时。"""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, rel)
    base = os.path.dirname(os.path.abspath(__file__))
    if not os.path.exists(os.path.join(base, rel)):
        base = os.path.dirname(base)
    return os.path.join(base, rel)


# ============================= ① 人设（角色卡） =============================
PERSONA = {
    "conf_uid": "yuno_dango_v2",
    "name": "尤诺（团子）",
    "identity": ("《鸣潮》七丘的谕女尤诺，在月食之夜降生，能借烛火预见未来。"
                 "如今被漂泊者收留，化成一团圆滚滚的月之团子，住在你的桌面角落。"),
    "personality": ("傲娇。嘴硬心软，明明很在意却总说'哼，才不是特意为你留的'。"
                    "害怕被当成小孩子，但被摸头时尾巴会忍不住摇起来。"),
    "speech_style": ("语速偏快、尾音上扬带钩；开心时明快跳跃，傲娇时故作冷淡但尾音露馅，"
                     "生气时气鼓鼓、拖长音。"),
    "likes": ("满月、热汤、被摸头、安静地看着你敲代码"),
    "dislikes": ("被突然戳脸（会炸毛）、熬夜不睡觉、'团子'之外的外号"),
    "moon_theme": ("随身带着一枚月亮符文：心情好时会亮起来。"),
    "relation": "把你当作唯一的'漂泊者'，守护你的桌面与时间。",
}

# =========================== ② 动态协议（情绪配置） ===========================
EMOTIONS = {
    # 情绪: (时长秒, 动作名)
    "平静": (0.0, "待机呼吸"),
    "开心": (3.0, "转圈"),
    "生气": (1.6, "炸毛冒烟"),
    "难过": (2.4, "缩团"),
    "惊讶": (1.2, "跳起"),
    "傲娇": (3.0, "别过头"),
}
EMOTION_ORDER = ["平静", "开心", "生气", "难过", "惊讶", "傲娇"]

# 语气词库（优先级最高，命中即播）
TONE_LIBRARY = {
    "摸头": {"file": "pat.wav",   "text": "哼~",        "emotion": "开心"},
    "戳脸": {"file": "poke.wav",  "text": "呀！",       "emotion": "惊讶"},
    "拖拽": {"file": "drag.wav",  "text": "喂喂！",     "emotion": "生气"},
    "喂食": {"file": "feed.wav",  "text": "吧唧吧唧",   "emotion": "开心"},
    "晚安": {"file": "sleep.wav", "text": "不准松开我", "emotion": "傲娇"},
}

# TTS 音色描述（风格参考，非真人克隆）—— 供接入更强 TTS 引擎时使用
TTS_VOICE_DESC = ("傲娇系年轻少女声线：清亮带小鼻音，语速偏快、尾音上扬带钩；"
                  "开心时明快跳跃，傲娇时故作冷淡但尾音露馅，生气时气鼓鼓、拖长音。")


# ---------------- 全局键盘钩子 ----------------
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
# 忽略修饰键（避免按 Ctrl/Shift/Alt/Win 触发）
MODIFIER_KEYS = {0x10, 0x11, 0x12, 0x5B, 0x5C, 0xA0, 0xA1, 0xA2, 0xA3}


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
                k = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                self.on_key(k.vkCode)
            except Exception:
                pass
        return ctypes.windll.user32.CallNextHookEx(
            self._hook, nCode, wParam, lParam)


# ---------------- 语音模块 ----------------
class VoiceEngine:
    """语气词库 + 音频电平包络（供口型联动）。"""

    def __init__(self, voice_dir, enabled=True):
        self.voice_dir = voice_dir
        self.enabled = enabled
        self.envelopes = {}   # tone -> [(t_ms, level 0~1), ...]
        self.durations = {}   # tone -> 秒
        for key, info in TONE_LIBRARY.items():
            path = os.path.join(voice_dir, info["file"])
            if os.path.exists(path):
                env, dur = self._load_envelope(path)
                self.envelopes[key] = env
                self.durations[key] = dur

    @staticmethod
    def _load_envelope(path, win_ms=50):
        """预计算 RMS 电平包络（0~1），供嘴部口型跟随。"""
        try:
            with wave.open(path, "rb") as w:
                rate = w.getframerate()
                n = w.getnframes()
                raw = w.readframes(n)
            a = array.array("h", raw)
            ch = 2
            frames = len(a) // ch
            win = max(1, int(rate * win_ms / 1000.0))
            env = []
            for i in range(0, frames, win):
                seg = a[i * ch:(i + win) * ch]
                if not seg:
                    break
                peak = max(abs(x) for x in seg) / 32768.0
                env.append((i / rate, min(1.0, peak)))
            dur = frames / rate if rate else 0.0
            return env, dur
        except Exception:
            return [], 0.0

    def play(self, key):
        """播放语气词，返回时长秒；不可用返回 0。"""
        if not self.enabled:
            return 0.0
        info = TONE_LIBRARY.get(key)
        if not info:
            return 0.0
        path = os.path.join(self.voice_dir, info["file"])
        if not os.path.exists(path):
            return 0.0
        try:
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception:
            return 0.0
        return self.durations.get(key, 0.0)

    def stop(self):
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass

    def level_at(self, key, t):
        """按时间取电平值，用于口型。"""
        env = self.envelopes.get(key)
        if not env:
            return 0.0
        level = 0.0
        for t0, lv in env:
            if t0 > t:
                break
            level = lv
        return level


# ---------------- 桌宠 v2 窗口 ----------------
class PetWindowV2(QWidget):
    PRESET_SIZES = [("小", 120), ("中", 180), ("大", 240), ("超大", 320)]
    MIN_H = 80
    MAX_H = 900
    FOLLOW_OFF = QPoint(48, 56)
    EASE = 0.18
    DOUBLE_CLICK_MS = 280
    TOP_PAD = 0.30   # 头部上方留白比例（冒烟/月亮/气泡绘制区），相对角色高度

    def __init__(self, image_path, voice_dir):
        super().__init__(None)
        self.base = QPixmap(image_path)
        if self.base.isNull():
            raise RuntimeError("无法加载图片: %s" % image_path)
        self.base_w = self.base.width()
        self.base_h = self.base.height()
        self.bbox = self._alpha_bbox()   # (x, y, w, h) 不透明主体范围

        # 窗口标志：无边框 + 始终置顶 + 工具窗口 + 不抢焦点
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        # 状态
        self.always_on_top = True
        self.follow = True
        self.dragging = False
        self.drag_offset = QPoint(0, 0)
        self.dragged_dist = 0
        self.base_pos = QPoint(0, 0)
        self.voice_on = True

        # 语音
        self.voice = VoiceEngine(voice_dir, enabled=True)
        self.speaking = False
        self.speak_key = None
        self.speak_t0 = 0.0
        self.speak_dur = 0.0
        self.bubble_text = ""
        self.bubble_end = 0.0

        # 动态协议状态
        self._clock = 0.0
        self.emotion = "平静"
        self.emotion_t = 0.0
        self.emotion_reset = QTimer(self)
        self.emotion_reset.setSingleShot(True)
        self.emotion_reset.timeout.connect(lambda: self.set_emotion("平静"))

        # 动画定时器
        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(16)
        self.anim_timer.timeout.connect(self._anim_tick)
        self.anim_timer.start()

        # 显示尺寸
        self.display_h = 220
        self.scaled = self.base.scaled(
            int(self.base_w * self.display_h / self.base_h),
            self.display_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._apply_window_size()

        # 跟随定时器
        self.follow_timer = QTimer(self)
        self.follow_timer.setInterval(16)
        self.follow_timer.timeout.connect(self._follow_tick)
        self.follow_timer.start()

        # 单击/双击判定
        self.click_timer = QTimer(self)
        self.click_timer.setSingleShot(True)
        self.click_timer.setInterval(self.DOUBLE_CLICK_MS)
        self.click_timer.timeout.connect(self._on_single_click)
        self.last_click_at = 0.0

        # 键盘钩子
        self.key_q = queue.Queue()
        self.key_poll = QTimer(self)
        self.key_poll.setInterval(50)
        self.key_poll.timeout.connect(self._poll_keys)
        self.key_poll.start()
        self.hook = GlobalKeyboardHook(lambda vk: self.key_q.put(vk))
        self.hook.start()
        self.last_key_at = 0.0

        # 初始位置：屏幕右下角
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.base_pos = QPoint(screen.right() - self.width() - 40,
                               screen.bottom() - self.height() - 10)
        self.move(self.base_pos)
        self.show()

    # ---------------- 主体 bbox ----------------
    def _alpha_bbox(self):
        img = self.base.toImage()
        min_x, min_y = self.base_w, self.base_h
        max_x = max_y = 0
        step = max(1, min(self.base_w, self.base_h) // 120)
        for y in range(0, self.base_h, step):
            for x in range(0, self.base_w, step):
                if img.pixelColor(x, y).alpha() > 40:
                    min_x = min(min_x, x); max_x = max(max_x, x)
                    min_y = min(min_y, y); max_y = max(max_y, y)
        if max_x <= min_x:
            return (0, 0, self.base_w, self.base_h)
        return (min_x, min_y, max_x - min_x, max_y - min_y)

    # ---------------- 动态协议：情绪切换 ----------------
    def set_emotion(self, name, dur=None):
        if name not in EMOTIONS:
            return
        self.emotion = name
        self.emotion_t = 0.0
        hold = EMOTIONS[name][0]
        if dur is not None:
            hold = dur
        self.emotion_reset.stop()
        if hold > 0:
            self.emotion_reset.start(int(hold * 1000))

    def trigger(self, tone_key):
        """语气词 → 语音 + 情绪 + 气泡（优先级最高的触发路径）。"""
        info = TONE_LIBRARY.get(tone_key)
        if not info:
            return
        if self.voice_on:
            dur = self.voice.play(tone_key)
        else:
            dur = self.voice.durations.get(tone_key, 0.0)
        self.speaking = self.voice_on and dur > 0
        self.speak_key = tone_key
        self.speak_t0 = 0.0
        self.speak_dur = dur
        self.bubble_text = info["text"]
        self.bubble_end = self._now() + max(dur, 1.0) + 0.6
        self.set_emotion(info["emotion"])

    def _now(self):
        return getattr(self, "_clock", 0.0)

    # ---------------- 动画主循环 ----------------
    def _anim_tick(self):
        self._clock = getattr(self, "_clock", 0.0) + 0.016
        t = self._clock
        self.emotion_t += 0.016

        # 说话口型计时
        if self.speaking:
            self.speak_t0 += 0.016
            if self.speak_dur > 0 and self.speak_t0 >= self.speak_dur:
                self.speaking = False
                self.speak_key = None
        self.update()

    def _state(self):
        """由情绪 + 语音计算当前视觉参数（对齐 Live2D 参数命名）。"""
        t = self.emotion_t
        e = self.emotion
        st = {"rot": 0.0, "scale": 1.0, "dx": 0.0, "dy": 0.0,
              "blush": 0.0, "mouth": 0.0, "smoke": 0.0, "tear": 0.0,
              "moon": 0.0, "tail": 0.0, "ears": 0.0, "heart": 0.0}
        if e == "平静":
            st["scale"] = 1 + 0.02 * math.sin(2 * math.pi * 0.5 * t)
            st["tail"] = 0.5 + 0.5 * math.sin(2 * math.pi * 0.6 * t)
            st["ears"] = 0.3 + 0.3 * math.sin(2 * math.pi * 0.7 * t)
            st["moon"] = 0.3
        elif e == "开心":
            st["rot"] = 15 * math.sin(2 * math.pi * 0.4 * t)     # 转圈
            st["dy"] = -6 * abs(math.sin(2 * math.pi * 0.8 * t))
            st["blush"] = 0.6
            st["tail"] = 1.0
            st["ears"] = 1.0
            st["moon"] = 0.7
        elif e == "生气":
            st["dx"] = 3 * math.sin(2 * math.pi * 12 * t)        # 抖动
            st["dy"] = 1 * math.sin(2 * math.pi * 24 * t)
            st["smoke"] = 1.0
            st["scale"] = 1.03
        elif e == "难过":
            st["scale"] = 0.86                                     # 缩团
            st["dy"] = 12
            st["tear"] = 1.0
            st["ears"] = -0.8                                      # 耳朵下垂
            st["rot"] = 3 * math.sin(2 * math.pi * 0.3 * t)
        elif e == "惊讶":
            x = min(1.0, t / max(EMOTIONS["惊讶"][0], 0.01))
            st["dy"] = -64 * 4 * x * (1 - x)                       # 跳起抛物线
            st["mouth"] = 1.0
            st["scale"] = 1 + 0.06 * math.sin(math.pi * x)
        elif e == "傲娇":
            st["rot"] = -20 + 8 * abs(math.sin(2 * math.pi * 0.5 * t))  # 别过头+偷瞄
            st["blush"] = 0.85
            st["mouth"] = 0.4
            st["heart"] = 0.5 * (0.5 + 0.5 * math.sin(2 * math.pi * 0.8 * t))
        # 口型联动：说话时 ParamMouthOpenY 跟随音频电平
        if self.speaking and self.speak_key:
            lv = self.voice.level_at(self.speak_key, self.speak_t0)
            st["mouth"] = max(st["mouth"], min(1.0, lv * 1.6 + 0.25))
        return st

    # ---------------- 绘制 ----------------
    def paintEvent(self, e):
        st = self._state()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cw, chh = self.scaled.width(), self.scaled.height()
        # 角色在窗口底部，顶部留白给冒烟/月亮/气泡
        sy_center = self.TOP_PAD * chh + chh / 2.0

        painter.save()
        painter.translate(w / 2, sy_center + st["dy"])
        painter.rotate(st["rot"])
        painter.scale(st["scale"], st["scale"])

        # 尾巴（绘制在角色背后）
        if st["tail"] > 0:
            self._draw_tail(painter, cw, chh, st["tail"], self._clock)
        # 角色本体
        painter.drawPixmap(QPointF(-cw / 2.0 + st["dx"], -chh / 2.0), self.scaled)
        # 正面特效
        self._draw_overlays(painter, cw, chh, st)
        painter.restore()

        # 头顶气泡
        self._draw_bubble(painter, w)

    def _draw_tail(self, p, cw, chh, level, clock):
        sway = 12 * math.sin(2 * math.pi * 1.5 * clock) * level
        path = self._crescent_path(QRectF(-12 * cw / 300, chh * 0.40,
                                          24 * cw / 300, 16 * chh / 300), 0.4)
        p.save()
        p.translate(0, chh * 0.42)
        p.rotate(sway * 0.3)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 214, 170, 200))
        p.drawPath(path)
        p.restore()

    def _draw_overlays(self, p, cw, chh, st):
        # 脸频坐标（相对角色中心）
        fx = 0.0
        # 耳朵（头顶两侧小揪揪，上竖/下垂）
        if abs(st["ears"]) > 0.02:
            ear_h = int(0.16 * chh * (0.6 + 0.4 * max(0.0, st["ears"])))
            droop = max(0.0, -st["ears"])
            for sx in (-1, 1):
                ex = sx * 0.26 * cw
                ey = -0.46 * chh + droop * 0.10 * chh
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(120, 180, 235, 220))
                p.drawEllipse(QRectF(ex - 0.045 * cw, ey - ear_h,
                                     0.09 * cw, ear_h))
        # 脸红
        if st["blush"] > 0.02:
            c = QColor(255, 150, 170, int(150 * st["blush"]))
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            for sx in (-1, 1):
                bx = sx * 0.30 * cw
                by = 0.10 * chh
                p.drawEllipse(QRectF(bx - 0.10 * cw, by - 0.045 * chh,
                                     0.20 * cw, 0.09 * chh))
        # 嘴（口型联动 / 惊讶张嘴）
        mouth = st["mouth"]
        if mouth > 0.03:
            mw = 0.10 * cw
            mh = (0.02 + 0.07 * mouth) * chh
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(120, 60, 70, 230))
            p.drawEllipse(QRectF(-mw / 2, 0.18 * chh - mh / 2, mw, mh))
        # 眼泪（难过）
        if st["tear"] > 0.02:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(150, 210, 255, 220))
            p.drawEllipse(QRectF(-0.10 * cw, -0.01 * chh,
                                 0.035 * cw, 0.06 * chh))
        # 冒烟（生气炸毛）
        if st["smoke"] > 0.02:
            for i in range(3):
                off = (self._clock * 55 + i * 18) % 52
                sy = -0.52 * chh - off
                alpha = int(150 * (1 - off / 52.0))
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(210, 215, 225, alpha))
                sx = (i - 1) * 0.10 * cw + 6 * math.sin(self._clock * 3 + i)
                p.drawEllipse(QRectF(sx - 0.045 * cw, sy - 0.03 * chh,
                                     0.09 * cw, 0.06 * chh))
        # 月亮符文（心情好时亮起）
        if st["moon"] > 0.02:
            moon_path = self._crescent_path(
                QRectF(-0.09 * cw, -0.56 * chh, 0.18 * cw, 0.13 * chh), 0.55)
            glow = int(120 * st["moon"])
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 235, 160, glow))
            p.drawEllipse(QRectF(-0.11 * cw, -0.58 * chh, 0.22 * cw, 0.17 * chh))
            p.setBrush(QColor(255, 225, 130, int(255 * st["moon"])))
            p.drawPath(moon_path)
        # 比心（傲娇）
        if st["heart"] > 0.02:
            p.save()
            hx = 0.42 * cw
            hy = -0.20 * chh + 8 * math.sin(self._clock * 3)
            hs = 0.030 * cw * (0.8 + 0.4 * st["heart"])
            f = QFont("Segoe UI Symbol", max(8, int(hs)))
            p.setFont(f)
            p.setPen(QColor(255, 120, 160, int(230 * st["heart"])))
            p.drawText(QRectF(hx, hy, hs * 2, hs * 2),
                       Qt.AlignCenter, "\u2665")
            p.restore()

    @staticmethod
    def _crescent_path(rect, ratio):
        """用两圆相减画月牙。"""
        r = rect
        outer = QPainterPath()
        outer.addEllipse(r)
        inner = QPainterPath()
        inner.addEllipse(QRectF(r.x() + r.width() * ratio, r.y() - r.height() * 0.2,
                                r.width() * (1 - ratio + 0.1), r.height() * 1.4))
        return outer.subtracted(inner)

    def _draw_bubble(self, p, w):
        if not self.bubble_text or self._clock >= self.bubble_end:
            return
        txt = self.bubble_text
        f = QFont("Microsoft YaHei UI", 11)
        p.setFont(f)
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(txt)
        bw = max(60, tw + 28)
        bh = 30
        bx = (w - bw) / 2
        by = 6
        # 气泡尾巴（三角）
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 235))
        p.drawRoundedRect(QRectF(bx, by, bw, bh), 10, 10)
        tri = QPainterPath()
        tri.moveTo(w / 2 - 8, by + bh - 1)
        tri.lineTo(w / 2 + 8, by + bh - 1)
        tri.lineTo(w / 2, by + bh + 9)
        tri.closeSubpath()
        p.drawPath(tri)
        p.setPen(QColor(60, 60, 90))
        p.drawText(QRectF(bx, by, bw, bh), Qt.AlignCenter, txt)

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

    def _apply_window_size(self):
        w = max(1, int(self.base_w * self.display_h / self.base_h))
        self.setFixedSize(w, int(self.display_h * (1 + self.TOP_PAD)))

    def _apply_size(self, anchor=False):
        old_geo = self.frameGeometry()
        w = max(1, int(self.base_w * self.display_h / self.base_h))
        self.scaled = self.base.scaled(w, self.display_h, Qt.KeepAspectRatio,
                                       Qt.SmoothTransformation)
        self._apply_window_size()
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

    # ---------------- 鼠标交互 ----------------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.dragging = True
            self.drag_start = e.globalPos()
            self.drag_offset = e.globalPos() - self.frameGeometry().topLeft()
            self.dragged_dist = 0
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self.dragging and (e.buttons() & Qt.LeftButton):
            d = (e.globalPos() - self.drag_start).manhattanLength()
            self.dragged_dist = max(self.dragged_dist, d)
            self.move(e.globalPos() - self.drag_offset)
            self.base_pos = self.pos()
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            was_drag = self.dragged_dist > 8
            self.dragging = False
            if was_drag:
                # 拖拽 → 喂喂！
                self.trigger("拖拽")
            else:
                # 可能是单击，等待双击判定
                now = getattr(self, "_clock", 0.0)
                if now - self.last_click_at < self.DOUBLE_CLICK_MS / 1000.0:
                    self.click_timer.stop()
                    self._on_double_click()
                else:
                    self.click_timer.start()
            self.last_click_at = now
            e.accept()
            return
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        # Qt 会先发两次 press/release；统一在 release 逻辑里处理，这里兜底
        e.accept()

    def _on_single_click(self):
        # 单击 → 戳脸 → 呀！
        self.trigger("戳脸")

    def _on_double_click(self):
        # 双击 → 摸头 → 哼~
        self.trigger("摸头")

    def contextMenuEvent(self, e):
        menu = QMenu(self)
        sub = menu.addMenu("调整大小")
        for name, h in self.PRESET_SIZES:
            act = sub.addAction(name)
            act.triggered.connect(lambda _=False, hh=h: self.set_preset_size(hh))
        menu.addSeparator()
        act_feed = menu.addAction("喂食")
        act_feed.triggered.connect(lambda: self.trigger("喂食"))
        act_sleep = menu.addAction("晚安")
        act_sleep.triggered.connect(lambda: self.trigger("晚安"))
        act_talk = menu.addAction("跟我说话…")
        act_talk.triggered.connect(self.speak_dialog)
        menu.addSeparator()
        act_voice = menu.addAction("语音开关")
        act_voice.setCheckable(True)
        act_voice.setChecked(self.voice_on)
        act_voice.toggled.connect(self.set_voice)
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

    # ---------------- 语音模块：任意文本 ----------------
    def speak_dialog(self):
        text, ok = QInputDialog.getText(self, "跟尤诺说话",
                                        "想让我说什么？（>80 字或含代码自动跳过语音）")
        if not ok or not text.strip():
            return
        text = text.strip()
        self.bubble_text = text
        self.bubble_end = self._clock + min(6.0, 2.0 + len(text) * 0.06)
        # 长文本 / 代码数据跳过语音规则
        has_code = any(k in text for k in ("{", "}", "def ", "import ", "http://",
                                           "https://", "class ", "=", "()"))
        if len(text) > 80 or has_code or not self.voice_on:
            return  # 只显示文字气泡
        # 系统 TTS 兜底（离线可用；音质为系统默认声线，语气词库才是 AI 音色）
        try:
            safe = text.replace("'", "''")
            script = ("(New-Object -ComObject SAPI.SpVoice).Speak('%s')" % safe)
            subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle",
                              "Hidden", "-Command", script],
                             creationflags=0x08000000)  # CREATE_NO_WINDOW
            self.speaking = True
            self.speak_key = "摸头"   # 用任意包络近似口型
            self.speak_t0 = 0.0
            self.speak_dur = max(1.0, len(text) * 0.18)
        except Exception:
            pass

    def set_voice(self, on):
        self.voice_on = on
        self.voice.enabled = on
        if not on:
            self.voice.stop()

    # ---------------- 跟随鼠标 ----------------
    def _follow_tick(self):
        if not self.follow or self.dragging:
            return
        cursor = QCursor.pos()
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

    # ---------------- 键盘 -> 语气词 ----------------
    def _poll_keys(self):
        if self.key_q.empty():
            return
        vks = []
        while not self.key_q.empty():
            vk = self.key_q.get()
            if vk not in MODIFIER_KEYS:
                vks.append(vk)
        if not vks:
            return
        now = self._clock
        if now - self.last_key_at < 0.8:
            return
        self.last_key_at = now
        # 随机语气词 + 对应情绪
        key = random.choice(list(TONE_LIBRARY.keys()))
        self.trigger(key)

    # ---------------- 置顶 / 退出 ----------------
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
        self.voice.stop()
        self.close()
        QApplication.instance().quit()


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    image_path = resource_path(os.path.join("assets", "iuno_pet.png"))
    voice_dir = resource_path(os.path.join("assets", "voice"))
    try:
        win = PetWindowV2(image_path, voice_dir)
    except Exception as ex:
        ctypes.windll.user32.MessageBoxW(0, str(ex), "尤诺桌宠 v2", 0x10)
        return 1

    # 自检模式：固定位置、关闭跟随、短暂运行后自动退出
    if "--selftest" in sys.argv:
        win.follow = False
        win.voice_on = False
        screen = QGuiApplication.primaryScreen().availableGeometry()
        win._clamp_and_move(screen.center().x() - win.width() // 2,
                            screen.center().y() - win.height() // 2)
        # 自检时依次切换情绪，验证渲染路径不崩溃
        for i, emo in enumerate(EMOTION_ORDER):
            QTimer.singleShot(300 + i * 250, lambda e=emo: win.set_emotion(e))
        QTimer.singleShot(2600, app.quit)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
