"""
V10菜单 - 月夜毛玻璃二次元风格（养成版）
参考设计：等级徽章+好感度5档分段+月亮糕+告白解锁
深蓝紫渐变背景 + 金色主题 + 星光
左上角尤诺团子动画 + 右上角×关闭
可鼠标拖动
"""
import os
import sys
import random
from PyQt5.QtCore import Qt, QTimer, QPoint, QSize, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QLinearGradient, QFont, QIcon
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                             QApplication, QProgressBar, QFrame)

def resource_path(rel):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, rel)
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), rel)

ANIMATION_DIR = resource_path(os.path.join('assets', 'animations'))

AFFECTION_TIERS = ['疏离', '熟悉', '亲近', '心动', '倾心']


class CornerPetWidget(QWidget):
    """菜单左上角尤诺团子动画（corner_pet 40帧）"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(72, 72)
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


class BadgeLabel(QLabel):
    """徽章标签（圆角背景）"""
    def __init__(self, text, color, parent=None):
        super().__init__(text, parent)
        self._color = color
        self.setStyleSheet(f"""
            QLabel {{
                background: {color};
                color: #fff;
                border-radius: 10px;
                padding: 2px 10px;
                font-size: 9pt;
                font-weight: bold;
                font-family: "Microsoft YaHei";
            }}
        """)
        self.setFixedHeight(22)


class TieredProgressBar(QWidget):
    """分段进度条（好感度5档）"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(14)
        self._value = 0
        self._tiers = 5

    def setValue(self, value):
        self._value = value
        self.update()

    def paintEvent(self, event):
        try:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing, True)
            w = self.width()
            h = self.height()
            tier_w = w / self._tiers

            # 背景分段
            for i in range(self._tiers):
                x = int(i * tier_w)
                tw = int(tier_w) - 1
                p.setBrush(QColor(60, 50, 90, 150))
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(x, 0, tw, h, 4, 4)

            # 进度（粉色渐变）
            fill_w = int(w * self._value / 100)
            if fill_w > 0:
                grad = QLinearGradient(0, 0, fill_w, 0)
                grad.setColorAt(0, QColor(255, 150, 180))
                grad.setColorAt(1, QColor(255, 100, 150))
                p.setBrush(grad)
                p.drawRoundedRect(0, 0, fill_w, h, 4, 4)

            # 分段线
            p.setPen(QPen(QColor(30, 25, 55, 200), 1))
            for i in range(1, self._tiers):
                x = int(i * tier_w)
                p.drawLine(x, 1, x, h - 1)

            p.end()
        except Exception:
            pass


class GrowthPanel(QWidget):
    """养成状态面板（等级+好感度+月亮糕+告白解锁）"""
    feed_clicked = pyqtSignal()

    def __init__(self, pet, parent=None):
        super().__init__(parent)
        self._pet = pet
        self.setFixedHeight(210)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(5)

        # 养成状态标题
        title = QLabel('✦  养 成 状 态  ✦')
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet('color: #FFD700; font-size: 10pt; font-weight: bold; font-family: "Microsoft YaHei"; letter-spacing: 2px;')
        layout.addWidget(title)

        # 等级行
        level_row = QHBoxLayout()
        level_row.setContentsMargins(0, 0, 0, 0)
        self._level_badge = QLabel('Lv.1')
        self._level_badge.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #DAA520, stop:1 #FFD700);
                color: #2a1f0a; border-radius: 10px;
                padding: 2px 10px; font-size: 9pt; font-weight: bold;
                font-family: "Microsoft YaHei";
            }
        """)
        self._level_badge.setFixedHeight(22)
        level_row.addWidget(self._level_badge)
        self._level_exp = QLabel('0/100 EXP')
        self._level_exp.setStyleSheet('color: #E0E0FF; font-size: 9pt; font-family: "Microsoft YaHei";')
        level_row.addWidget(self._level_exp)
        level_row.addStretch()
        layout.addLayout(level_row)

        # 等级进度条（金色渐变）
        self._exp_bar = QProgressBar()
        self._exp_bar.setFixedHeight(12)
        self._exp_bar.setTextVisible(False)
        self._exp_bar.setStyleSheet("""
            QProgressBar { background: rgba(50,40,80,180); border: 1px solid rgba(212,175,55,100); border-radius: 6px; }
            QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #DAA520, stop:0.5 #FFD700, stop:1 #FFA500); border-radius: 5px; }
        """)
        layout.addWidget(self._exp_bar)

        # 好感度行
        aff_row = QHBoxLayout()
        aff_row.setContentsMargins(0, 0, 0, 0)
        self._aff_badge = QLabel('💗 疏离')
        self._aff_badge.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #FF69B4, stop:1 #FFB6C1);
                color: #fff; border-radius: 10px;
                padding: 2px 10px; font-size: 9pt; font-weight: bold;
                font-family: "Microsoft YaHei";
            }
        """)
        self._aff_badge.setFixedHeight(22)
        aff_row.addWidget(self._aff_badge)
        self._aff_value = QLabel('0/100')
        self._aff_value.setStyleSheet('color: #FFB6C1; font-size: 9pt; font-family: "Microsoft YaHei";')
        aff_row.addWidget(self._aff_value)
        aff_row.addStretch()
        layout.addLayout(aff_row)

        # 好感度分段进度条
        self._aff_bar = TieredProgressBar()
        layout.addWidget(self._aff_bar)

        # 好感度档位标签
        tier_labels = QHBoxLayout()
        tier_labels.setContentsMargins(0, 0, 0, 0)
        tier_labels.setSpacing(0)
        for i, tier in enumerate(AFFECTION_TIERS):
            lbl = QLabel(tier)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet('color: rgba(180,160,200,150); font-size: 7pt; font-family: "Microsoft YaHei";')
            tier_labels.addWidget(lbl)
        layout.addLayout(tier_labels)

        # 月亮糕 + 喂食按钮
        food_row = QHBoxLayout()
        food_row.setContentsMargins(0, 2, 0, 2)
        self._food_label = QLabel('🥮 月亮糕 × 0')
        self._food_label.setStyleSheet('color: #FFE4B5; font-size: 10pt; font-family: "Microsoft YaHei";')
        food_row.addWidget(self._food_label)
        self._food_max = QLabel('(上限30)')
        self._food_max.setStyleSheet('color: rgba(180,160,200,120); font-size: 8pt; font-family: "Microsoft YaHei";')
        food_row.addWidget(self._food_max)
        food_row.addStretch()
        self._feed_btn = QPushButton('喂食 +10')
        self._feed_btn.setFixedHeight(28)
        self._feed_btn.setCursor(Qt.PointingHandCursor)
        self._feed_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #DAA520, stop:0.5 #FFD700, stop:1 #DAA520);
                color: #2a1f0a; border: 1px solid rgba(255,220,130,200);
                border-radius: 14px; font-family: "Microsoft YaHei";
                font-size: 9pt; font-weight: bold; padding: 0px 14px;
            }
            QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #FFD700, stop:0.5 #FFEC8B, stop:1 #FFD700); }
            QPushButton:disabled { background: rgba(80,70,100,150); color: #808090; border-color: rgba(100,90,130,100); }
        """)
        self._feed_btn.clicked.connect(self.feed_clicked.emit)
        food_row.addWidget(self._feed_btn)
        layout.addLayout(food_row)

        # 告白解锁
        conf_row = QHBoxLayout()
        conf_row.setContentsMargins(0, 2, 0, 2)
        conf_title = QLabel('💍 告白解锁')
        conf_title.setStyleSheet('color: #DDA0DD; font-size: 9pt; font-family: "Microsoft YaHei";')
        conf_row.addWidget(conf_title)
        conf_row.addStretch()
        self._conf_status = QLabel('等级 Lv1 / 好感 0')
        self._conf_status.setStyleSheet('color: rgba(221,160,221,150); font-size: 8pt; font-family: "Microsoft YaHei";')
        conf_row.addWidget(self._conf_status)
        layout.addLayout(conf_row)

        # 告白总进度条（粉紫渐变）
        self._conf_bar = QProgressBar()
        self._conf_bar.setFixedHeight(10)
        self._conf_bar.setTextVisible(False)
        self._conf_bar.setStyleSheet("""
            QProgressBar { background: rgba(50,40,80,180); border: 1px solid rgba(221,160,221,100); border-radius: 5px; }
            QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #FF69B4, stop:0.5 #DDA0DD, stop:1 #9370DB); border-radius: 4px; }
        """)
        layout.addWidget(self._conf_bar)

    def update_info(self):
        try:
            g = self._pet.growth
            a = self._pet.affection
            # 等级
            self._level_badge.setText(f'Lv.{g.level}')
            exp_needed = g.exp_needed()
            self._level_exp.setText(f'{g.exp}/{exp_needed} EXP')
            exp_pct = int(g.exp * 100 / exp_needed) if exp_needed > 0 else 0
            self._exp_bar.setValue(exp_pct)
            # 好感度
            tier_name, tier_idx = get_affection_tier(a.affection)
            self._aff_badge.setText(f'💗 {tier_name}')
            self._aff_value.setText(f'{a.affection}/100')
            self._aff_bar.setValue(a.affection)
            # 月亮糕
            self._food_label.setText(f'🥮 月亮糕 × {g.food}')
            self._feed_btn.setEnabled(g.can_feed())
            # 告白解锁
            level_ok = g.level >= 20
            aff_ok = a.affection >= 100
            level_mark = '✓' if level_ok else '✗'
            aff_mark = '✓' if aff_ok else '✗'
            self._conf_status.setText(f'{level_mark}等级 Lv20 / {aff_mark}好感 100')
            conf_pct = int((min(g.level, 20) / 20 * 50) + (a.affection / 100 * 50))
            self._conf_bar.setValue(conf_pct)
        except Exception:
            pass


def get_affection_tier(affection):
    tiers = [(0, 19, '疏离', 0), (20, 49, '熟悉', 1), (50, 79, '亲近', 2), (80, 99, '心动', 3), (100, 100, '倾心', 4)]
    for lo, hi, name, idx in tiers:
        if lo <= affection <= hi:
            return name, idx
    return '疏离', 0


class V7MenuItem(QWidget):
    """菜单项：图标+文字+右箭头"""
    clicked = pyqtSignal()

    def __init__(self, icon_text, text, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self.setCursor(Qt.PointingHandCursor)
        self._icon = icon_text
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
            # 图标（emoji）
            p.setFont(QFont("Microsoft YaHei", 11))
            p.drawText(14, 25, self._icon)
            # 文字
            p.setPen(QColor(245, 238, 220, 230))
            p.setFont(QFont("Microsoft YaHei", 10))
            p.drawText(40, 24, self._text)
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

    def __init__(self, icon_text, text, checked=False, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self.setCursor(Qt.PointingHandCursor)
        self._icon = icon_text
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
            p.setFont(QFont("Microsoft YaHei", 11))
            p.drawText(14, 25, self._icon)
            p.setPen(QColor(245, 238, 220, 230))
            p.setFont(QFont("Microsoft YaHei", 10))
            p.drawText(40, 24, self._text)
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


class V7Menu(QWidget):
    """V10主菜单 - 月夜毛玻璃风格（养成版）"""
    closed = pyqtSignal()

    def __init__(self, pet, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self._pet = pet
        self.setFixedWidth(260)
        self._drag_pos = None
        self._outside_timer = QTimer(self)
        self._outside_timer.timeout.connect(self._check_outside)
        self._stars = []
        self._init_stars()
        self._build_ui()
        self.setAttribute(Qt.WA_TranslucentBackground)

    def _init_stars(self):
        rnd = random.Random(42)
        for _ in range(25):
            self._stars.append((rnd.randint(5, 260), rnd.randint(5, 900), rnd.randint(1, 2), rnd.randint(40, 120)))

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
        title_layout = QVBoxLayout()
        title_layout.setContentsMargins(0, 5, 0, 0)
        title = QLabel('尤诺团子')
        title.setStyleSheet('color: #FFD700; font-size: 15pt; font-weight: bold; font-family: "Microsoft YaHei";')
        title_layout.addWidget(title)
        subtitle = QLabel('谕女·月食诞生')
        subtitle.setStyleSheet('color: rgba(200,180,220,150); font-size: 8pt; font-family: "Microsoft YaHei";')
        title_layout.addWidget(subtitle)
        tl.addLayout(title_layout)
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
        layout.addSpacing(2)

        # 成长区
        layout.addWidget(self._section_title('成长区'))
        self._growth_panel = GrowthPanel(self._pet)
        self._growth_panel.feed_clicked.connect(lambda: self._pet.interact('feed'))
        layout.addWidget(self._growth_panel)
        layout.addSpacing(4)

        # 互动区
        layout.addWidget(self._section_title('互动区'))
        for icon, text, action in [('🍖', '喂食', 'feed'), ('🎮', '玩耍', 'play'), ('👆', '戳脸', 'poke')]:
            item = V7MenuItem(icon, text)
            item.clicked.connect(lambda a=action: (self.close(), self._pet.interact(a)))
            layout.addWidget(item)
        layout.addSpacing(4)

        # 外观区
        layout.addWidget(self._section_title('外观区'))
        size_widget = QWidget()
        size_widget.setFixedHeight(32)
        sl = QHBoxLayout(size_widget)
        sl.setContentsMargins(10, 2, 10, 2)
        sl.setSpacing(6)
        size_label = QLabel('大小')
        size_label.setStyleSheet('color: #B0A0C8; font-size: 9pt; font-family: "Microsoft YaHei";')
        sl.addWidget(size_label)
        self._size_buttons = {}
        for label, sz in [('小',140),('中',200),('大',280),('超大',340)]:
            sb = QPushButton(label)
            sb.setFixedHeight(24)
            sb.setCursor(Qt.PointingHandCursor)
            self._size_buttons[sz] = sb
            sb.clicked.connect(lambda checked=False, s=sz: (self.close(), self._pet.setFixedSize(s, int(s * 230 / 200))))
            sl.addWidget(sb)
        sl.addStretch()
        layout.addWidget(size_widget)
        self._top_toggle = V7ToggleItem('⬆️', '始终置顶', True)
        self._top_toggle.toggled.connect(lambda on: self._pet._toggle_topmost(on))
        layout.addWidget(self._top_toggle)
        layout.addSpacing(4)

        # 系统区
        layout.addWidget(self._section_title('系统区'))
        self._voice_toggle = V7ToggleItem('🔊', '语音开关', self._pet.voice.enabled)
        self._voice_toggle.toggled.connect(self._pet.voice.set_enabled)
        layout.addWidget(self._voice_toggle)
        help_item = V7MenuItem('❓', '使用说明')
        help_item.clicked.connect(lambda: (self.close(), self._pet.show_help()))
        layout.addWidget(help_item)
        quit_item = V7MenuItem('⏻', '退出程序')
        quit_item.clicked.connect(lambda: (self.close(), QApplication.instance().quit()))
        layout.addWidget(quit_item)
        layout.addSpacing(6)

        # 底部落款
        footer = QLabel('✦  尤 诺 团 子 · 养 成 版  ✦')
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet('color: rgba(212,175,55,130); font-size: 8pt; font-family: "Microsoft YaHei"; letter-spacing: 2px;')
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
