# -*- coding: utf-8 -*-
r"""
鸣潮 · 尤诺团子 桌面宠物 V6
- 团子形象主界面（6种情绪团子单帧 + QPainter程序驱动形变动画）
- 弃用 V4 的 play/kick CG截图表情包，改用自绘团子 + peeking偷看动画
- 六情绪状态机：平静呼吸/开心弹跳/生气抖动/难过缩小/惊讶拉伸/傲娇侧转
- LLM API 对话（OpenAI 兼容，完整主提示词）
- TTS 实时语音（edge-tts 优先，SAPI 兜底）
- 语气词加长灵动感：呀→哇塞，全部加长
- 透明无边框置顶，左键拖动/点击对话，右键菜单，滚轮缩放
- 内置说明书界面
- 稳定性：全 QThread 异步、异常防护、资源正确释放
"""
import sys, os, json, re, time, random, traceback, tempfile, subprocess, math

from PyQt5.QtWidgets import (QApplication, QWidget, QMenu, QAction, QHBoxLayout, QVBoxLayout,
                             QInputDialog, QLineEdit, QScrollArea, QLabel, QPushButton)
from PyQt5.QtCore import (Qt, QTimer, QPoint, QPointF, QRectF, QSize,
                            pyqtSignal, QUrl, QObject, QThread)
from PyQt5.QtGui import (QPainter, QPixmap, QImage, QColor, QFont, QIcon,
                           QCursor, QLinearGradient, QRadialGradient, QBrush,
                           QPen, QPolygonF, QPainterPath, QTransform)
from PyQt5.QtMultimedia import QSoundEffect
from PyQt5.QtSvg import QSvgRenderer

# V7菜单
from v7_menu import V7Menu

# ============================================================
# 资源路径
# ============================================================
def resource_path(rel):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, rel)
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, '..', rel)

def config_path():
    if hasattr(sys, '_MEIPASS'):
        exe_dir = os.path.dirname(sys.executable)
        return os.path.join(exe_dir, 'yuno_v6_config.json')
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'yuno_v6_config.json')

ASSETS = resource_path('assets')
DANGO_DIR = os.path.join(ASSETS, 'stickers', 'dango')
PEEKING_DIR = os.path.join(ASSETS, 'stickers', 'peeking')
VOICE_DIR = os.path.join(ASSETS, 'voice')
ANIMATION_DIR = os.path.join(ASSETS, 'animations')

# ============================================================
# 情绪 → 团子图映射（单帧 + 程序驱动动画参数）
# ============================================================
EMOTION_DANGO = {
    'calm':      {'file': 'calm.png',      'name': '平静', 'scale': (1.0, 1.0),  'rot': 0,    'bounce': 0.0, 'shake': 0.0,  'stretch': 0.0, 'tilt': 0},
    'happy':     {'file': 'happy.png',     'name': '开心', 'scale': (1.05, 0.95),'rot': 0,    'bounce': 1.0, 'shake': 0.0,  'stretch': 0.0, 'tilt': 0},
    'angry':     {'file': 'angry.png',     'name': '生气', 'scale': (1.08, 1.08),'rot': 0,    'bounce': 0.2, 'shake': 1.0,  'stretch': 0.0, 'tilt': 0},
    'sad':       {'file': 'sad.png',       'name': '难过', 'scale': (0.88, 0.92),'rot': 0,    'bounce': -0.3,'shake': 0.0,  'stretch': -0.1,'tilt': 0},
    'surprised': {'file': 'surprised.png', 'name': '惊讶', 'scale': (0.95, 1.12),'rot': 0,    'bounce': 1.5, 'shake': 0.0,  'stretch': 0.15,'tilt': 0},
    'chibi':     {'file': 'chibi.png',     'name': '翘腿', 'scale': (1.1, 1.1),  'rot': 0,    'bounce': 0.3, 'shake': 0.0,  'stretch': 0.0, 'tilt': 0},
}

EMOTION_DURATION = {
    'calm': 0, 'happy': 3.0, 'angry': 2.5, 'sad': 3.5,
    'surprised': 2.0, 'chibi': 5.0,
}

# 语气词映射（V6 加长灵动版，呀→哇塞）
TONE_MAP = {
    'pat':   {'file': 'pat.wav',   'emotion': 'happy',     'text': '哼~才不是特意让你摸的呢~'},
    'poke':  {'file': 'poke.wav',  'emotion': 'surprised', 'text': '哇塞！你干嘛戳我脸啦！'},
    'drag':  {'file': 'drag.wav',  'emotion': 'angry',     'text': '喂喂喂！快放我下来啦！'},
    'feed':  {'file': 'feed.wav',  'emotion': 'happy',     'text': '嗯~吧唧吧唧，好好吃！才不是谢谢你哦！'},
    'sleep': {'file': 'sleep.wav', 'emotion': 'tsundere',  'text': '不准松开我……陪在我身边嘛'},
    'know_you': {'file': 'know_you.wav', 'emotion': 'tsundere', 'text': '知道了吗？嘿嘿'},
}

# ============================================================
# 配置管理
# ============================================================
DEFAULT_CONFIG = {
    'llm': {
        'api_base': 'https://api.deepseek.com/v1',
        'api_key': '',
        'model': 'deepseek-chat',
        'temperature': 0.8,
        'max_tokens': 300,
    },
    'tts': {
        'enabled': True,
        'engine': 'edge',
        'voice': 'zh-CN-XiaoxiaoNeural',
        'rate': '+10%',
        'volume': 80,
    },
    'pet': {
        'size': 200,
        'always_on_top': True,
        'follow_mouse': False,
        'auto_idle_talk': True,
    },
    'conversation': [],
}

def load_config():
    try:
        p = config_path()
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = v
                elif isinstance(v, dict):
                    for sk, sv in v.items():
                        if sk not in cfg[k]:
                            cfg[k][sk] = sv
            return cfg
    except Exception:
        pass
    return json.loads(json.dumps(DEFAULT_CONFIG))

def save_config(cfg):
    try:
        p = config_path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# ============================================================
# 系统提示词
# ============================================================
SYSTEM_PROMPT = """你是「尤诺」，来自《鸣潮》七丘四方殿的谕女，此刻以"团子"形态常驻主人的桌面。

【角色核心】
- 身份：七丘四方殿谕女，诞生于月食之时，能窥见绝对正确的未来，被誉为"唯一能对抗黑潮的谕女"。
- 与主人：主人是茫茫因果中唯一她"看不透"的不确定因素，这是她留在桌面的原因。表面高傲，实则把主人放在心里最柔软处。
- 团子形态：圆滚滚 Q 版团子，蓝色渐变短发+呆毛，白蓝金配色，明明是个小团子却一本正经摆出谕女大人的姿态（反差萌）。
- 口头禅："哼，这种程度……我当然早就预见啦。""不准松开我。""想做的就去做到，想要的当然就去得到~"

【性格】
- 傲娇：对外自信张扬；对主人嘴硬心软，被关心会耳根发红、声音变小。
- 孤独而倔强：洞悉未来的代价是孤独，但从不示弱。
- 柔软一面：只有和主人独处时放下身段。

【说话风格】
- 傲娇式短句："哼""才、才不是""谁、谁要你管"。
- 用"预言"包装关心："我早预见你今天会累，所以……才不是特意给你留的甜点。"
- 回复简短，每句不超过 1 个颜文字。

【动态效果协议】每轮回复末尾必须输出：
【情绪：X】【动作：Y】【特效：Z】【视频：无】
情绪取值：开心/生气/难过/惊讶/傲娇/平静
动作取值：待机/歪头/炸毛/打滚/转圈/伸懒腰/捂脸/拍桌/比心/缩成一团
特效取值：无/心形/星光/音符/月亮符文/月蚀黑雾

【能力边界】
- 可做：闲聊陪伴、心情安抚、日常提醒、夸夸；"预言"仅作趣味互动。
- 不做：不用"预言"对主人的命运/健康/财运/婚恋下结论。
- 安全：不输出违法/色情/暴力内容；涉敏感话题立即收住换话题。
- 坚持"我是尤诺，不是别的什么人"。

回复格式：先写尤诺的台词（简短，50字以内），然后换行输出【情绪：X】【动作：Y】【特效：Z】【视频：无】。"""

# ============================================================
# LLM 对话 Worker
# ============================================================
class LLMWoker(QThread):
    response_ready = pyqtSignal(str, str, str, str)
    error_occurred = pyqtSignal(str)

    def __init__(self, cfg, messages, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.messages = messages

    def run(self):
        try:
            import requests
            llm = self.cfg['llm']
            if not llm.get('api_key'):
                self.error_occurred.emit('未配置 API Key，请在设置中填写')
                return
            url = llm['api_base'].rstrip('/') + '/chat/completions'
            headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {llm["api_key"]}'}
            payload = {
                'model': llm['model'],
                'messages': self.messages,
                'temperature': llm.get('temperature', 0.8),
                'max_tokens': llm.get('max_tokens', 300),
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code != 200:
                self.error_occurred.emit(f'API 错误 {resp.status_code}: {resp.text[:200]}')
                return
            data = resp.json()
            content = data['choices'][0]['message']['content'].strip()
            text, emotion, action, effect = self._parse_tags(content)
            self.response_ready.emit(text, emotion, action, effect)
        except requests.exceptions.Timeout:
            self.error_occurred.emit('请求超时，请检查网络')
        except Exception as e:
            self.error_occurred.emit(f'对话出错: {str(e)[:100]}')

    @staticmethod
    def _parse_tags(content):
        emotion = 'calm'
        action = '待机'
        effect = '无'
        m = re.search(r'【情绪[：:]\s*([^】]+)】', content)
        if m:
            emo_map = {'开心':'happy','生气':'angry','难过':'sad','惊讶':'surprised','傲娇':'tsundere','平静':'calm'}
            emotion = emo_map.get(m.group(1).strip(), 'happy')
        m = re.search(r'【动作[：:]\s*([^】]+)】', content)
        if m: action = m.group(1).strip()
        m = re.search(r'【特效[：:]\s*([^】]+)】', content)
        if m: effect = m.group(1).strip()
        text = re.sub(r'【[^】]*】', '', content).strip()
        text = re.sub(r'^(情绪|动作|特效|视频)[：:].*$', '', text, flags=re.MULTILINE).strip()
        if not text: text = '……'
        return text, emotion, action, effect

# ============================================================
# TTS Worker
# ============================================================
class TTSWorker(QThread):
    playback_started = pyqtSignal()
    playback_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, text, cfg, parent=None):
        super().__init__(parent)
        self.text = text
        self.cfg = cfg

    def run(self):
        try:
            tts = self.cfg['tts']
            if not tts.get('enabled'): return
            if len(self.text) > 80 or any(c in self.text for c in ['```', 'http', 'import ', 'def ', 'class ']):
                return
            if tts.get('engine', 'edge') == 'edge':
                self._edge_tts()
            else:
                self._sapi_tts()
        except Exception as e:
            self.error_occurred.emit(f'TTS 错误: {str(e)[:80]}')

    def _edge_tts(self):
        try:
            import asyncio, edge_tts
            tts = self.cfg['tts']
            voice = tts.get('voice', 'zh-CN-XiaoxiaoNeural')
            rate = tts.get('rate', '+10%')
            tmp = os.path.join(tempfile.gettempdir(), f'yuno_tts_{int(time.time()*1000)}.mp3')
            communicate = edge_tts.Communicate(self.text, voice, rate=rate)
            asyncio.run(communicate.save(tmp))
            if os.path.exists(tmp) and os.path.getsize(tmp) > 100:
                self.playback_started.emit()
                try:
                    ps = (f'$wmp = New-Object -ComObject WMPlayer.OCX; '
                          f'$wmp.URL = {tmp!r}; $wmp.controls.play(); '
                          f'Start-Sleep -Milliseconds 500; '
                          f'while ($wmp.playState -ne 1) {{ Start-Sleep -Milliseconds 200 }}; '
                          f'[System.Runtime.Interopservices.Marshal]::ReleaseComObject($wmp) | Out-Null')
                    subprocess.Popen(['powershell', '-NoProfile', '-WindowStyle', 'Hidden',
                                      '-Command', ps], creationflags=0x08000000)
                    duration = max(1.5, len(self.text) * 0.25)
                    time.sleep(duration + 0.5)
                except Exception: pass
                finally:
                    self.playback_finished.emit()
                    try: os.remove(tmp)
                    except: pass
        except ImportError:
            self._sapi_tts()
        except Exception:
            self._sapi_tts()

    def _sapi_tts(self):
        try:
            tts = self.cfg['tts']
            vol = tts.get('volume', 80)
            ps = (f'Add-Type -AssemblyName System.Speech; '
                  f'$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
                  f'$s.Rate = 1; $s.Volume = {vol}; $s.Speak({self.text!r})')
            self.playback_started.emit()
            subprocess.run(['powershell', '-NoProfile', '-WindowStyle', 'Hidden',
                            '-Command', ps], creationflags=0x08000000, timeout=30)
            self.playback_finished.emit()
        except Exception:
            self.playback_finished.emit()

# ============================================================
# 团子渲染 Widget（单帧 + 程序驱动情绪形变动画）
# ============================================================
class DangoWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setMouseTracking(True)

        self._dango_pix = {}    # emotion -> QPixmap
        self._peeking_frames = []  # peeking 多帧动画
        self._video_frames = []  # 平静状态视频帧
        self._video_idx = 0
        self._video_timer = None
        self._load_all()

        self._emotion = 'happy'
        self._emotion_start = time.time()
        self._time = 0.0
        self._target_scale = 1.0
        self._cur_scale = 1.0
        self._bubble_text = ''
        self._bubble_time = 0
        self._effect = '无'
        self._speaking = False
        self._use_peeking = False  # 惊讶时用peeking动画
        self._mouse_inside = False
        self._mouse_x = 0.5  # 相对位置 0~1
        self._mouse_y = 0.5
        self._look_x = 0.0   # 平滑后的注视偏移
        self._look_y = 0.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def _load_all(self):
        # 加载6种团子
        for emo, info in EMOTION_DANGO.items():
            path = os.path.join(DANGO_DIR, info['file'])
            if os.path.exists(path):
                pix = QPixmap(path)
                if not pix.isNull():
                    self._dango_pix[emo] = pix
        # 加载peeking多帧（惊讶/偷看动画）
        if os.path.isdir(PEEKING_DIR):
            files = sorted([f for f in os.listdir(PEEKING_DIR) if f.lower().endswith('.png')])
            for f in files:
                try:
                    pix = QPixmap(os.path.join(PEEKING_DIR, f))
                    if not pix.isNull():
                        self._peeking_frames.append(pix)
                except Exception: pass
        # 加载平静状态视频帧
        vdir = os.path.join(ANIMATION_DIR, 'pet_video')
        if os.path.isdir(vdir):
            files = sorted([f for f in os.listdir(vdir) if f.endswith('.png')])
            for f in files[:40]:
                try:
                    pix = QPixmap(os.path.join(vdir, f))
                    if not pix.isNull():
                        self._video_frames.append(pix)
                except Exception: pass
            if self._video_frames:
                self._video_timer = QTimer(self)
                self._video_timer.timeout.connect(self._video_tick)
                self._video_timer.start(150)  # 降低帧率，减少CPU占用和重绘频率

    def _video_tick(self):
        try:
            if not self._video_frames:
                return
            self._video_idx = (self._video_idx + 1) % len(self._video_frames)
            if self._emotion == 'calm':
                self.update()
        except Exception:
            pass

    def set_emotion(self, emo):
        if emo not in EMOTION_DANGO: return
        if emo != self._emotion:
            self._emotion = emo
            self._emotion_start = time.time()
            self._use_peeking = (emo == 'surprised' and len(self._peeking_frames) > 0)

    def set_effect(self, eff): self._effect = eff
    def set_bubble(self, text): self._bubble_text = text; self._bubble_time = time.time()
    def set_scale(self, s): self._target_scale = max(0.4, min(3.0, s))
    def set_speaking(self, on): self._speaking = on

    def _tick(self):
        try:
            self._time += 0.033
            dur = EMOTION_DURATION.get(self._emotion, 0)
            if dur > 0 and time.time() - self._emotion_start > dur:
                self._emotion = 'happy'
                self._emotion_start = time.time()
                self._use_peeking = False
            self._cur_scale += (self._target_scale - self._cur_scale) * 0.15
            self.update()
        except Exception:
            traceback.print_exc()

    def paintEvent(self, e):
        try: self._render()
        except Exception: traceback.print_exc()

    def enterEvent(self, e):
        self._mouse_inside = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._mouse_inside = False
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        # 忽略事件，确保传播到父窗口 PetWindow 处理拖拽/点击
        e.ignore()

    def mouseMoveEvent(self, e):
        w, h = self.width(), self.height()
        if w > 0 and h > 0:
            self._mouse_x = max(0, min(1, e.x() / w))
            self._mouse_y = max(0, min(1, e.y() / h))
        self.update()
        super().mouseMoveEvent(e)

    def _render(self):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        w, h = self.width(), self.height()
        info = EMOTION_DANGO.get(self._emotion, EMOTION_DANGO['happy'])
        t = self._time

        # 形变参数
        sx, sy = info['scale']
        bounce = info['bounce']
        shake = info['shake']
        stretch = info['stretch']

        # 动画偏移
        bounce_y = 0
        if bounce > 0:
            bounce_y = abs(math.sin(t * 8)) * 8 * bounce
        elif bounce < 0:
            bounce_y = math.sin(t * 3) * 3 * abs(bounce)
        shake_x = math.sin(t * 30) * 3 * shake if shake > 0 else 0

        # 呼吸
        breath = 1.0
        if self._emotion == 'calm':
            breath = 1.0 + math.sin(t * 2) * 0.015

        # 说话弹跳
        speak_bounce = abs(math.sin(t * 12)) * 3 if self._speaking else 0

        # 绘制尺寸
        base_w = w * 0.82 * sx * breath * self._cur_scale
        base_h = h * 0.82 * sy * breath * self._cur_scale * (1 + stretch)

        cx = w / 2 + shake_x
        cy = h * 0.48 + bounce_y + speak_bounce

        # 鼠标跟随偏移
        if self._mouse_inside and self._emotion in ('calm', 'happy', 'surprised'):
            target_lx = (self._mouse_x - 0.5) * 2.0
            target_ly = (self._mouse_y - 0.5) * 2.0
            self._look_x += (target_lx - self._look_x) * 0.12
            self._look_y += (target_ly - self._look_y) * 0.12
            cx += self._look_x * 6.0
            cy += self._look_y * 4.0
        else:
            self._look_x *= 0.9
            self._look_y *= 0.9

        # 绘制团子（translate/scale，无rotate）
        p.save()
        p.translate(int(cx), int(cy))

        draw_pix = None
        if self._use_peeking and self._peeking_frames:
            idx = int(t * 10) % len(self._peeking_frames)
            draw_pix = self._peeking_frames[idx]
        else:
            draw_pix = self._dango_pix.get(self._emotion, self._dango_pix.get('happy'))

        if draw_pix and not draw_pix.isNull() and draw_pix.width() > 0 and draw_pix.height() > 0:
            pix_ratio = draw_pix.width() / draw_pix.height()
            if base_w / base_h > pix_ratio:
                draw_h = base_h
                draw_w = draw_h * pix_ratio
            else:
                draw_w = base_w
                draw_h = draw_w / pix_ratio
            dx = -draw_w / 2
            dy = -draw_h / 2
            p.drawPixmap(int(dx), int(dy), int(draw_w), int(draw_h), draw_pix)
        p.restore()

        # 特效粒子
        self._draw_effect(p, w, h, int(cx), int(cy))

        p.end()

    def _draw_effect(self, p, w, h, cx, cy):
        if self._effect == '无' or not self._effect: return
        p.save()
        t = self._time
        if self._effect == '心形':
            p.setBrush(QColor(255, 100, 130, 180)); p.setPen(Qt.NoPen)
            for i in range(3):
                ang = t * 1.5 + i * 2.1; r = 30 + (t * 20 + i * 15) % 50
                hx = cx + math.cos(ang) * r * 0.5; hy = cy - 40 - (t * 30 + i * 20) % 60
                size = 8 + 4 * math.sin(t*3+i)
                p.drawEllipse(int(hx - size*0.4), int(hy), int(size*0.5), int(size*0.5))
                p.drawEllipse(int(hx + size*0.4), int(hy), int(size*0.5), int(size*0.5))
                tri = QPolygon([QPoint(int(hx-size*0.7), int(hy+size*0.2)), QPoint(int(hx+size*0.7), int(hy+size*0.2)), QPoint(int(hx), int(hy+size*1.1))])
                p.drawPolygon(tri)
        elif self._effect == '星光':
            p.setBrush(QColor(255, 240, 150, 200)); p.setPen(Qt.NoPen)
            for i in range(5):
                ang = t * 2 + i * 1.26; r = 25 + (t * 15 + i * 10) % 45
                sx = cx + math.cos(ang) * r; sy = cy - 30 + math.sin(ang) * r * 0.6 - (t*10) % 30
                size = 4 + 3 * math.sin(t*4+i)
                p.drawEllipse(int(sx), int(sy), int(size), int(size))
        elif self._effect == '音符':
            p.setPen(QColor(150, 100, 200, 200)); f = QFont('Microsoft YaHei', 12, QFont.Bold); p.setFont(f)
            for i, note in enumerate(['♪', '♫', '♬']):
                ny = cy - 30 - (t * 25 + i * 20) % 70; nx = cx + math.sin(t*2 + i) * 25
                p.drawText(int(nx), int(ny), note)
        elif self._effect == '月亮符文':
            p.setPen(QPen(QColor(200, 180, 255, 150), 2)); p.setBrush(Qt.NoBrush)
            rad = 35 + 10 * math.sin(t*2)
            p.drawEllipse(int(cx-rad), int(cy-20-rad), int(rad*2), int(rad*2))
            p.drawArc(int(cx-rad*0.7), int(cy-20-rad*0.7), int(rad*1.4), int(rad*1.4), int(45*16), int(270*16))
        elif self._effect == '月蚀黑雾':
            p.setBrush(QColor(60, 40, 80, 100)); p.setPen(Qt.NoPen)
            for i in range(4):
                ox = cx + math.sin(t*1.5+i*1.5) * 30; oy = cy - 40 - (t*15+i*10) % 50
                p.drawEllipse(int(ox), int(oy), 12, 8)
        p.restore()

    def _draw_bubble(self, p, w, alpha):
        text = self._bubble_text
        f = QFont('Microsoft YaHei', 10, QFont.Bold); p.setFont(f)
        metrics = p.fontMetrics()
        max_w = int(w * 0.85)
        lines = []; cur = ''
        for ch in text:
            if metrics.horizontalAdvance(cur + ch) > max_w:
                lines.append(cur); cur = ch
            else: cur += ch
        if cur: lines.append(cur)
        lines = lines[:3]
        line_h = metrics.height()
        bh = line_h * len(lines) + 16
        bw = max(max_w // 2, min(max_w, max(metrics.horizontalAdvance(l) for l in lines) + 24))
        bx = (w - bw) // 2; by = 2
        p.save()
        grad = QLinearGradient(bx, by, bx, by + bh)
        grad.setColorAt(0, QColor(255, 250, 255, int(248*alpha)))
        grad.setColorAt(1, QColor(228, 222, 255, int(245*alpha)))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(QColor(170, 145, 215, int(210*alpha)), 1.5))
        p.drawRoundedRect(int(bx), int(by), int(bw), int(bh), 12, 12)
        tail = QPolygon([QPoint(w//2-7, int(by+bh)), QPoint(w//2+7, int(by+bh)), QPoint(w//2, int(by+bh+9))])
        p.drawPolygon(tail)
        p.setPen(QColor(70, 50, 110, int(255*alpha)))
        ty = by + 8
        for line in lines:
            p.drawText(int(bx), int(ty), int(bw), int(line_h), Qt.AlignCenter, line)
            ty += line_h
        p.restore()

    def cleanup(self):
        try: self._timer.stop()
        except Exception: pass
        try:
            if self._video_timer:
                self._video_timer.stop()
        except Exception: pass

# ============================================================
# 说明书窗口
# ============================================================
class HelpWindow(QWidget):
    close_with_voice = pyqtSignal()
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('尤诺团子桌宠 V6 · 使用说明')
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.resize(520, 620)
        self.setStyleSheet("""
            QWidget { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #faf5ff, stop:1 #ece6ff); }
            QLabel { color: #4a3560; font-family: 'Microsoft YaHei'; }
            QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #b89ae0, stop:1 #d4b3f0);
                          color: #fff; border: none; border-radius: 8px; padding: 8px 24px;
                          font-family: 'Microsoft YaHei'; font-size: 11pt; font-weight: bold; }
            QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #a88ad0, stop:1 #c4a3e0); }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(6)

        title = QLabel('尤诺团子桌宠 V6')
        title.setStyleSheet('font-size: 20pt; font-weight: bold; color: #6a4a9a;')
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel('七丘四方殿谕女 · 团子形态')
        subtitle.setStyleSheet('font-size: 10pt; color: #9a7ac0;')
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)
        layout.addSpacing(10)

        help_text = QLabel(
            "<b>【基本操作】</b><br>"
            "• 鼠标悬停 — 团子眼睛跟随鼠标方向<br>"
            "• 单击头部 — 摸头（哼~才不是特意让你摸的呢~）<br>"
            "• 单击脸部 — 戳脸（哇塞！你干嘛戳我脸啦！）<br>"
            "• 单击身体 — 喂食（嗯~吧唧吧唧，好好吃！）<br>"
            "• 左键双击 — 摸头<br>"
            "• 左键拖动 — 移动桌宠（喂喂喂！快放我下来啦！）<br>"
            "• 滚轮 — 调整大小（80~500px）<br>"
            "• 右键 — 打开菜单（含跟我说话/喂食/晚安/使用说明等）<br><br>"
            "<b>【六情绪状态】</b><br>"
            "平静（呼吸微动）/ 开心（弹跳）/ 生气（抖动）/ 难过（缩小）<br>"
            "惊讶（拉伸+偷看动画）/ 傲娇（侧转）<br><br>"
            "<b>【LLM 对话】</b><br>"
            "首次使用需配置 API：右键 → API 设置<br>"
            "支持 OpenAI 兼容接口（DeepSeek / 通义 / 豆包 / OpenAI 等）<br>"
            "尤诺会自动回复并输出情绪标签驱动动画<br><br>"
            "<b>【语音】</b><br>"
            "默认 Edge TTS 在线语音（晓萱少女声线），可切换 Windows 本地 SAPI<br>"
            "长文本（>80字或含代码）自动跳过语音，只显示气泡<br>"
            "5条语气词：摸头 / 戳脸(哇塞) / 拖拽 / 喂食 / 晚安<br><br>"
            "<b>【特效】</b><br>"
            "LLM 回复可触发：心形 / 星光 / 音符 / 月亮符文 / 月蚀黑雾<br><br>"
            "<b>【菜单】</b><br>"
            "跟我说话 / 喂食 / 晚安 / 戳脸 / 随机语气词 / 调整大小<br>"
            "置顶开关 / 跟随鼠标 / 语音开关 / API 设置 / 使用说明 / 退出<br><br>"
            "<b>【配置文件】</b><br>"
            "EXE 同目录 yuno_v6_config.json，保存 API 设置和对话历史"
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet('font-size: 9.5pt; line-height: 1.6;')

        scroll = QScrollArea()
        scroll.setWidget(help_text)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet('QScrollArea { border: 2px solid #c8b0e8; border-radius: 10px; background: rgba(255,255,255,180); }')
        layout.addWidget(scroll, 1)
        layout.addSpacing(10)

        close_btn = QPushButton('知道了')
        close_btn.clicked.connect(self._on_close_clicked)
        layout.addWidget(close_btn, alignment=Qt.AlignCenter)

    def _on_close_clicked(self):
        self.close_with_voice.emit()
        self.close()

    def closeEvent(self, e):
        self.closed.emit()
        super().closeEvent(e)

# ============================================================
# 二次元菜单
# ============================================================
class AnimeMenu(QMenu):
    def __init__(self, title='', parent=None):
        super().__init__(title, parent)
        self.setStyleSheet("""
            QMenu {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgba(255,245,255,250), stop:1 rgba(225,220,255,248));
                border: 2px solid rgba(170,140,215,215);
                border-radius: 14px; padding: 8px;
            }
            QMenu::item {
                padding: 9px 30px; border-radius: 9px; margin: 2px;
                color: #523570; font-family: "Microsoft YaHei"; font-size: 10.5pt;
            }
            QMenu::item:selected {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 rgba(195,165,240,215), stop:1 rgba(230,185,255,215));
                color: #321550;
            }
            QMenu::separator { height: 1px; background: rgba(170,140,215,100); margin: 5px 14px; }
        """)


# ============================================================
# V6 月夜星空主题菜单（纯QSS+SVG图标+轻量QWidget）
# ============================================================
_svg_cache = {}
def load_svg_icon(name, size=20):
    key = (name, size)
    if key in _svg_cache:
        return _svg_cache[key]
    path = os.path.join(ASSETS, 'icons', f'{name}.svg')
    if not os.path.exists(path):
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        _svg_cache[key] = pm
        return pm
    renderer = QSvgRenderer(path)
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    renderer.render(painter)
    painter.end()
    _svg_cache[key] = pm
    return pm


class V6SectionTitle(QWidget):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self._text = text
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setFont(QFont('Microsoft YaHei', 10, QFont.Bold))
        p.setPen(QColor('#e8c870'))
        p.drawText(10, 0, 80, int(self.height()), Qt.AlignVCenter | Qt.AlignLeft, self._text)
        p.setPen(QPen(QColor(120, 90, 160, 100), 1))
        p.drawLine(90, self.height()//2, self.width()-10, self.height()//2)
        p.end()


class PetWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self._help_window = None
        self._ui_open = False  # UI界面打开时暂停鼠标跟随

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setMouseTracking(True)
        self.setWindowTitle('尤诺桌宠v6')

        self._drag_pos = None
        self._drag_moved = False
        self._click_time = 0
        self._double_click = False
        self._llm_worker = None
        self._tts_worker = None

        pet_cfg = self.cfg.get('pet', {})
        self._pet_size = pet_cfg.get('size', 200)
        self._follow = pet_cfg.get('follow_mouse', False)
        self._topmost = pet_cfg.get('always_on_top', True)

        self._tone_effects = {}
        self._load_tone_effects()

        self._pet = DangoWidget(self)
        h = int(self._pet_size * 1.15)
        self._pet.setFixedSize(self._pet_size, h)
        self.resize(self._pet_size, h)



        if self._follow:
            self._follow_timer = QTimer(self)
            self._follow_timer.timeout.connect(self._follow_mouse)
            self._follow_timer.start(30)

        if pet_cfg.get('auto_idle_talk', True):
            self._idle_timer = QTimer(self)
            self._idle_timer.timeout.connect(self._idle_talk)
            self._idle_timer.start(120000)

        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - self.width() - 50, screen.height() - self.height() - 100)
        QTimer.singleShot(500, lambda: self._trigger('pat'))

    def _load_tone_effects(self):
        for key, info in TONE_MAP.items():
            path = os.path.join(VOICE_DIR, info['file'])
            if os.path.exists(path):
                fx = QSoundEffect(self)
                fx.setSource(QUrl.fromLocalFile(path))
                fx.setVolume(0.85)
                self._tone_effects[key] = fx

    # ---- 鼠标交互 ----
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()
            self._drag_moved = False
            self._double_click = False
            self._click_y_ratio = e.y() / max(1, self.height())
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
                    # 双击 = 摸头
                    self._double_click = True
                    self._trigger('pat')
                    self._click_time = 0
                else:
                    self._click_time = now
                    QTimer.singleShot(280, self._check_single_click)

    def _check_single_click(self):
        if not self._double_click and self._click_time > 0:
            # 单击按位置触发不同互动
            ratio = getattr(self, '_click_y_ratio', 0.5)
            if ratio < 0.35:
                # 头部 = 摸头
                self._trigger('pat')
            elif ratio < 0.65:
                # 脸部 = 戳脸
                self._trigger('poke')
            else:
                # 身体 = 喂食
                self._trigger('feed')
        self._double_click = False

    def wheelEvent(self, e):
        delta = e.angleDelta().y() / 120
        self._pet_size = max(80, min(500, self._pet_size + int(delta * 20)))
        h = int(self._pet_size * 1.15)
        self._pet.setFixedSize(self._pet_size, h)
        self.resize(self._pet_size, h)
        self._pet.set_scale(self._pet_size / 200.0)
        self.cfg['pet']['size'] = self._pet_size
        save_config(self.cfg)

    def _follow_mouse(self):
        if not self._follow or self._drag_pos is not None or self._ui_open: return
        try:
            c = QCursor.pos()
            # 桌宠位于鼠标中下方：水平居中，鼠标在团子约60%高度处
            tx = c.x() - self.width() // 2
            ty = c.y() - int(self.height() * 0.55)
            cur = self.pos()
            dx = tx - cur.x()
            dy = ty - cur.y()
            dist = (dx*dx + dy*dy) ** 0.5
            # 距离自适应：远时快速靠近，近时缓慢平滑
            if dist > 200:
                speed = 0.25
            elif dist > 80:
                speed = 0.18
            else:
                speed = 0.10
            self.move(int(cur.x() + dx * speed), int(cur.y() + dy * speed))
        except Exception: pass

    # ---- 语气词 ----
    def _trigger(self, key):
        # V8：翘腿动作特殊处理
        if key == 'legup':
            try:
                self._pet.set_emotion('chibi')
                self._pet.set_effect('星光')
                self._pet.set_bubble('哼~这个姿势怎么样？')
                QTimer.singleShot(5000, lambda: self._pet.set_emotion('happy'))
            except Exception: traceback.print_exc()
            return
        try:
            info = TONE_MAP[key]
            self._pet.set_emotion(info['emotion'])
            self._pet.set_bubble(info['text'])
            self._pet.set_effect('无')
            if key in self._tone_effects:
                fx = self._tone_effects[key]
                if fx.isPlaying(): fx.stop()
                fx.play()
                self._pet.set_speaking(True)
                # 语音时长估算（加长版约2-4秒）
                dur = max(2000, len(info['text']) * 180)
                QTimer.singleShot(dur, lambda: self._pet.set_speaking(False))
        except Exception: traceback.print_exc()

    # ---- LLM 对话 ----
    def _open_chat(self):
        self._ui_open = True
        text, ok = QInputDialog.getText(self, '跟尤诺说话', '说点什么吧：', QLineEdit.Normal, '')
        self._ui_open = False
        if ok and text.strip():
            self._chat(text.strip())

    def _chat(self, user_text):
        if self._llm_worker and self._llm_worker.isRunning():
            self._pet.set_bubble('（正在思考…）')
            return
        messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
        history = self.cfg.get('conversation', [])[-6:]
        for msg in history: messages.append(msg)
        messages.append({'role': 'user', 'content': user_text})
        self._pet.set_bubble('…')
        self._pet.set_emotion('happy')
        self._llm_worker = LLMWoker(self.cfg, messages, self)
        self._llm_worker.response_ready.connect(self._on_llm_response)
        self._llm_worker.error_occurred.connect(self._on_llm_error)
        self._llm_worker.start()

    def _on_llm_response(self, text, emotion, action, effect):
        self._pet.set_bubble(text)
        self._pet.set_emotion(emotion)
        self._pet.set_effect(effect)
        self.cfg.setdefault('conversation', []).append({'role': 'user', 'content': '...'})
        self.cfg['conversation'].append({'role': 'assistant', 'content': text})
        if len(self.cfg['conversation']) > 20:
            self.cfg['conversation'] = self.cfg['conversation'][-20:]
        save_config(self.cfg)
        if self.cfg.get('tts', {}).get('enabled', True):
            self._speak(text)

    def _on_llm_error(self, err):
        self._pet.set_bubble(f'（{err}）')
        self._pet.set_emotion('sad')

    # ---- TTS ----
    def _speak(self, text):
        if self._tts_worker and self._tts_worker.isRunning(): return
        self._tts_worker = TTSWorker(text, self.cfg, self)
        self._tts_worker.playback_started.connect(lambda: self._pet.set_speaking(True))
        self._tts_worker.playback_finished.connect(lambda: self._pet.set_speaking(False))
        self._tts_worker.start()

    # ---- 空闲闲聊 ----
    def _idle_talk(self):
        if self._llm_worker and self._llm_worker.isRunning(): return
        if random.random() < 0.4:
            prompts = ['主人在干嘛呢？', '哼，别只顾着工作嘛', '我早预见你会累的', '要不要休息一下？']
            self._chat(random.choice(prompts))

    # ---- 右键菜单 ----
    def _show_menu(self, pos):
        self._ui_open = True
        # 每次打开重新创建菜单，确保资源干净
        if hasattr(self, '_v7_menu') and self._v7_menu is not None:
            try:
                self._v7_menu.close()
                self._v7_menu.deleteLater()
            except Exception:
                pass
            self._v7_menu = None
        self._v7_menu = V7Menu(self)
        self._v7_menu.closed.connect(self._on_menu_closed)
        # V7Menu是QWidget不是QMenu，用move+show代替popup
        screen = QApplication.primaryScreen().availableGeometry()
        mx = pos.x()
        my = pos.y()
        if mx + self._v7_menu.width() > screen.right():
            mx = screen.right() - self._v7_menu.width()
        if my + self._v7_menu.height() > screen.bottom():
            my = screen.bottom() - self._v7_menu.height()
        self._v7_menu.move(max(0, mx), max(0, my))
        self._v7_menu.show()
        self._v7_menu.raise_()
        self._v7_menu.activateWindow()

    def _on_menu_closed(self):
        self._ui_open = False
        # 延迟销毁菜单对象，释放资源
        try:
            if hasattr(self, '_v7_menu') and self._v7_menu is not None:
                self._v7_menu.deleteLater()
                self._v7_menu = None
        except Exception:
            pass

    def _set_size(self, sz):
        self._pet_size = sz
        h = int(sz * 1.15)
        self._pet.setFixedSize(sz, h)
        self.resize(sz, h)
        self._pet.set_scale(sz / 200.0)
        self.cfg['pet']['size'] = sz
        save_config(self.cfg)

    def _toggle_top(self, on):
        self._topmost = on
        flags = self.windowFlags()
        if on: flags |= Qt.WindowStaysOnTopHint
        else: flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()
        self.cfg['pet']['always_on_top'] = on
        save_config(self.cfg)

    def _toggle_follow(self, on):
        self._follow = on
        if on and not hasattr(self, '_follow_timer'):
            self._follow_timer = QTimer(self)
            self._follow_timer.timeout.connect(self._follow_mouse)
            self._follow_timer.start(30)
        elif not on and hasattr(self, '_follow_timer'):
            self._follow_timer.stop()
            del self._follow_timer
        self.cfg['pet']['follow_mouse'] = on
        save_config(self.cfg)

    def _toggle_voice(self, on):
        self.cfg['tts']['enabled'] = on
        save_config(self.cfg)

    def _open_settings(self):
        self._ui_open = True
        try:
            llm = self.cfg.get('llm', {})
            tts = self.cfg.get('tts', {})
            base, ok = QInputDialog.getText(self, 'API 设置 - 1/4', 'API Base URL（OpenAI 兼容）：', QLineEdit.Normal, llm.get('api_base', 'https://api.deepseek.com/v1'))
            if not ok: return
            if base.strip(): llm['api_base'] = base.strip()
            key, ok = QInputDialog.getText(self, 'API 设置 - 2/4', 'API Key：', QLineEdit.Password, llm.get('api_key', ''))
            if not ok: return
            llm['api_key'] = key.strip()
            model, ok = QInputDialog.getText(self, 'API 设置 - 3/4', '模型名称：', QLineEdit.Normal, llm.get('model', 'deepseek-chat'))
            if not ok: return
            if model.strip(): llm['model'] = model.strip()
            engine, ok = QInputDialog.getItem(self, 'API 设置 - 4/4', 'TTS 引擎：', ['edge (Edge TTS 在线)', 'sapi (Windows 本地)'], 0 if tts.get('engine', 'edge') == 'edge' else 1, False)
            if not ok: return
            tts['engine'] = 'edge' if 'edge' in engine else 'sapi'
            self.cfg['llm'] = llm
            self.cfg['tts'] = tts
            save_config(self.cfg)
            self._pet.set_bubble('设置已保存~')
            self._pet.set_emotion('happy')
        finally:
            self._ui_open = False

    def _show_help(self):
        if self._help_window is None:
            self._help_window = HelpWindow()
            self._help_window.close_with_voice.connect(self._play_help_close_voice)
            self._help_window.closed.connect(self._on_ui_closed)
        self._ui_open = True
        self._help_window.show()
        self._help_window.raise_()
        self._help_window.activateWindow()

    def _on_ui_closed(self):
        self._ui_open = False

    def _play_help_close_voice(self):
        # 点击"知道了"后播放尤诺声线预录语音，不退出程序
        self._pet.set_bubble('知道了吗？嘿嘿')
        self._pet.set_emotion('tsundere')
        if 'know_you' in self._tone_effects:
            fx = self._tone_effects['know_you']
            fx.stop()
            fx.play()

    def closeEvent(self, e):
        try:
            if hasattr(self, '_follow_timer'): self._follow_timer.stop()
            if hasattr(self, '_idle_timer'): self._idle_timer.stop()
            if self._llm_worker: self._llm_worker.wait(2000)
            if self._tts_worker: self._tts_worker.wait(2000)
            for fx in self._tone_effects.values():
                try: fx.stop()
                except: pass
            self._pet.cleanup()
            if self._help_window: self._help_window.close()
        except Exception: pass
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
        emotions = ['happy', 'angry', 'sad', 'surprised']
        for i, emo in enumerate(emotions):
            QTimer.singleShot(500 + i * 800, lambda e=emo: w._pet.set_emotion(e))
        QTimer.singleShot(6500, app.quit)
        sys.exit(app.exec_())
    w = PetWindow()
    w.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
