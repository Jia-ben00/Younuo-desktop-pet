"""
V10菜单 - 月夜毛玻璃二次元风格（基于V9稳定版）
去掉跟我说话和互动区，添加等级+好感度成长界面
深蓝紫渐变背景 + 金色主题 + 星光
左上角尤诺团子动画 + 右上角×关闭
可鼠标拖动
"""
import os
import sys
import random
from PyQt5.QtCore import Qt, QTimer, QPoint, QSize, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QLinearGradient, QFont, QIcon
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QApplication, QProgressBar

def resource_path(rel):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, rel)
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), rel)

ANIMATION_DIR = resource_path(os.path.join('assets', 'animations'))


class CornerPetWidget(QWidget):
    """菜单左上角尤诺团子动画（corner_pet 40帧）"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(80, 80)
        self._frames = []
        self._frame_idx = 0
        self._timer = None
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
        for f in files[:40]:
            pix = QPixmap(os.path.join(corner_dir, f))
            if not pix.isNull():
                self._frames.append(pix)

    def _tick(self):
        if self._frames:
            self._frame_idx = (self._frame_idx + 1) % len(self._frames)
            self.update()

    def stop(self):
        if self._timer:
            self._timer.stop()

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
            if self._hover:
                p.fillRect(self.rect(), QColor(212, 175, 55, 30))
            if self._icon and not self._icon.isNull():
                p.drawPixmap(14, 9, 20, 20, self._icon)
            p.setPen(QColor(245, 238, 220, 230))
            p.setFont(QFont("Microsoft YaHei", 10))
            p.drawText(44, 24, self._text)
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
            cx = self.width() - 28
            cy = 19
            if self._checked:
                p.setBrush(QColor(212, 175, 55, 220))
                p.setPen(Qt.NoPen)
                p.drawEllipse(cx - 10, cy - 8, 20, 16)
            else:
                p.setBrush(QColor(100, 90, 130, 180))
                p.setPen(Qt.NoPen)
                p.drawEllipse(cx - 10, cy - 8, 20, 16)
                p.setBrush(QColor(30, 25, 55, 255))
                p.drawEllipse(cx - 6, cy - 8, 16, 16)
            p.end()
        except Exception:
            pass


class GrowthPanel(QWidget):
    """等级+好感度成长面板"""
    def __init__(self, pet, parent=None):
        super().__init__(parent)
        self._pet = pet
        self.setFixedHeight(130)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(4)

        # 等级行
        level_row = QHBoxLayout()
        level_row.setContentsMargins(0, 0, 0, 0)
        self._level_label = QLabel('Lv.1')
        self._level_label.setStyleSheet('color: #FFD700; font-size: 12pt; font-weight: bold; font-family: "Microsoft YaHei";')
        level_row.addWidget(self._level_label)
        level_row.addStretch()
        self._food_label = QLabel('月亮糕: 5')
        self._food_label.setStyleSheet('color: #E0E0FF; font-size: 9pt; font-family: "Microsoft YaHei";')
        level_row.addWidget(self._food_label)
        layout.addLayout(level_row)

        # 经验条
        self._exp_bar = QProgressBar()
        self._exp_bar.setFixedHeight(10)
        self._exp_bar.setTextVisible(False)
        self._exp_bar.setStyleSheet("""
            QProgressBar { background: rgba(50,40,80,150); border: 1px solid rgba(212,175,55,100); border-radius: 5px; }
            QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #FFD700, stop:1 #FFA500); border-radius: 4px; }
        """)
        layout.addWidget(self._exp_bar)

        # 好感度行
        aff_row = QHBoxLayout()
        aff_row.setContentsMargins(0, 0, 0, 0)
        self._aff_label = QLabel('陌生')
        self._aff_label.setStyleSheet('color: #B0E0FF; font-size: 10pt; font-weight: bold; font-family: "Microsoft YaHei";')
        aff_row.addWidget(self._aff_label)
        aff_row.addStretch()
        self._aff_value = QLabel('0/100')
        self._aff_value.setStyleSheet('color: #B0B0D0; font-size: 8pt; font-family: "Microsoft YaHei";')
        aff_row.addWidget(self._aff_value)
        layout.addLayout(aff_row)

        # 好感度条
        self._aff_bar = QProgressBar()
        self._aff_bar.setFixedHeight(10)
        self._aff_bar.setTextVisible(False)
        self._aff_bar.setStyleSheet("""
            QProgressBar { background: rgba(50,40,80,150); border: 1px solid rgba(176,224,255,100); border-radius: 5px; }
            QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #87CEEB, stop:1 #FF69B4); border-radius: 4px; }
        """)
        layout.addWidget(self._aff_bar)

        # 喂食按钮
        self._feed_btn = QPushButton('  喂食月亮糕')
        self._feed_btn.setFixedHeight(28)
        self._feed_btn.setCursor(Qt.PointingHandCursor)
        self._feed_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 rgba(180,140,60,200), stop:1 rgba(220,190,100,220));
                color: #2a1f0a; border: 1px solid rgba(255,220,130,180); border-radius: 6px;
                font-family: "Microsoft YaHei"; font-size: 9pt; font-weight: bold;
            }
            QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 rgba(200,160,70,230), stop:1 rgba(240,210,120,240)); }
            QPushButton:disabled { background: rgba(80,70,100,150); color: #808090; border-color: rgba(100,90,130,100); }
        """)
        self._feed_btn.clicked.connect(self._on_feed)
        layout.addWidget(self._feed_btn)

    def _on_feed(self):
        self._pet.interact('feed')
        self.update_info()

    def update_info(self):
        try:
            g = self._pet.growth
            a = self._pet.affection
            self._level_label.setText(f'Lv.{g.level}')
            self._food_label.setText(f'月亮糕: {g.food}')
            exp_needed = g.exp_needed()
            exp_pct = int(g.exp * 100 / exp_needed) if exp_needed > 0 else 0
            self._exp_bar.setValue(exp_pct)
            tier_name, _ = a.get_affection_tier(a.affection) if hasattr(a, 'get_affection_tier') else (a.get_tier_name(), 0)
            self._aff_label.setText(tier_name)
            self._aff_value.setText(f'{a.affection}/100')
            self._aff_bar.setValue(a.affection)
            self._feed_btn.setEnabled(g.can_feed())
        except Exception:
            pass


class V7Menu(QWidget):
    """V10主菜单 - 月夜毛玻璃风格（成长版）"""
    closed = pyqtSignal()

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

        self._icons['topmost'] = make_icon(lambda p: [p.drawLine(12, 4, 12, 16), p.drawEllipse(9, 3, 6, 6), p.drawLine(8, 16, 16, 16)])
        self._icons['follow'] = make_icon(lambda p: [p.drawPolygon([QPoint(6,4), QPoint(6,18), QPoint(10,14), QPoint(13,20), QPoint(16,19), QPoint(13,13), QPoint(18,13)])])
        self._icons['voice'] = make_icon(lambda p: [p.drawRect(4, 9, 4, 6), p.drawPolygon([QPoint(8,8), QPoint(13,4), QPoint(13,20), QPoint(8,16)]), p.drawArc(14, 7, 6, 10, -30*16, 60*16)])
        self._icons['help'] = make_icon(lambda p: [p.drawEllipse(4, 4, 16, 16), p.drawText(8, 17, '?')])
        self._icons['quit'] = make_icon(lambda p: [p.drawArc(5, 6, 14, 14, 45*16, 270*16), p.drawLine(12, 4, 12, 12)])

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

        # 成长区（等级+好感度）
        layout.addWidget(self._section_title('成长区'))
        self._growth_panel = GrowthPanel(self._pet)
        layout.addWidget(self._growth_panel)
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
            sb.clicked.connect(lambda checked=False, s=sz: (self.close(), self._pet.setFixedSize(s, s)))
            sl.addWidget(sb)
        sl.addStretch()
        layout.addWidget(size_widget)
        self._top_toggle = V7ToggleItem(self._icons.get('topmost'), '始终置顶', True)
        self._top_toggle.toggled.connect(lambda on: self._pet._toggle_topmost(on))
        layout.addWidget(self._top_toggle)
        layout.addSpacing(4)

        # 系统区
        layout.addWidget(self._section_title('系统区'))
        self._voice_toggle = V7ToggleItem(self._icons.get('voice'), '语音开关', self._pet.voice.enabled)
        self._voice_toggle.toggled.connect(self._pet.voice.set_enabled)
        layout.addWidget(self._voice_toggle)
        quit_item = V7MenuItem(self._icons.get('quit'), '退出程序')
        quit_item.clicked.connect(lambda: (self.close(), QApplication.instance().quit()))
        layout.addWidget(quit_item)
        layout.addSpacing(6)

        # 底部落款
        footer = QLabel('✦  尤 诺 团 子  ✦')
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet('color: rgba(212,175,55,130); font-size: 8pt; font-family: "Microsoft YaHei"; letter-spacing: 3px;')
        layout.addWidget(footer)

        self._update_size_buttons()
        self._growth_panel.update_info()
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
        cur = self._pet.width()
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
            g = QLinearGradient(0, 0, 0, self.height())
            g.setColorAt(0.0, QColor(11, 10, 34, 235))
            g.setColorAt(0.55, QColor(26, 20, 64, 235))
            g.setColorAt(1.0, QColor(42, 27, 74, 235))
            p.setBrush(g)
            p.setPen(QPen(QColor(212, 175, 55, 120), 1.5))
            p.drawRoundedRect(2, 2, self.width() - 4, self.height() - 4, 16, 16)
            p.setPen(Qt.NoPen)
            for x, y, r, a in self._stars:
                if y < self.height():
                    p.setBrush(QColor(255, 240, 200, a))
                    p.drawEllipse(x, y, r, r)
            p.end()
        except Exception:
            pass

    def popup(self, pos):
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
        self._growth_panel.update_info()
        self._outside_timer.start(200)

    def _check_outside(self):
        try:
            if not self.isVisible():
                self._outside_timer.stop()
                return
            cursor_pos = QApplication.desktop().cursor().pos()
            if not self.geometry().contains(cursor_pos):
                pet_geo = self._pet.geometry() if hasattr(self._pet, 'geometry') else None
                if pet_geo and pet_geo.contains(cursor_pos):
                    return
                self.close()
        except Exception:
            pass

    def closeEvent(self, event):
        self._outside_timer.stop()
        if hasattr(self, '_corner_pet') and self._corner_pet:
            self._corner_pet.stop()
        self.closed.emit()
        super().closeEvent(event)

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
