"""
V7菜单 - 按效果图重写
深蓝紫星空背景 + 金色主题
左上角尤诺团子动画 + 右上角×关闭
可鼠标拖动
"""
import os
import math
import random
from PyQt5.QtCore import Qt, QTimer, QPoint, QPointF, QSize, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QLinearGradient, QRadialGradient, QFont, QIcon
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSizePolicy, QApplication

ANIMATION_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', 'animations')


class CornerPetWidget(QWidget):
    """菜单左上角尤诺团子动画"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(90, 90)
        self._frames = []
        self._frame_idx = 0
        self._load_frames()
        if self._frames:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._tick)
            self._timer.start(80)

    def _load_frames(self):
        pdir = os.path.join(ANIMATION_DIR, 'corner_pet')
        if not os.path.isdir(pdir):
            return
        files = sorted([f for f in os.listdir(pdir) if f.endswith('.png')])
        for f in files:
            pix = QPixmap(os.path.join(pdir, f))
            if not pix.isNull():
                self._frames.append(pix)

    def _tick(self):
        self._frame_idx = (self._frame_idx + 1) % len(self._frames)
        self.update()

    def paintEvent(self, e):
        if not self._frames:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        pix = self._frames[self._frame_idx]
        scaled = pix.scaled(self.width(), self.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        p.drawPixmap(x, y, scaled)
        p.end()

    def cleanup(self):
        try:
            if hasattr(self, '_timer'):
                self._timer.stop()
        except Exception:
            pass


class V7MenuItem(QWidget):
    """菜单项：图标+文字+右箭头"""
    clicked = pyqtSignal()

    def __init__(self, icon_pix, text, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self.setCursor(Qt.PointingHandCursor)
        self._icon = icon_pix
        self._text = text
        self._hovered = False

    def enterEvent(self, e):
        self._hovered = True
        self.update()

    def leaveEvent(self, e):
        self._hovered = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        # hover背景
        if self._hovered:
            p.setBrush(QColor(212, 175, 55, 30))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(2, 2, self.width()-4, self.height()-4, 8, 8)
        # 图标
        if self._icon and not self._icon.isNull():
            p.drawPixmap(14, 9, self._icon.scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        # 文字
        p.setPen(QColor(220, 200, 160))
        p.setFont(QFont("Microsoft YaHei", 10))
        p.drawText(44, 24, self._text)
        # 右箭头
        p.setPen(QPen(QColor(180, 150, 100), 1.5))
        p.drawLine(self.width()-22, 16, self.width()-14, 19)
        p.drawLine(self.width()-14, 19, self.width()-22, 22)
        p.end()


class V7ToggleItem(QWidget):
    """开关项：图标+文字+月牙开关"""
    toggled = pyqtSignal(bool)

    def __init__(self, icon_pix, text, checked=False, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self.setCursor(Qt.PointingHandCursor)
        self._icon = icon_pix
        self._text = text
        self._checked = checked
        self._hovered = False

    def set_checked(self, val):
        self._checked = val
        self.update()

    def enterEvent(self, e):
        self._hovered = True
        self.update()

    def leaveEvent(self, e):
        self._hovered = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._checked = not self._checked
            self.toggled.emit(self._checked)
            self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        if self._hovered:
            p.setBrush(QColor(212, 175, 55, 30))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(2, 2, self.width()-4, self.height()-4, 8, 8)
        if self._icon and not self._icon.isNull():
            p.drawPixmap(14, 9, self._icon.scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        p.setPen(QColor(220, 200, 160))
        p.setFont(QFont("Microsoft YaHei", 10))
        p.drawText(44, 24, self._text)
        # 月牙开关
        cx = self.width() - 28
        cy = 19
        if self._checked:
            # 满月（金色）
            p.setBrush(QColor(212, 175, 55, 200))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx, cy), 9, 9)
        else:
            # 月牙
            p.setBrush(QColor(100, 90, 120, 150))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx, cy), 9, 9)
            p.setBrush(QColor(30, 25, 55, 255))
            p.drawEllipse(QPointF(cx+4, cy), 8, 8)
        p.end()


class V7Menu(QWidget):
    """V7菜单 - 深蓝紫星空+金色主题，可拖动"""
    closed = pyqtSignal()

    def __init__(self, pet, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self._pet = pet
        self.setFixedWidth(260)
        self._drag_pos = None
        self._outside_timer = QTimer(self)
        self._outside_timer.timeout.connect(self._check_outside)
        self._icons = {}
        self._load_icons()
        self._build_ui()

    def _load_icons(self):
        """加载金色线性图标（用简单绘制代替SVG）"""
        # 用QPixmap绘制简单图标
        def make_icon(draw_func):
            pix = QPixmap(24, 24)
            pix.fill(Qt.transparent)
            p = QPainter(pix)
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setPen(QPen(QColor(212, 175, 55), 1.8))
            p.setBrush(Qt.NoBrush)
            draw_func(p)
            p.end()
            return pix

        # 喂食（碗）
        self._icons['feed'] = make_icon(lambda p: [p.drawArc(4, 6, 16, 12, 0, 180*16), p.drawLine(4, 12, 20, 12)])
        # 晚安（月亮）
        self._icons['sleep'] = make_icon(lambda p: [p.drawArc(6, 4, 14, 16, 90*16, 270*16), p.setBrush(QColor(30,25,55)), p.drawEllipse(10, 5, 10, 14)])
        # 戳脸（手指）
        self._icons['poke'] = make_icon(lambda p: [p.drawEllipse(6, 6, 12, 12), p.drawLine(12, 18, 12, 22), p.drawLine(10, 22, 14, 22)])
        # 随机（音符）
        self._icons['random'] = make_icon(lambda p: [p.drawLine(8, 18, 8, 8), p.drawLine(8, 8, 16, 5), p.drawLine(16, 5, 16, 15), p.drawEllipse(5, 16, 6, 5), p.drawEllipse(13, 13, 6, 5)])
        # 置顶（图钉）
        self._icons['topmost'] = make_icon(lambda p: [p.drawLine(12, 4, 12, 16), p.drawEllipse(9, 3, 6, 6), p.drawLine(8, 16, 16, 16)])
        # 跟随（鼠标）
        self._icons['follow'] = make_icon(lambda p: [p.drawPolygon([QPoint(6,4), QPoint(6,18), QPoint(10,14), QPoint(13,20), QPoint(16,19), QPoint(13,13), QPoint(18,13)])])
        # 语音（音量）
        self._icons['voice'] = make_icon(lambda p: [p.drawRect(4, 9, 4, 6), p.drawPolygon([QPoint(8,8), QPoint(13,4), QPoint(13,20), QPoint(8,16)]), p.drawArc(14, 7, 6, 10, -30*16, 60*16)])
        # API（齿轮）
        self._icons['api'] = make_icon(lambda p: [p.drawEllipse(8, 8, 8, 8), p.drawLine(12, 3, 12, 6), p.drawLine(12, 18, 12, 21), p.drawLine(3, 12, 6, 12), p.drawLine(18, 12, 21, 12)])
        # 帮助（问号）
        self._icons['help'] = make_icon(lambda p: [p.drawEllipse(4, 4, 16, 16), p.drawText(8, 17, '?')])
        # 退出（电源）
        self._icons['quit'] = make_icon(lambda p: [p.drawArc(5, 6, 14, 14, 45*16, 270*16), p.drawLine(12, 4, 12, 12)])
        # 聊天
        self._icons['chat'] = make_icon(lambda p: [p.drawRoundedRect(3, 5, 18, 12, 4, 4), p.drawLine(7, 17, 10, 21), p.drawLine(10, 21, 12, 17)])

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 12)
        layout.setSpacing(2)

        # 顶部区域：左上角团子动画 + 标题 + 关闭按钮
        top = QWidget()
        top.setFixedHeight(80)
        tl = QHBoxLayout(top)
        tl.setContentsMargins(0, 0, 0, 0)
        self._corner_pet = CornerPetWidget()
        tl.addWidget(self._corner_pet)
        tl.addStretch()
        title = QLabel('尤诺团子')
        title.setStyleSheet('color: #d4af37; font-size: 16pt; font-weight: bold; font-family: "Microsoft YaHei";')
        tl.addWidget(title)
        tl.addStretch()
        close_btn = QPushButton('×')
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton { background: rgba(40,35,70,180); color: #d0b0e8; border: 1px solid rgba(212,175,55,100); border-radius: 14px; font-size: 14pt; font-weight: bold; }
            QPushButton:hover { background: rgba(200,80,80,160); color: #fff; border-color: rgba(255,150,150,180); }
        """)
        close_btn.clicked.connect(self.close)
        tl.addWidget(close_btn)
        layout.addWidget(top)

        # 跟我说话主按钮
        main_btn = QPushButton('  跟我说话')
        main_btn.setFixedHeight(42)
        main_btn.setCursor(Qt.PointingHandCursor)
        main_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 rgba(180,140,60,230), stop:0.5 rgba(220,190,100,240), stop:1 rgba(180,140,60,230));
                color: #2a1f0a; border: 1px solid rgba(255,220,130,200); border-radius: 8px;
                font-family: "Microsoft YaHei"; font-size: 12pt; font-weight: bold;
            }
            QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 rgba(200,160,70,250), stop:0.5 rgba(240,210,120,255), stop:1 rgba(200,160,70,250)); }
        """)
        main_btn.setIcon(QIcon(self._icons.get('chat')))
        main_btn.setIconSize(QSize(22, 22))
        main_btn.clicked.connect(lambda: (self.close(), self._pet._open_chat()))
        layout.addWidget(main_btn)
        layout.addSpacing(8)

        # 互动区
        layout.addWidget(self._section_title('互动区'))
        for icon_key, text, key in [('feed','喂食','feed'), ('sleep','晚安','sleep'), ('poke','戳脸','poke')]:
            item = V7MenuItem(self._icons.get(icon_key), text)
            item.clicked.connect(lambda checked=False, k=key: (self.close(), self._pet._trigger(k)))
            layout.addWidget(item)
        layout.addSpacing(6)

        # 外观区
        layout.addWidget(self._section_title('外观区'))
        size_widget = QWidget()
        size_widget.setFixedHeight(34)
        sl = QHBoxLayout(size_widget)
        sl.setContentsMargins(10, 2, 10, 2)
        sl.setSpacing(6)
        self._size_buttons = {}
        for label, sz in [('小',140),('中',200),('大',280)]:
            sb = QPushButton(label)
            sb.setFixedHeight(26)
            sb.setCursor(Qt.PointingHandCursor)
            self._size_buttons[sz] = sb
            sb.clicked.connect(lambda checked=False, s=sz: (self.close(), self._pet._set_size(s)))
            sl.addWidget(sb)
        sl.addStretch()
        layout.addWidget(size_widget)
        self._top_toggle = V7ToggleItem(self._icons.get('topmost'), '始终置顶', self._pet._topmost)
        self._top_toggle.toggled.connect(lambda on: self._pet._toggle_top(on))
        layout.addWidget(self._top_toggle)
        self._follow_toggle = V7ToggleItem(self._icons.get('follow'), '跟随鼠标', self._pet._follow)
        self._follow_toggle.toggled.connect(lambda on: self._pet._toggle_follow(on))
        layout.addWidget(self._follow_toggle)
        layout.addSpacing(6)

        # 系统区
        layout.addWidget(self._section_title('系统区'))
        self._voice_toggle = V7ToggleItem(self._icons.get('voice'), '语音开关', self._pet.cfg.get('tts',{}).get('enabled', True))
        self._voice_toggle.toggled.connect(self._pet._toggle_voice)
        layout.addWidget(self._voice_toggle)
        for icon_key, text, handler in [('help','使用说明','_show_help')]:
            item = V7MenuItem(self._icons.get(icon_key), text)
            item.clicked.connect(lambda checked=False, h=handler: (self.close(), getattr(self._pet, h)()))
            layout.addWidget(item)
        quit_item = V7MenuItem(self._icons.get('quit'), '退出程序')
        quit_item.clicked.connect(lambda: (self.close(), self._pet.close()))
        layout.addWidget(quit_item)
        layout.addSpacing(8)

        # 底部落款
        footer = QLabel('✦  尤 诺 团 子  ✦')
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet('color: rgba(212,175,55,150); font-size: 9pt; font-family: "Microsoft YaHei"; letter-spacing: 4px;')
        layout.addWidget(footer)

        self._update_size_buttons()

    def _section_title(self, text):
        """分区标题：文字+金色分隔线"""
        w = QWidget()
        w.setFixedHeight(24)
        hl = QHBoxLayout(w)
        hl.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(text)
        lbl.setStyleSheet('color: rgba(180,150,100,180); font-size: 9pt; font-family: "Microsoft YaHei";')
        hl.addWidget(lbl)
        line = QLabel()
        line.setFixedHeight(1)
        line.setStyleSheet('background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 rgba(212,175,55,120), stop:1 rgba(212,175,55,0));')
        hl.addWidget(line, 1)
        return w

    def _update_size_buttons(self):
        cur = self._pet._pet_size
        for sz, btn in self._size_buttons.items():
            active = (cur == sz)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {'rgba(212,175,55,200)' if active else 'rgba(50,40,80,150)'};
                    color: {'#2a1f0a' if active else '#b0a0c8'};
                    border: 1px solid {'rgba(255,220,130,200)' if active else 'rgba(100,80,140,100)'};
                    border-radius: 13px; font-size: 9pt; font-family: "Microsoft YaHei";
                    padding: 0px 10px;
                }}
                QPushButton:hover {{ background: {'rgba(230,200,90,230)' if active else 'rgba(212,175,55,90)'}; color: {'#2a1f0a' if active else '#ffe8a0'}; }}
            """)

    def update_states(self):
        if self._top_toggle: self._top_toggle.set_checked(self._pet._topmost)
        if self._follow_toggle: self._follow_toggle.set_checked(self._pet._follow)
        if self._voice_toggle: self._voice_toggle.set_checked(self._pet.cfg.get('tts',{}).get('enabled', True))
        self._update_size_buttons()

    def popup(self, pos):
        self.update_states()
        screen = QApplication.primaryScreen().availableGeometry()
        x = min(pos.x(), screen.right() - self.width() - 5)
        y = min(pos.y(), screen.bottom() - self.height() - 5)
        x = max(x, screen.left() + 5)
        y = max(y, screen.top() + 5)
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        self._outside_timer.start(150)

    def _check_outside(self):
        try:
            if QApplication.mouseButtons() & Qt.LeftButton:
                gp = QCursor.pos()
                if not self.geometry().contains(gp):
                    self.close()
        except Exception:
            pass

    # 鼠标拖动
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() & Qt.LeftButton:
            self.move(e.globalPos() - self._drag_pos)
            e.accept()

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    def paintEvent(self, e):
        try:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing, True)
            w, h = self.width(), self.height()
            # 深蓝紫星空渐变背景
            grad = QLinearGradient(0, 0, w, h)
            grad.setColorAt(0, QColor(18, 14, 42, 252))
            grad.setColorAt(0.4, QColor(28, 20, 58, 252))
            grad.setColorAt(0.7, QColor(35, 24, 68, 252))
            grad.setColorAt(1, QColor(22, 16, 50, 252))
            p.setBrush(grad)
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(0, 0, w, h, 16, 16)
            # 金色内边框
            p.setPen(QPen(QColor(212, 175, 55, 100), 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(2, 2, w-4, h-4, 14, 14)
            # 四角金色圆弧装饰
            p.setPen(QPen(QColor(230, 200, 120, 180), 2))
            cs = 14
            p.drawArc(4, 4, cs*2, cs*2, 90*16, 90*16)
            p.drawArc(w-4-cs*2, 4, cs*2, cs*2, 0, 90*16)
            p.drawArc(4, h-4-cs*2, cs*2, cs*2, 180*16, 90*16)
            p.drawArc(w-4-cs*2, h-4-cs*2, cs*2, cs*2, 270*16, 90*16)
            # 星星
            p.setBrush(QColor(255, 230, 150, 70))
            p.setPen(Qt.NoPen)
            random.seed(42)
            for _ in range(20):
                sx = random.randint(20, w-20)
                sy = random.randint(90, h-30)
                sr = random.uniform(0.4, 1.2)
                p.drawEllipse(QPointF(sx, sy), sr, sr)
            p.end()
        except Exception:
            pass

    def closeEvent(self, e):
        try:
            self._outside_timer.stop()
        except Exception:
            pass
        try:
            if hasattr(self, '_corner_pet') and self._corner_pet:
                self._corner_pet.cleanup()
        except Exception:
            pass
        try:
            self.closed.emit()
        except Exception:
            pass
        # 延迟删除，避免在closeEvent中直接销毁
        QTimer.singleShot(50, self.deleteLater)
        super().closeEvent(e)
