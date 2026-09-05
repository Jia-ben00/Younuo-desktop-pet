# -*- coding: utf-8 -*-
r"""
鸣潮 · 尤诺团子 桌面宠物 V10
- 等级+好感度双成长系统
- 7状态×5档好感度台词系统（尤诺声线）
- 月亮糕产出/喂食/升级解锁
- 告白解锁（Lv20+好感100）
- 语音修复：开关控制+打断上一条
- 透明无边框置顶，左键拖动，右键菜单，滚轮缩放
"""
import sys, os, json, time, random, math, winsound
from datetime import datetime, timedelta

from PyQt5.QtWidgets import (QApplication, QWidget, QMenu, QAction, QHBoxLayout,
                             QVBoxLayout, QLabel, QPushButton, QProgressBar,
                             QDialog, QTextEdit, QScrollArea, QFrame)
from PyQt5.QtCore import (Qt, QTimer, QPoint, QSize, pyqtSignal, QUrl, QObject)
from PyQt5.QtGui import (QPainter, QPixmap, QColor, QFont, QIcon, QCursor,
                         QLinearGradient, QBrush, QPen, QPainterPath)
from PyQt5.QtMultimedia import QSoundEffect, QMediaPlayer, QMediaContent

# V10菜单
from v7_menu import V7Menu

# ============================================================
# 资源路径
# ============================================================
def resource_path(rel):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, rel)
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, '..', rel)

def data_path():
    if hasattr(sys, '_MEIPASS'):
        exe_dir = os.path.dirname(sys.executable)
        return os.path.join(exe_dir, 'yuno_v10_data.json')
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'yuno_v10_data.json')

ASSETS = resource_path('assets')
DANGO_DIR = os.path.join(ASSETS, 'stickers', 'dango')
PEEKING_DIR = os.path.join(ASSETS, 'stickers', 'peeking')
VOICE_DIR = os.path.join(ASSETS, 'voice_v10')
ANIMATION_DIR = os.path.join(ASSETS, 'animations')

# ============================================================
# 状态→形象映射
# ============================================================
STATE_IMAGE = {
    'qiaotui':  'design_1.png',
    'haixiu':   'design_2.png',
    'sajiao':   'design_3.png',
    'kaixin':   'design_happy.png',
    'shangxin': 'design_sad.png',
    'daimeng':  'design_surprised.png',
    'toukan':   'peeking',
}

STATE_NAME = {
    'qiaotui': '翘腿', 'haixiu': '害羞', 'sajiao': '撒娇',
    'kaixin': '开心', 'shangxin': '伤心', 'daimeng': '呆萌', 'toukan': '偷看',
}

# 好感度档位
AFFECTION_TIERS = [
    (0, 19, '陌生', 1),
    (20, 49, '熟悉', 2),
    (50, 79, '亲近', 3),
    (80, 99, '心动', 4),
    (100, 100, '倾心', 5),
]

def get_affection_tier(affection):
    for lo, hi, name, idx in AFFECTION_TIERS:
        if lo <= affection <= hi:
            return name, idx
    return '陌生', 1

# ============================================================
# 成长数据管理
# ============================================================
class GrowthManager(QObject):
    level_up_signal = pyqtSignal(int)  # 新等级
    food_changed = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.level = 1
        self.exp = 0
        self.food = 5
        self.max_food = 30
        self.last_food_time = time.time()
        self.lover_mode = False
        self._load()
        self._apply_offline_food()

        # 月亮糕产出定时器（5分钟）
        self.food_timer = QTimer()
        self.food_timer.timeout.connect(self._produce_food)
        self.food_timer.start(300000)  # 5分钟

    def _load(self):
        try:
            if os.path.exists(data_path()):
                with open(data_path(), 'r', encoding='utf-8') as f:
                    d = json.load(f)
                self.level = d.get('level', 1)
                self.exp = d.get('exp', 0)
                self.food = d.get('food', 5)
                self.last_food_time = d.get('last_food_time', time.time())
                self.lover_mode = d.get('lover_mode', False)
        except Exception:
            pass

    def save(self):
        try:
            d = {
                'level': self.level,
                'exp': self.exp,
                'food': self.food,
                'last_food_time': self.last_food_time,
                'lover_mode': self.lover_mode,
            }
            with open(data_path(), 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _apply_offline_food(self):
        now = time.time()
        elapsed = now - self.last_food_time
        produced = int(elapsed / 300)  # 5分钟1个
        if produced > 0:
            self.food = min(self.max_food, self.food + produced)
            self.last_food_time = now
            self.save()

    def _produce_food(self):
        if self.food < self.max_food:
            self.food += 1
            self.last_food_time = time.time()
            self.food_changed.emit(self.food)
            self.save()

    def exp_needed(self, level=None):
        if level is None:
            level = self.level
        return level * 100

    def feed(self):
        if self.food <= 0:
            return False, 0
        self.food -= 1
        self.exp += 10
        self.food_changed.emit(self.food)
        leveled_up = False
        new_level = self.level
        while self.exp >= self.exp_needed() and self.level < 20:
            self.exp -= self.exp_needed()
            self.level += 1
            new_level = self.level
            leveled_up = True
        if self.level >= 20:
            self.exp = 0
        self.save()
        if leveled_up:
            self.level_up_signal.emit(new_level)
        return True, new_level if leveled_up else 0

    def can_feed(self):
        return self.food > 0

# ============================================================
# 好感度管理
# ============================================================
class AffectionManager(QObject):
    affection_changed = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.affection = 0
        self.today_date = datetime.now().strftime('%Y-%m-%d')
        self.today_feed_count = 0
        self.today_interact_count = 0
        self.today_online_minutes = 0
        self._load()
        self._check_new_day()

        # 在线陪伴定时器（10分钟+1）
        self.online_timer = QTimer()
        self.online_timer.timeout.connect(self._online_tick)
        self.online_timer.start(600000)  # 10分钟

    def _load(self):
        try:
            if os.path.exists(data_path()):
                with open(data_path(), 'r', encoding='utf-8') as f:
                    d = json.load(f)
                self.affection = d.get('affection', 0)
                self.today_date = d.get('today_date', datetime.now().strftime('%Y-%m-%d'))
                self.today_feed_count = d.get('today_feed_count', 0)
                self.today_interact_count = d.get('today_interact_count', 0)
                self.today_online_minutes = d.get('today_online_minutes', 0)
        except Exception:
            pass

    def save(self):
        try:
            d = {}
            if os.path.exists(data_path()):
                with open(data_path(), 'r', encoding='utf-8') as f:
                    d = json.load(f)
            d.update({
                'affection': self.affection,
                'today_date': self.today_date,
                'today_feed_count': self.today_feed_count,
                'today_interact_count': self.today_interact_count,
                'today_online_minutes': self.today_online_minutes,
            })
            with open(data_path(), 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _check_new_day(self):
        today = datetime.now().strftime('%Y-%m-%d')
        if today != self.today_date:
            self.today_date = today
            self.today_feed_count = 0
            self.today_interact_count = 0
            self.today_online_minutes = 0
            self.save()

    def _online_tick(self):
        self._check_new_day()
        if self.today_online_minutes < 300:  # 上限300分钟=+30
            self.today_online_minutes += 10
            self._add_affection(1)
            self.save()

    def _add_affection(self, amount):
        old = self.affection
        self.affection = min(100, self.affection + amount)
        if self.affection != old:
            self.affection_changed.emit(self.affection)

    def on_feed(self):
        self._check_new_day()
        if self.today_feed_count < 15:
            self.today_feed_count += 1
            bonus = 2
            # 及时投喂（食物<3时）额外+2
            # 由调用方判断
            self._add_affection(bonus)
            self.save()
            return bonus
        return 0

    def on_interact(self):
        self._check_new_day()
        if self.today_interact_count < 20:
            self.today_interact_count += 1
            self._add_affection(1)
            self.save()
            return 1
        return 0

    def get_tier_name(self):
        name, _ = get_affection_tier(self.affection)
        return name

# ============================================================
# 语音管理器（修复：开关控制+打断上一条）
# ============================================================
class VoiceManager(QObject):
    def __init__(self):
        super().__init__()
        self.enabled = True

    def set_enabled(self, enabled):
        self.enabled = enabled
        if not enabled:
            self.stop()

    def stop(self):
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass

    def play(self, voice_name):
        if not self.enabled:
            return
        voice_file = os.path.join(VOICE_DIR, f'{voice_name}.wav')
        if not os.path.exists(voice_file):
            return
        try:
            # 先停止上一条，再异步播放新的
            winsound.PlaySound(None, winsound.SND_PURGE)
            winsound.PlaySound(voice_file, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except Exception:
            pass

    def play_line(self, state, tier_idx):
        voice_name = f'{state}_{tier_idx}'
        self.play(voice_name)

# ============================================================
# 升级弹窗
# ============================================================
class LevelUpDialog(QDialog):
    def __init__(self, level, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(360, 200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel(f'等级提升！Lv.{level}')
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet('font-size: 24px; font-weight: bold; color: #FFD700;')
        layout.addWidget(title)

        subtitle = QLabel('本座果然是最棒的！')
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet('font-size: 14px; color: #E0E0FF;')
        layout.addWidget(subtitle)

        layout.addSpacing(20)

        ok_btn = QPushButton('知道了')
        ok_btn.setStyleSheet('''
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #4A3F8C, stop:1 #6B5B95);
                color: #FFD700; border: 1px solid #FFD700;
                border-radius: 15px; padding: 8px 20px; font-size: 14px;
            }
            QPushButton:hover { background: #6B5B95; }
        ''')
        ok_btn.clicked.connect(self.accept)
        layout.addWidget(ok_btn)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(10, 10, self.width()-20, self.height()-20, 20, 20)
        p.fillPath(path, QColor(20, 15, 50, 240))
        p.setPen(QPen(QColor(255, 215, 0, 180), 2))
        p.drawPath(path)

# ============================================================
# 告白场景
# ============================================================
class ConfessionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(420, 320)
        self.current_line = 0
        self.lines = [
            '本座预见无数个未来……每个都绕不开你。',
            '月食是月的命数，你是本座的例外。',
            '不准松开我。这句话，从来不是命令，是请求。',
        ]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)

        self.title = QLabel('今晚月色真美……')
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet('font-size: 20px; font-weight: bold; color: #FFD700;')
        layout.addWidget(self.title)

        layout.addSpacing(20)

        self.text = QLabel(self.lines[0])
        self.text.setAlignment(Qt.AlignCenter)
        self.text.setWordWrap(True)
        self.text.setStyleSheet('font-size: 16px; color: #E0E0FF; line-height: 1.6;')
        layout.addWidget(self.text)

        layout.addSpacing(30)

        self.next_btn = QPushButton('下一句')
        self.next_btn.setStyleSheet('''
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #4A3F8C, stop:1 #6B5B95);
                color: #FFD700; border: 1px solid #FFD700;
                border-radius: 15px; padding: 8px 20px; font-size: 14px;
            }
            QPushButton:hover { background: #6B5B95; }
        ''')
        self.next_btn.clicked.connect(self._next_line)
        layout.addWidget(self.next_btn)

    def _next_line(self):
        self.current_line += 1
        if self.current_line < len(self.lines):
            self.text.setText(self.lines[self.current_line])
            if self.current_line == len(self.lines) - 1:
                self.next_btn.setText('进入恋人模式')
        else:
            self.accept()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # 月光渐变背景
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0, QColor(30, 20, 70, 245))
        grad.setColorAt(1, QColor(15, 10, 40, 245))
        path = QPainterPath()
        path.addRoundedRect(10, 10, self.width()-20, self.height()-20, 25, 25)
        p.fillPath(path, grad)
        p.setPen(QPen(QColor(255, 215, 0, 200), 2))
        p.drawPath(path)
        # 星光
        p.setBrush(QColor(255, 255, 200, 150))
        for _ in range(15):
            x = random.randint(20, self.width()-20)
            y = random.randint(20, self.height()-20)
            p.drawEllipse(x, y, 2, 2)

# ============================================================
# 使用说明对话框
# ============================================================
class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(440, 620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(8)

        # 标题
        title = QLabel('✦ 尤诺团子 · 使用说明 ✦')
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet('font-size: 16px; font-weight: bold; color: #FFD700; font-family: "Microsoft YaHei";')
        layout.addWidget(title)

        # 内容（滚动区域）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet('QScrollArea { background: rgba(20,15,45,200); border: none; border-radius: 8px; } QScrollBar:vertical { background: rgba(50,40,80,100); width: 8px; border-radius: 4px; } QScrollBar::handle:vertical { background: rgba(212,175,55,150); border-radius: 4px; }')
        content = QWidget()
        content.setStyleSheet('background: transparent;')
        cl = QVBoxLayout(content)
        cl.setContentsMargins(5, 5, 15, 5)
        cl.setSpacing(10)

        sections = [
            ('🐾 基础操作', [
                '• 左键拖动：移动桌宠位置',
                '• 右键点击：打开功能菜单',
                '• 滚轮滚动：调整桌宠大小',
                '• 左键单击：戳脸互动（呆萌状态）',
            ]),
            ('🌙 成长系统', [
                '• 月亮糕：每5分钟自动产出1个，上限30个',
                '• 喂食：消耗1个月亮糕，+10经验值',
                '• 等级：Lv1~Lv20，升级需 N×100 经验',
                '• 升级解锁：偷看(Lv2)、撒娇(Lv3)、害羞(Lv4)、开心(Lv5)等',
            ]),
            ('💗 好感度系统', [
                '• 5档：疏离(0-19)→熟悉(20-49)→亲近(50-79)→心动(80-99)→倾心(100)',
                '• 获取：喂食+2(每日前15次)、互动+1(每日前20次)、在线每10分钟+1',
                '• 不同好感度档位触发不同台词，越高级越亲昵',
            ]),
            ('💍 告白解锁', [
                '• 条件：等级Lv20 AND 好感度100（双满）',
                '• 达成后触发月光告白场景，进入恋人模式',
                '• 恋人模式：全局台词切换为倾心档，互动更亲昵',
            ]),
            ('🔊 语音系统', [
                '• 7种状态×5档好感度 = 35句尤诺声线台词',
                '• 升级/告白专属语音',
                '• 菜单中可开关语音',
                '• 触发新语音时自动打断上一条',
            ]),
            ('⏳ 状态变化', [
                '• 2分钟无互动→开心状态（喂食暗示）',
                '• 5分钟无互动→偷看状态',
                '• 喂食→翘腿/开心状态',
                '• 戳脸→呆萌状态',
            ]),
        ]

        for sec_title, items in sections:
            sec_lbl = QLabel(sec_title)
            sec_lbl.setStyleSheet('color: #FFD700; font-size: 11px; font-weight: bold; font-family: "Microsoft YaHei"; margin-top: 5px;')
            cl.addWidget(sec_lbl)
            for item in items:
                item_lbl = QLabel(item)
                item_lbl.setWordWrap(True)
                item_lbl.setStyleSheet('color: #D0C8E0; font-size: 9px; font-family: "Microsoft YaHei"; line-height: 1.4;')
                cl.addWidget(item_lbl)

        cl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        # 关闭按钮
        close_btn = QPushButton('知道了')
        close_btn.setFixedHeight(32)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #DAA520, stop:0.5 #FFD700, stop:1 #DAA520);
                color: #2a1f0a; border: 1px solid rgba(255,220,130,200);
                border-radius: 16px; font-family: "Microsoft YaHei";
                font-size: 10pt; font-weight: bold;
            }
            QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #FFD700, stop:0.5 #FFEC8B, stop:1 #FFD700); }
        """)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def paintEvent(self, event):
        try:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing, True)
            grad = QLinearGradient(0, 0, 0, self.height())
            grad.setColorAt(0, QColor(15, 12, 40, 245))
            grad.setColorAt(1, QColor(35, 22, 60, 245))
            path = QPainterPath()
            path.addRoundedRect(5, 5, self.width()-10, self.height()-10, 18, 18)
            p.fillPath(path, grad)
            p.setPen(QPen(QColor(212, 175, 55, 150), 1.5))
            p.drawPath(path)
            p.end()
        except Exception:
            pass

# ============================================================
# 桌宠主组件
# ============================================================
class DangoWidget(QWidget):
    state_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(200, 230)

        # 状态
        self.current_state = 'qiaotui'
        self._drag_pos = None
        self._idle_timer = QTimer()
        self._idle_timer.timeout.connect(self._on_idle)
        self._idle_seconds = 0
        self._idle_timer.start(1000)

        # 加载图片
        self._pixmaps = {}
        self._peeking_frames = []
        self._peeking_idx = 0
        self._peeking_timer = QTimer()
        self._peeking_timer.timeout.connect(self._peeking_tick)
        self._load_images()

        # 动画
        self._anim_timer = QTimer()
        self._anim_timer.timeout.connect(self.update)
        self._anim_timer.start(50)
        self._anim_time = 0

        # 成长系统
        self.growth = GrowthManager()
        self.affection = AffectionManager()
        self.voice = VoiceManager()

        # 连接信号
        self.growth.level_up_signal.connect(self._on_level_up)

        # 显示
        self.move(100, 100)
        self.show()

    def _load_images(self):
        for state, fname in STATE_IMAGE.items():
            if fname == 'peeking':
                continue
            path = os.path.join(DANGO_DIR, fname)
            if os.path.exists(path):
                pm = QPixmap(path)
                if not pm.isNull():
                    self._pixmaps[state] = pm
        # peeking帧
        if os.path.exists(PEEKING_DIR):
            frames = sorted([f for f in os.listdir(PEEKING_DIR) if f.endswith('.png')])
            for f in frames[:10]:
                pm = QPixmap(os.path.join(PEEKING_DIR, f))
                if not pm.isNull():
                    self._peeking_frames.append(pm)

    def _peeking_tick(self):
        self._peeking_idx = (self._peeking_idx + 1) % len(self._peeking_frames)
        self.update()

    def set_state(self, state):
        if state == self.current_state:
            return
        self.current_state = state
        if state == 'toukan' and self._peeking_frames:
            self._peeking_idx = 0
            self._peeking_timer.start(100)
        else:
            self._peeking_timer.stop()
        self.state_changed.emit(state)
        self.update()

    def _on_idle(self):
        self._idle_seconds += 1
        # 2分钟无互动→开心（喂食暗示）
        if self._idle_seconds == 120 and self.current_state != 'kaixin':
            self.set_state('kaixin')
            self._play_current_line()
        # 5分钟无互动→偷看
        elif self._idle_seconds == 300 and self.current_state != 'toukan':
            self.set_state('toukan')
            self._play_current_line()

    def _reset_idle(self):
        self._idle_seconds = 0

    def _play_current_line(self):
        _, tier_idx = get_affection_tier(self.affection.affection)
        self.voice.play_line(self.current_state, tier_idx)

    def interact(self, action):
        self._reset_idle()
        self.affection.on_interact()

        if action == 'poke':
            self.set_state('daimeng')
            self._play_current_line()
        elif action == 'drag':
            self.set_state('haixiu')
            self._play_current_line()
        elif action == 'play':
            self.set_state('kaixin')
            self._play_current_line()
        elif action == 'feed':
            if self.growth.can_feed():
                success, new_level = self.growth.feed()
                if success:
                    self.affection.on_feed()
                    self.set_state('sajiao')
                    self._play_current_line()
                    if new_level > 0:
                        self.voice.play('levelup')
            else:
                # 没有月亮糕时也说一句话
                self.set_state('shangxin')
                self._play_current_line()
        elif action == 'idle_talk':
            # 随机状态
            states = ['qiaotui', 'haixiu', 'sajiao', 'kaixin', 'daimeng']
            self.set_state(random.choice(states))
            self._play_current_line()

        # 5分钟无互动后互动→伤心
        if self._idle_seconds > 300:
            self.set_state('shangxin')
            self._play_current_line()

    def _on_level_up(self, level):
        dlg = LevelUpDialog(level, self)
        dlg.exec_()
        # 检查告白解锁
        if level >= 20 and self.affection.affection >= 100 and not self.growth.lover_mode:
            self.growth.lover_mode = True
            self.growth.save()
            self._show_confession()

    def _show_confession(self):
        dlg = ConfessionDialog(self)
        dlg.exec_()
        self.voice.play('gaobai_1')

    def check_confession(self):
        if (self.growth.level >= 20 and self.affection.affection >= 100
                and not self.growth.lover_mode):
            self.growth.lover_mode = True
            self.growth.save()
            self._show_confession()

    def paintEvent(self, event):
        p = QPainter(self)

        # 呼吸动画
        self._anim_time += 0.05
        breath = 1.0 + 0.03 * math.sin(self._anim_time * 2)

        if self.current_state == 'toukan' and self._peeking_frames:
            pm = self._peeking_frames[self._peeking_idx % len(self._peeking_frames)]
        else:
            pm = self._pixmaps.get(self.current_state)
            if pm is None:
                pm = self._pixmaps.get('qiaotui')

        if pm and not pm.isNull():
            w = int(self.width() * 0.9 * breath)
            h = int(self.height() * 0.9 * breath)
            x = (self.width() - w) // 2
            y = (self.height() - h) // 2
            p.drawPixmap(x, y, w, h, pm)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            self._press_pos = event.globalPos()
            event.accept()
        elif event.button() == Qt.RightButton:
            self._show_menu(event.globalPos())
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            moved = (event.globalPos() - self._press_pos).manhattanLength() if hasattr(self, '_press_pos') else 0
            self._drag_pos = None
            if moved > 10:
                # 拖拽→害羞互动
                self.interact('drag')
            else:
                # 点击（非拖动）→戳脸互动
                self.interact('poke')

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        new_size = max(100, min(400, self.width() + delta // 8))
        self.setFixedSize(new_size, new_size)

    def _toggle_topmost(self, on):
        flags = self.windowFlags()
        if on:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def _show_menu(self, pos):
        self._menu = V7Menu(self)
        self._menu.popup(pos)

    def _toggle_voice(self):
        self.voice.set_enabled(not self.voice.enabled)

    def show_help(self):
        dlg = HelpDialog()
        dlg.exec_()

# ============================================================
# 主程序
# ============================================================
def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # 全局异常钩子
    def excepthook(exc_type, exc_value, exc_tb):
        import traceback
        traceback.print_exception(exc_type, exc_value, exc_tb)
    sys.excepthook = excepthook

    pet = DangoWidget()

    # 启动时翘腿状态+台词
    QTimer.singleShot(1000, lambda: pet.interact('idle_talk'))

    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
