# -*- coding: utf-8 -*-
r"""
鸣潮 · 尤诺团子 桌面宠物 V3
- 2.5D QPainter 渲染（径向渐变球体 + 脸部透视变形 + 3D 旋转动画）
- 去头饰重绘尤诺团子 + 三视图素材
- 透明无边框置顶窗口，左键拖动，滚轮缩放
- 六情绪状态机 + 2.5D 形变动画
- 语音模块（QSoundEffect 异步播放，5 条语气词 + 口型联动）
- 二次元风格右键菜单
- 稳定性：无全局键盘钩子，全异常防护，30fps 限帧，资源正确释放
"""
import sys, os, math, random, time, traceback

from PyQt5.QtWidgets import (QApplication, QWidget, QMenu, QAction,
                             QInputDialog, QSystemTrayIcon)
from PyQt5.QtCore import (Qt, QTimer, QPoint, QPointF, QRectF, QSize,
                            pyqtSignal, QUrl, QObject)
from PyQt5.QtGui import (QPainter, QPixmap, QImage, QColor, QFont, QIcon,
                           QCursor, QLinearGradient, QRadialGradient, QBrush,
                           QPen, QPolygonF, QPainterPath, QTransform)
from PyQt5.QtMultimedia import QSoundEffect
from PIL import Image as PILImage

# ============================================================
# 资源路径
# ============================================================
def resource_path(rel):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, rel)
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, '..', rel)

ASSETS = resource_path('assets')
VOICE_DIR = os.path.join(ASSETS, 'voice')
FACE_PATH = os.path.join(ASSETS, 'iuno_face.png')

# ============================================================
# 情绪定义
# ============================================================
EMOTIONS = {
    'calm':     {'name': '平静', 'duration': 0,   'scale': (1.0, 1.0), 'rot': 0,    'bounce': 0.0, 'tint': (255,255,255,0),    'blush': 0.0},
    'happy':    {'name': '开心', 'duration': 2.5, 'scale': (1.06, 0.92), 'rot': 0,    'bounce': 1.0, 'tint': (255,240,250,30),  'blush': 0.6},
    'angry':    {'name': '生气', 'duration': 2.0, 'scale': (1.04, 1.04), 'rot': 0,    'bounce': 0.2, 'tint': (255,200,200,40),  'blush': 0.0},
    'sad':      {'name': '难过', 'duration': 2.5, 'scale': (0.90, 0.90), 'rot': 0,    'bounce': -0.3,'tint': (200,210,255,40),  'blush': 0.0},
    'surprised':{'name': '惊讶', 'duration': 1.5, 'scale': (0.94, 1.10), 'rot': 0,    'bounce': 1.5, 'tint': (255,255,220,30),  'blush': 0.3},
    'tsundere': {'name': '傲娇', 'duration': 3.0, 'scale': (1.0, 1.0),   'rot': -18,  'bounce': 0.1, 'tint': (255,220,240,40),  'blush': 0.85},
}

TONE_MAP = {
    'pat':     {'file': 'pat.wav',   'emotion': 'happy',     'text': '哼~',        'mouth': 0.6},
    'poke':    {'file': 'poke.wav',  'emotion': 'surprised', 'text': '呀！',        'mouth': 1.0},
    'drag':    {'file': 'drag.wav',  'emotion': 'angry',     'text': '喂喂！',      'mouth': 0.8},
    'feed':    {'file': 'feed.wav',  'emotion': 'happy',     'text': '吧唧吧唧',    'mouth': 0.7},
    'sleep':   {'file': 'sleep.wav', 'emotion': 'tsundere',  'text': '不准松开我',  'mouth': 0.5},
}

# ============================================================
# 语音引擎
# ============================================================
class VoiceEngine(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.enabled = True
        self._effects = {}
        self._level = 0.0
        self._level_timer = QTimer(self)
        self._level_timer.timeout.connect(self._decay)
        self._level_timer.start(50)
        for key, info in TONE_MAP.items():
            path = os.path.join(VOICE_DIR, info['file'])
            if os.path.exists(path):
                fx = QSoundEffect(self)
                fx.setSource(QUrl.fromLocalFile(path))
                fx.setVolume(0.8)
                self._effects[key] = fx

    def _decay(self):
        self._level = max(0.0, self._level - 0.08)

    def play(self, key):
        if not self.enabled or key not in self._effects:
            return
        try:
            fx = self._effects[key]
            if fx.isPlaying():
                fx.stop()
            fx.play()
            self._level = TONE_MAP[key]['mouth']
        except Exception:
            pass

    def stop_all(self):
        for fx in self._effects.values():
            try: fx.stop()
            except: pass

    @property
    def mouth_level(self):
        return self._level

# ============================================================
# 2.5D 团子渲染 Widget
# ============================================================
class Pet2DWidget(QWidget):
    emotion_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setMouseTracking(True)

        self._face_pix = None
        self._load_face()

        self._emotion = 'calm'
        self._emotion_start = time.time()
        self._emotion_duration = 0
        self._rot = 0.0          # 水平旋转角度 -45~45
        self._auto_rot = True
        self._time = 0.0
        self._mouth_open = 0.0
        self._target_scale = 1.0
        self._cur_scale = 1.0
        self._voice = None
        self._bubble_text = ''
        self._bubble_time = 0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(33)

    def _load_face(self):
        try:
            if os.path.exists(FACE_PATH):
                self._face_pix = QPixmap(FACE_PATH)
        except Exception as e:
            print(f'[V3] face load error: {e}')

    def set_voice(self, v):
        self._voice = v

    def set_emotion(self, emo):
        if emo not in EMOTIONS:
            return
        self._emotion = emo
        self._emotion_start = time.time()
        self._emotion_duration = EMOTIONS[emo]['duration']
        self.emotion_changed.emit(emo)

    def set_bubble(self, text):
        self._bubble_text = text
        self._bubble_time = time.time()

    def set_scale(self, s):
        self._target_scale = max(0.4, min(3.0, s))

    def paintEvent(self, e):
        try:
            self._render()
        except Exception:
            traceback.print_exc()

    def _render(self):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h * 0.55
        base_r = min(w, h) * 0.38

        self._time += 0.033
        e = EMOTIONS[self._emotion]
        if self._emotion_duration > 0:
            if time.time() - self._emotion_start > self._emotion_duration:
                self._emotion = 'calm'
                e = EMOTIONS['calm']
                self._emotion_duration = 0

        self._cur_scale += (self._target_scale - self._cur_scale) * 0.15

        # 自动旋转（左右摆动）
        if self._auto_rot and self._emotion == 'calm':
            self._rot = math.sin(self._time * 0.7) * 22.0
        else:
            target_rot = e['rot']
            self._rot += (target_rot - self._rot) * 0.1

        # 弹跳
        bounce = e['bounce']
        bounce_y = math.sin(self._time * 8) * 6 * bounce if bounce > 0 else 0
        if self._emotion == 'surprised':
            bounce_y = abs(math.sin(self._time * 10)) * 12
        shake_x = math.sin(self._time * 30) * 2.5 if self._emotion == 'angry' else 0
        breath = 1.0 + math.sin(self._time * 2) * 0.012

        if self._voice:
            self._mouth_open = self._voice.mouth_level

        sx, sy = e['scale']
        r = base_r * sx * breath * self._cur_scale
        ry = base_r * sy * breath * self._cur_scale
        cx += shake_x
        cy += bounce_y

        # ---- 阴影 ----
        shadow_rect = QRectF(cx - r * 0.7, cy + ry * 0.85, r * 1.4, ry * 0.25)
        shadow_grad = QRadialGradient(shadow_rect.center(), r * 0.7)
        shadow_grad.setColorAt(0, QColor(0, 0, 0, 50))
        shadow_grad.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(shadow_grad))
        p.setPen(Qt.NoPen)
        p.drawEllipse(shadow_rect)

        # ---- 球体（径向渐变模拟 3D）----
        sphere_rect = QRectF(cx - r, cy - ry, r * 2, ry * 2)
        sphere_grad = QRadialGradient(QPointF(cx - r * 0.35, cy - ry * 0.4), r * 1.3)
        sphere_grad.setColorAt(0, QColor(140, 180, 255))
        sphere_grad.setColorAt(0.4, QColor(80, 130, 220))
        sphere_grad.setColorAt(0.8, QColor(50, 90, 180))
        sphere_grad.setColorAt(1, QColor(30, 60, 140))
        p.setBrush(QBrush(sphere_grad))
        p.setPen(QPen(QColor(30, 50, 120, 180), 2))
        p.drawEllipse(sphere_rect)

        # ---- 脸部贴图（裁剪到圆 + 水平缩放模拟 3D 旋转）----
        if self._face_pix and not self._face_pix.isNull():
            p.save()
            # 裁剪到球体圆形
            path = QPainterPath()
            path.addEllipse(sphere_rect)
            p.setClipPath(path)

            # 水平缩放模拟旋转：rot 越大脸越扁
            rot_factor = math.cos(math.radians(self._rot))
            face_w = r * 1.7 * max(0.25, abs(rot_factor))
            face_h = ry * 1.7
            face_x = cx - face_w / 2
            face_y = cy - face_h * 0.45

            # 脸部随旋转水平偏移
            face_x += math.sin(math.radians(self._rot)) * r * 0.15

            face_rect = QRectF(face_x, face_y, face_w, face_h)
            p.drawPixmap(face_rect, self._face_pix, QRectF(self._face_pix.rect()))
            p.restore()

        # ---- 情绪色罩 ----
        tr, tg, tb, ta = e['tint']
        if ta > 0:
            p.save()
            path = QPainterPath()
            path.addEllipse(sphere_rect)
            p.setClipPath(path)
            p.fillRect(sphere_rect, QColor(tr, tg, tb, ta))
            p.restore()

        # ---- 腮红 ----
        blush = e['blush']
        if blush > 0:
            p.save()
            p.setBrush(QColor(255, 120, 150, int(100 * blush)))
            p.setPen(Qt.NoPen)
            bw = r * 0.22
            bh = ry * 0.12
            by = cy + ry * 0.15
            p.drawEllipse(QPointF(cx - r * 0.42, by), bw, bh)
            p.drawEllipse(QPointF(cx + r * 0.42, by), bw, bh)
            p.restore()

        # ---- 口型（说话时开合）----
        if self._mouth_open > 0.05 or self._emotion in ('surprised', 'happy'):
            p.save()
            mouth_w = r * 0.12 * (1 + self._mouth_open)
            mouth_h = ry * 0.06 * (1 + self._mouth_open * 2)
            mouth_y = cy + ry * 0.35
            if self._emotion == 'happy':
                # 微笑弧线
                p.setPen(QPen(QColor(120, 40, 60), 2.5))
                p.setBrush(Qt.NoBrush)
                p.drawArc(QRectF(cx - mouth_w * 1.5, mouth_y - mouth_h, mouth_w * 3, mouth_h * 2.5),
                           200 * 16, 140 * 16)
            elif self._emotion == 'surprised':
                p.setBrush(QColor(120, 40, 60))
                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(cx, mouth_y), mouth_w, mouth_h * 1.5)
            else:
                p.setBrush(QColor(120, 40, 60, int(200 * self._mouth_open)))
                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(cx, mouth_y), mouth_w, mouth_h)
            p.restore()

        # ---- 高光（3D 立体感）----
        p.save()
        hl_rect = QRectF(cx - r * 0.5, cy - ry * 0.65, r * 0.45, ry * 0.3)
        hl_grad = QRadialGradient(hl_rect.center(), r * 0.35)
        hl_grad.setColorAt(0, QColor(255, 255, 255, 120))
        hl_grad.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(hl_grad))
        p.setPen(Qt.NoPen)
        p.drawEllipse(hl_rect)
        p.restore()

        # ---- 生气冒烟 ----
        if self._emotion == 'angry':
            p.save()
            p.setBrush(QColor(150, 150, 150, 100))
            p.setPen(Qt.NoPen)
            for i in range(3):
                sx2 = cx - r * 0.3 + i * r * 0.3
                sy2 = cy - ry - 10 - math.sin(self._time * 5 + i) * 8
                p.drawEllipse(QPointF(sx2, sy2), r * 0.08, r * 0.1)
            p.restore()

        # ---- 语音气泡 ----
        if self._bubble_text:
            elapsed = time.time() - self._bubble_time
            if elapsed < 3.0:
                alpha = 1.0 if elapsed < 2.5 else max(0, 1.0 - (elapsed - 2.5) / 0.5)
                bw2 = min(w * 0.75, 180)
                bh2 = 32
                bx = (w - bw2) // 2
                by2 = 4
                p.save()
                grad = QLinearGradient(bx, by2, bx, by2 + bh2)
                grad.setColorAt(0, QColor(255, 250, 255, int(240 * alpha)))
                grad.setColorAt(1, QColor(235, 228, 255, int(235 * alpha)))
                p.setBrush(QBrush(grad))
                p.setPen(QPen(QColor(175, 155, 215, int(200 * alpha)), 1.5))
                p.drawRoundedRect(QRectF(bx, by2, bw2, bh2), 12, 12)
                # 气泡尾巴
                tail = QPolygonF([QPointF(w//2 - 7, by2 + bh2),
                                  QPointF(w//2 + 7, by2 + bh2),
                                  QPointF(w//2, by2 + bh2 + 9)])
                p.drawPolygon(tail)
                p.setPen(QColor(75, 55, 115, int(255 * alpha)))
                f = QFont('Microsoft YaHei', 10, QFont.Bold)
                p.setFont(f)
                p.drawText(QRectF(bx, by2, bw2, bh2), Qt.AlignCenter, self._bubble_text)
                p.restore()

        p.end()

    def cleanup(self):
        try:
            self._timer.stop()
        except Exception:
            pass

# ============================================================
# 二次元菜单
# ============================================================
class AnimeMenu(QMenu):
    def __init__(self, title='', parent=None):
        super().__init__(title, parent)
        self.setStyleSheet("""
            QMenu {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgba(255,245,255,245), stop:1 rgba(230,225,255,240));
                border: 2px solid rgba(180,150,220,200);
                border-radius: 12px; padding: 6px;
            }
            QMenu::item {
                padding: 8px 28px; border-radius: 8px; margin: 2px;
                color: #5a3d7a; font-family: "Microsoft YaHei"; font-size: 10pt;
            }
            QMenu::item:selected {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 rgba(200,170,240,200), stop:1 rgba(230,190,255,200));
                color: #3a1d5a;
            }
            QMenu::separator { height: 1px; background: rgba(180,150,220,100); margin: 4px 12px; }
        """)

# ============================================================
# 主窗口
# ============================================================
class PetWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setMouseTracking(True)

        self._drag_pos = None
        self._drag_moved = False
        self._click_time = 0
        self._double_click = False
        self._follow = True
        self._pet_size = 180
        self._voice = VoiceEngine(self)
        self._pet = Pet2DWidget(self)
        self._pet.set_voice(self._voice)
        h = int(self._pet_size * 1.25)
        self._pet.setFixedSize(self._pet_size, h)
        self.resize(self._pet_size, h)

        self._follow_timer = QTimer(self)
        self._follow_timer.timeout.connect(self._follow_mouse)
        self._follow_timer.start(50)

        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - self.width() - 40, screen.height() - self.height() - 80)
        self._trigger('pat')

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()
            self._drag_moved = False
            self._double_click = False
        elif e.button() == Qt.RightButton:
            self._show_menu(e.globalPos())

    def mouseMoveEvent(self, e):
        if self._drag_pos is not None and e.buttons() & Qt.LeftButton:
            new_pos = e.globalPos() - self._drag_pos
            if (new_pos - self.pos()).manhattanLength() > 8:
                self._drag_moved = True
            self.move(new_pos)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            was_drag = self._drag_moved
            self._drag_pos = None
            self._drag_moved = False
            if was_drag:
                self._trigger('drag')
            else:
                now = time.time()
                if now - self._click_time < 0.28:
                    self._double_click = True
                    self._trigger('pat')
                    self._click_time = 0
                else:
                    self._click_time = now
                    QTimer.singleShot(280, self._check_single)

    def _check_single(self):
        if not self._double_click and self._click_time > 0:
            self._trigger('poke')
        self._double_click = False

    def wheelEvent(self, e):
        delta = e.angleDelta().y() / 120
        self._pet_size = max(80, min(500, self._pet_size + delta * 20))
        h = int(self._pet_size * 1.25)
        self._pet.setFixedSize(self._pet_size, h)
        self.resize(self._pet_size, h)
        self._pet.set_scale(self._pet_size / 180.0)

    def _follow_mouse(self):
        if not self._follow or self._drag_pos is not None:
            return
        try:
            c = QCursor.pos()
            tx = c.x() - self.width() // 2 + 30
            ty = c.y() + 20
            cur = self.pos()
            self.move(int(cur.x() + (tx - cur.x()) * 0.06),
                      int(cur.y() + (ty - cur.y()) * 0.06))
        except Exception:
            pass

    def _trigger(self, key):
        try:
            info = TONE_MAP[key]
            self._pet.set_emotion(info['emotion'])
            self._pet.set_bubble(info['text'])
            self._voice.play(key)
        except Exception:
            traceback.print_exc()

    def _random_tone(self):
        self._trigger(random.choice(list(TONE_MAP.keys())))

    def _show_menu(self, pos):
        menu = AnimeMenu('尤诺团子 v3', self)
        a_feed = menu.addAction('喂食')
        a_sleep = menu.addAction('晚安')
        a_talk = menu.addAction('跟我说话…')
        a_random = menu.addAction('随机语气词')
        menu.addSeparator()
        size_menu = menu.addMenu('调整大小')
        for label, sz in [('小', 120), ('中', 180), ('大', 260), ('超大', 360)]:
            act = size_menu.addAction(label)
            act.triggered.connect(lambda checked, s=sz: self._set_size(s))
        menu.addSeparator()
        a_top = menu.addAction('始终置顶'); a_top.setCheckable(True); a_top.setChecked(True)
        a_follow = menu.addAction('跟随鼠标'); a_follow.setCheckable(True); a_follow.setChecked(self._follow)
        a_voice = menu.addAction('语音开关'); a_voice.setCheckable(True); a_voice.setChecked(self._voice.enabled)
        a_rot = menu.addAction('自动旋转'); a_rot.setCheckable(True); a_rot.setChecked(self._pet._auto_rot)
        menu.addSeparator()
        a_quit = menu.addAction('退出程序')
        action = menu.exec_(pos)
        if action == a_feed: self._trigger('feed')
        elif action == a_sleep: self._trigger('sleep')
        elif action == a_talk: self._talk()
        elif action == a_random: self._random_tone()
        elif action == a_top: self._toggle_top(a_top.isChecked())
        elif action == a_follow: self._follow = a_follow.isChecked()
        elif action == a_voice:
            self._voice.enabled = a_voice.isChecked()
            if not self._voice.enabled: self._voice.stop_all()
        elif action == a_rot: self._pet._auto_rot = a_rot.isChecked()
        elif action == a_quit: self.close()

    def _set_size(self, sz):
        self._pet_size = sz
        h = int(sz * 1.25)
        self._pet.setFixedSize(sz, h)
        self.resize(sz, h)
        self._pet.set_scale(sz / 180.0)

    def _toggle_top(self, on):
        flags = self.windowFlags()
        if on: flags |= Qt.WindowStaysOnTopHint
        else: flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def _talk(self):
        text, ok = QInputDialog.getText(self, '跟尤诺说话', '说点什么吧：')
        if ok and text.strip():
            if len(text) > 80 or any(c in text for c in ['```', 'http', 'import ', 'def ']):
                self._pet.set_bubble(text[:60] + '…')
                self._pet.set_emotion('calm')
            else:
                self._pet.set_bubble(text)
                self._pet.set_emotion('happy')
                try:
                    import subprocess
                    ps = (f'Add-Type -AssemblyName System.Speech; '
                          f'$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
                          f'$s.Rate = 1; $s.Volume = 80; $s.Speak({text!r})')
                    subprocess.Popen(['powershell', '-NoProfile', '-WindowStyle', 'Hidden',
                                      '-Command', ps], creationflags=0x08000000)
                except Exception:
                    pass

    def closeEvent(self, e):
        try:
            self._follow_timer.stop()
            self._voice.stop_all()
            self._pet.cleanup()
        except Exception:
            pass
        super().closeEvent(e)

# ============================================================
def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    if '--selftest' in sys.argv:
        w = PetWindow()
        w.show()
        QTimer.singleShot(3000, app.quit)
        sys.exit(app.exec_())
    w = PetWindow()
    w.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
