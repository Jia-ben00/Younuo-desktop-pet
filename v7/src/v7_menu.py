"""
V7菜单 - 月夜毛玻璃二次元风格（稳定版）
深蓝紫渐变背景 + 金色主题 + 星光
左上角尤诺团子动画 + 右上角×关闭
可鼠标拖动
简化版：删除随机语气词/超大/API设置
"""
import os
import random
from PyQt5.QtCore import Qt, QTimer, QPoint, QSize, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QLinearGradient, QFont, QIcon
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QApplication

ANIMATION_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', 'animations')


class CornerPetWidget(QWidget):
    """菜单左上角尤诺团子动画"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(80, 80)
        self._frames = []
        self._frame_idx = 0
        self._load_frames()
        if self._frames:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._tick)
            self._timer.start(100)

    def _load_frames(self):
        corner_dir = os.path.join(ANIMATION_DIR, 'corner_pet')
        if not os.path.isdir(corner_dir):
            return
        files = sorted([f for f in os.listdir(corner_dir) if f.endswith('.png')])
        for f in files[:30]:
            pix = QPixmap(os.path.join(corner_dir, f))
            if not pix.isNull():
                self._frames.append(pix)

    def _tick(self):
        self._frame_idx = (self._frame_idx + 1) % len(self._frames)
        self.update()

    def paintEvent(self, event):
        try:
            p = QPainter(self)
            if self._frames:
                pix = self._frames[self._frame_idx]
                p.drawPixmap(0, 0, self.width(), self.height(), pix)
            p.end()
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
        self._hover = False

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

    def paintEvent(self, event):
        try:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing, True)
            # hover背景
            if self._hover:
                p.fillRect(self.rect(), QColor(212, 175, 55, 30))
            # 图标
            if self._icon and not self._icon.isNull():
                p.drawPixmap(14, 9, 20, 20, self._icon)
            # 文字
            p.setPen(QColor(245, 238, 220, 230))
            p.setFont(QFont("Microsoft YaHei", 10))
            p.drawText(44, 24, self._text)
            # 右箭头
            p.setPen(QPen(QColor(212, 175, 55, 150), 1.5))
            p.drawLine(self.width() - 18, 16, self.width() - 12, 19)
            p.drawLine(self.width() - 12, 19, self.width() - 18, 22)
            p.end()
        except Exception:
            pass


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
        self._hover = False

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._checked = not self._checked
            self.update()
            self.toggled.emit(self._checked)

    def setChecked(self, checked):
        self._checked = checked
        self.update()

    def paintEvent(self, event):
        try:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing, True)
            if self._hover:
                p.fillRect(self.rect(), QColor(212, 175, 55, 30))
            if self._icon and not self._icon.isNull():
                p.drawPixmap(14, 9, 20, 20, self._icon)
            p.setPen(QColor(245, 238, 220, 230))
            p.setFont(QFont("Microsoft YaHei", 10))
            p.drawText(44, 24, self._text)
            # 月牙开关
            cx = self.width() - 28
            cy = 19
            if self._checked:
                # 满月
                p.setBrush(QColor(212, 175, 55, 220))
                p.setPen(Qt.NoPen)
                p.drawEllipse(cx - 10, cy - 8, 20, 16)
            else:
                # 月牙
                p.setBrush(QColor(100, 90, 130, 180))
                p.setPen(Qt.NoPen)
                p.drawEllipse(cx - 10, cy - 8, 20, 16)
                p.setBrush(QColor(30, 25, 55, 255))
                p.drawEllipse(cx - 6, cy - 8, 16, 16)
            p.end()
        except Exception:
            pass


class V7Menu(QWidget):
    """V7主菜单 - 月夜毛玻璃风格"""

    def __init__(self, pet, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self._pet = pet
        self.setFixedWidth(260)
        self._drag_pos = None
        self._outside_timer = QTimer(self)
        self._outside_timer.timeout.connect(self._check_outside)
        self._icons = {}
        self._stars = []
        self._init_stars()
        self._load_icons()
        self._build_ui()
        self.setAttribute(Qt.WA_TranslucentBackground)

    def _init_stars(self):
        rnd = random.Random(42)
        for _ in range(25):
            self._stars.append((rnd.randint(5, 250), rnd.randint(5, 800), rnd.randint(1, 2), rnd.randint(40, 120)))

    def _load_icons(self):
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

        self._icons['feed'] = make_icon(lambda p: [p.drawArc(4, 6, 16, 12, 0, 180*16), p.drawLine(4, 12, 20, 12)])
        self._icons['sleep'] = make_icon(lambda p: [p.drawArc(6, 4, 14, 16, 90*16, 270*16), p.setBrush(QColor(30,25,55)), p.drawEllipse(10, 5, 10, 14)])
        self._icons['poke'] = make_icon(lambda p: [p.drawEllipse(6, 6, 12, 12), p.drawLine(12, 18, 12, 22), p.drawLine(10, 22, 14, 22)])
        self._icons['topmost'] = make_icon(lambda p: [p.drawLine(12, 4, 12, 16), p.drawEllipse(9, 3, 6, 6), p.drawLine(8, 16, 16, 16)])
        self._icons['follow'] = make_icon(lambda p: [p.drawPolygon([QPoint(6,4), QPoint(6,18), QPoint(10,14), QPoint(13,20), QPoint(16,19), QPoint(13,13), QPoint(18,13)])])
        self._icons['voice'] = make_icon(lambda p: [p.drawRect(4, 9, 4, 6), p.drawPolygon([QPoint(8,8), QPoint(13,4), QPoint(13,20), QPoint(8,16)]), p.drawArc(14, 7, 6, 10, -30*16, 60*16)])
        self._icons['help'] = make_icon(lambda p: [p.drawEllipse(4, 4, 16, 16), p.drawText(8, 17, '?')])
        self._icons['quit'] = make_icon(lambda p: [p.drawArc(5, 6, 14, 14, 45*16, 270*16), p.drawLine(12, 4, 12, 12)])
        self._icons['chat'] = make_icon(lambda p: [p.drawRoundedRect(3, 5, 18, 12, 4, 4), p.drawLine(7, 17, 10, 21), p.drawLine(10, 21, 12, 17)])

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)

        # 顶部：团子动画 + 标题 + 关闭
        top = QWidget()
        top.setFixedHeight(72)
        tl = QHBoxLayout(top)
        tl.setContentsMargins(0, 0, 0, 0)
        self._corner_pet = CornerPetWidget()
        tl.addWidget(self._corner_pet)
        tl.addStretch()
        title = QLabel('尤诺团子')
        title.setStyleSheet('color: #d4af37; font-size: 15pt; font-weight: bold; font-family: "Microsoft YaHei";')
        tl.addWidget(title)
        tl.addStretch()
        close_btn = QPushButton('×')
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton { background: rgba(40,35,70,180); color: #d0b0e8; border: 1px solid rgba(212,175,55,100); border-radius: 13px; font-size: 13pt; font-weight: bold; }
            QPushButton:hover { background: rgba(200,80,80,160); color: #fff; }
        """)
        close_btn.clicked.connect(self.close)
        tl.addWidget(close_btn)
        layout.addWidget(top)
        layout.addSpacing(4)

        # 跟我说话主按钮
        main_btn = QPushButton('  跟我说话')
        main_btn.setFixedHeight(40)
        main_btn.setCursor(Qt.PointingHandCursor)
        main_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 rgba(180,140,60,230), stop:0.5 rgba(220,190,100,240), stop:1 rgba(180,140,60,230));
                color: #2a1f0a; border: 1px solid rgba(255,220,130,200); border-radius: 8px;
                font-family: "Microsoft YaHei"; font-size: 11pt; font-weight: bold;
            }
            QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 rgba(200,160,70,250), stop:0.5 rgba(240,210,120,255), stop:1 rgba(200,160,70,250)); }
        """)
        main_btn.setIcon(QIcon(self._icons.get('chat')))
        main_btn.setIconSize(QSize(20, 20))
        main_btn.clicked.connect(lambda: (self.close(), self._pet._open_chat()))
        layout.addWidget(main_btn)
        layout.addSpacing(6)

        # 互动区
        layout.addWidget(self._section_title('互动区'))
        for icon_key, text, key in [('feed','喂食','feed'), ('sleep','晚安','sleep'), ('poke','戳脸','poke')]:
            item = V7MenuItem(self._icons.get(icon_key), text)
            item.clicked.connect(lambda k=key: (self.close(), self._pet._trigger(k)))
            layout.addWidget(item)
        layout.addSpacing(4)

        # 外观区
        layout.addWidget(self._section_title('外观区'))
        size_widget = QWidget()
        size_widget.setFixedHeight(32)
        sl = QHBoxLayout(size_widget)
        sl.setContentsMargins(10, 2, 10, 2)
        sl.setSpacing(6)
        self._size_buttons = {}
        for label, sz in [('小',140),('中',200),('大',280)]:
            sb = QPushButton(label)
            sb.setFixedHeight(24)
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
        layout.addSpacing(4)

        # 系统区
        layout.addWidget(self._section_title('系统区'))
        self._voice_toggle = V7ToggleItem(self._icons.get('voice'), '语音开关', self._pet.cfg.get('tts',{}).get('enabled', True))
        self._voice_toggle.toggled.connect(self._pet._toggle_voice)
        layout.addWidget(self._voice_toggle)
        help_item = V7MenuItem(self._icons.get('help'), '使用说明')
        help_item.clicked.connect(lambda: (self.close(), self._pet._show_help()))
        layout.addWidget(help_item)
        quit_item = V7MenuItem(self._icons.get('quit'), '退出程序')
        quit_item.clicked.connect(lambda: (self.close(), self._pet.close()))
        layout.addWidget(quit_item)
        layout.addSpacing(6)

        # 底部落款
        footer = QLabel('✦  尤 诺 团 子  ✦')
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet('color: rgba(212,175,55,130); font-size: 8pt; font-family: "Microsoft YaHei"; letter-spacing: 3px;')
        layout.addWidget(footer)

        self._update_size_buttons()
        self.adjustSize()

    def _section_title(self, text):
        w = QWidget()
        w.setFixedHeight(22)
        hl = QHBoxLayout(w)
        hl.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(text)
        lbl.setStyleSheet('color: rgba(180,150,100,170); font-size: 8pt; font-family: "Microsoft YaHei";')
        hl.addWidget(lbl)
        line = QLabel()
        line.setFixedHeight(1)
        line.setStyleSheet('background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 rgba(212,175,55,100), stop:1 rgba(212,175,55,0));')
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
                    border-radius: 12px; font-size: 8pt; font-family: "Microsoft YaHei";
                    padding: 0px 8px;
                }}
                QPushButton:hover {{ background: {'rgba(230,190,80,230)' if active else 'rgba(70,55,100,180)'}; }}
            """)

    def paintEvent(self, event):
        try:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing, True)
            # 背景渐变（用QLinearGradient，不用QRadialGradient避免崩溃）
            g = QLinearGradient(0, 0, 0, self.height())
            g.setColorAt(0.0, QColor(11, 10, 34, 235))
            g.setColorAt(0.55, QColor(26, 20, 64, 235))
            g.setColorAt(1.0, QColor(42, 27, 74, 235))
            p.setBrush(g)
            p.setPen(QPen(QColor(212, 175, 55, 120), 1.5))
            p.drawRoundedRect(2, 2, self.width() - 4, self.height() - 4, 16, 16)
            # 星光（整数坐标）
            p.setPen(Qt.NoPen)
            for x, y, r, a in self._stars:
                if y < self.height():
                    p.setBrush(QColor(255, 240, 200, a))
                    p.drawEllipse(x, y, r, r)
            p.end()
        except Exception:
            pass

    def popup(self, pos):
        """显示菜单（V7Menu是QWidget不是QMenu，用move+show）"""
        screen = QApplication.primaryScreen().availableGeometry()
        x = pos.x()
        y = pos.y()
        if x + self.width() > screen.right():
            x = screen.right() - self.width()
        if y + self.height() > screen.bottom():
            y = screen.bottom() - self.height()
        if x < screen.left():
            x = screen.left()
        if y < screen.top():
            y = screen.top()
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        self._outside_timer.start(200)

    def _check_outside(self):
        try:
            if not self.isVisible():
                self._outside_timer.stop()
                return
            cursor_pos = QApplication.desktop().cursor().pos()
            if not self.geometry().contains(cursor_pos):
                # 检查是否在桌宠窗口上
                pet_geo = self._pet.geometry() if hasattr(self._pet, 'geometry') else None
                if pet_geo and pet_geo.contains(cursor_pos):
                    return
                self.close()
        except Exception:
            pass

    def closeEvent(self, event):
        self._outside_timer.stop()
        # 显式停止子组件定时器，避免销毁时仍触发导致崩溃
        if hasattr(self, '_corner_pet') and self._corner_pet:
            if hasattr(self._corner_pet, '_timer') and self._corner_pet._timer:
                self._corner_pet._timer.stop()
        super().closeEvent(event)

    # 鼠标拖动
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
