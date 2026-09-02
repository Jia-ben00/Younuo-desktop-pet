# -*- coding: utf-8 -*-
r"""
鸣潮 · 尤诺团子 桌面宠物 V4 (Bongo Cat 版)
- 微信官方尤诺表情包多帧动画（raise/play/kick/peeking/holdsign）
- 六情绪状态机驱动表情包切换
- LLM API 对话（OpenAI 兼容，跑完整主提示词）
- TTS 实时语音（edge-tts 优先，Windows SAPI 兜底）
- 情绪/动作/特效标签解析驱动动画
- 透明无边框置顶，左键拖动/点击对话，右键菜单，滚轮缩放
- 稳定性：全 QThread 异步、异常防护、资源正确释放
"""
import sys, os, json, re, time, random, traceback, tempfile, subprocess, math

from PyQt5.QtWidgets import (QApplication, QWidget, QMenu, QAction,
                             QInputDialog, QLineEdit)
from PyQt5.QtCore import (Qt, QTimer, QPoint, QPointF, QRectF, QSize,
                            pyqtSignal, QUrl, QObject, QThread)
from PyQt5.QtGui import (QPainter, QPixmap, QImage, QColor, QFont,
                           QCursor, QLinearGradient, QRadialGradient, QBrush,
                           QPen, QPolygonF, QPainterPath)
from PyQt5.QtMultimedia import QSoundEffect

# ============================================================
# 资源路径
# ============================================================
def resource_path(rel):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, rel)
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, '..', rel)

def config_path():
    """配置文件路径：优先 EXE 同目录，其次用户目录"""
    if hasattr(sys, '_MEIPASS'):
        exe_dir = os.path.dirname(sys.executable)
        return os.path.join(exe_dir, 'yuno_v4_config.json')
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'yuno_v4_config.json')

ASSETS = resource_path('assets')
STICKER_DIR = os.path.join(ASSETS, 'stickers')
VOICE_DIR = os.path.join(ASSETS, 'voice')

# ============================================================
# 情绪 → 表情包映射
# ============================================================
EMOTION_STICKER = {
    'calm':      {'pack': 'raise',    'fps': 2,  'loop': True,  'name': '平静'},
    'happy':     {'pack': 'play',     'fps': 12, 'loop': True,  'name': '开心'},
    'angry':     {'pack': 'kick',     'fps': 15, 'loop': True,  'name': '生气'},
    'sad':       {'pack': 'peeking',  'fps': 8,  'loop': True,  'name': '难过'},
    'surprised': {'pack': 'peeking',  'fps': 12, 'loop': True,  'name': '惊讶'},
    'tsundere':  {'pack': 'holdsign', 'fps': 3,  'loop': True,  'name': '傲娇'},
}

EMOTION_DURATION = {
    'calm': 0, 'happy': 3.0, 'angry': 2.5, 'sad': 3.0,
    'surprised': 2.0, 'tsundere': 3.5,
}

# 语气词映射（复用 V3 语音）
TONE_MAP = {
    'pat':   {'file': 'pat.wav',   'emotion': 'happy',     'text': '哼~'},
    'poke':  {'file': 'poke.wav',  'emotion': 'surprised', 'text': '呀！'},
    'drag':  {'file': 'drag.wav',  'emotion': 'angry',     'text': '喂喂！'},
    'feed':  {'file': 'feed.wav',  'emotion': 'happy',     'text': '吧唧吧唧'},
    'sleep': {'file': 'sleep.wav', 'emotion': 'tsundere',  'text': '不准松开我'},
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
        'engine': 'edge',  # edge | sapi
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
    'conversation': [],  # 对话历史
}

def load_config():
    try:
        p = config_path()
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            # 合并默认值
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
# 系统提示词（主提示词）
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
# LLM 对话 Worker (QThread)
# ============================================================
class LLMWoker(QThread):
    response_ready = pyqtSignal(str, str, str, str)  # text, emotion, action, effect
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
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {llm["api_key"]}',
            }
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
            # 解析标签
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
        # 提取情绪
        m = re.search(r'【情绪[：:]\s*([^】]+)】', content)
        if m:
            emo_map = {'开心':'happy','生气':'angry','难过':'sad','惊讶':'surprised','傲娇':'tsundere','平静':'calm'}
            emotion = emo_map.get(m.group(1).strip(), 'calm')
        # 提取动作
        m = re.search(r'【动作[：:]\s*([^】]+)】', content)
        if m:
            action = m.group(1).strip()
        # 提取特效
        m = re.search(r'【特效[：:]\s*([^】]+)】', content)
        if m:
            effect = m.group(1).strip()
        # 移除标签行，保留纯文本
        text = re.sub(r'【[^】]*】', '', content).strip()
        # 移除可能残留的标签关键词行
        text = re.sub(r'^(情绪|动作|特效|视频)[：:].*$', '', text, flags=re.MULTILINE).strip()
        if not text:
            text = '……'
        return text, emotion, action, effect

# ============================================================
# TTS Worker (QThread)
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
            if not tts.get('enabled'):
                return
            # 长文本跳过
            if len(self.text) > 80 or any(c in self.text for c in ['```', 'http', 'import ', 'def ', 'class ']):
                return
            engine = tts.get('engine', 'edge')
            if engine == 'edge':
                self._edge_tts()
            else:
                self._sapi_tts()
        except Exception as e:
            self.error_occurred.emit(f'TTS 错误: {str(e)[:80]}')

    def _edge_tts(self):
        try:
            import asyncio
            import edge_tts
            tts = self.cfg['tts']
            voice = tts.get('voice', 'zh-CN-XiaoxiaoNeural')
            rate = tts.get('rate', '+10%')
            # 生成临时 mp3
            tmp = os.path.join(tempfile.gettempdir(), f'yuno_tts_{int(time.time()*1000)}.mp3')
            communicate = edge_tts.Communicate(self.text, voice, rate=rate)
            asyncio.run(communicate.save(tmp))
            if os.path.exists(tmp) and os.path.getsize(tmp) > 100:
                self.playback_started.emit()
                # 用 QSoundEffect 播放 mp3 不行，用系统默认播放器后台播放
                # Windows: 用 powershell 的 System.Media 不行(只支持wav)，用 cmd start
                # 改用 playsound 或简单的 subprocess
                try:
                    # 尝试用 Windows Media Player COM 播放
                    ps = (f'$player = New-Object System.Media.SoundPlayer; '
                          f'# mp3 not supported by SoundPlayer, use WMP COM\n'
                          f'$wmp = New-Object -ComObject WMPlayer.OCX; '
                          f'$wmp.URL = {tmp!r}; '
                          f'$wmp.controls.play(); '
                          f'Start-Sleep -Milliseconds 500; '
                          f'while ($wmp.playState -ne 1) {{ Start-Sleep -Milliseconds 200 }}; '
                          f'[System.Runtime.Interopservices.Marshal]::ReleaseComObject($wmp) | Out-Null')
                    # 不等待，后台播放
                    subprocess.Popen(['powershell', '-NoProfile', '-WindowStyle', 'Hidden',
                                      '-Command', ps], creationflags=0x08000000)
                    # 估算播放时长后发 finished
                    duration = max(1.5, len(self.text) * 0.25)
                    time.sleep(duration + 0.5)
                except Exception:
                    pass
                finally:
                    self.playback_finished.emit()
                    try: os.remove(tmp)
                    except: pass
        except ImportError:
            self._sapi_tts()
        except Exception as e:
            # edge-tts 失败回退 SAPI
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
# 表情包帧动画 Widget
# ============================================================
class StickerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setMouseTracking(True)

        self._frames = {}       # pack -> [QPixmap]
        self._frame_sizes = {}  # pack -> (w, h)
        self._load_all()

        self._emotion = 'calm'
        self._emotion_start = time.time()
        self._frame_idx = 0
        self._time = 0.0
        self._target_scale = 1.0
        self._cur_scale = 1.0
        self._bubble_text = ''
        self._bubble_time = 0
        self._effect = '无'
        self._speaking = False
        self._speak_start = 0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def _load_all(self):
        for emo, info in EMOTION_STICKER.items():
            pack = info['pack']
            if pack in self._frames:
                continue
            d = os.path.join(STICKER_DIR, pack)
            if not os.path.isdir(d):
                continue
            frames = []
            files = sorted([f for f in os.listdir(d) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
            for f in files:
                try:
                    pix = QPixmap(os.path.join(d, f))
                    if not pix.isNull():
                        frames.append(pix)
                except Exception:
                    pass
            if frames:
                self._frames[pack] = frames
                self._frame_sizes[pack] = (frames[0].width(), frames[0].height())

    def set_emotion(self, emo):
        if emo not in EMOTION_STICKER:
            return
        if emo != self._emotion:
            self._emotion = emo
            self._emotion_start = time.time()
            self._frame_idx = 0

    def set_effect(self, eff):
        self._effect = eff

    def set_bubble(self, text):
        self._bubble_text = text
        self._bubble_time = time.time()

    def set_scale(self, s):
        self._target_scale = max(0.4, min(3.0, s))

    def set_speaking(self, on):
        self._speaking = on
        if on:
            self._speak_start = time.time()

    def _tick(self):
        self._time += 0.033
        # 情绪持续时间
        dur = EMOTION_DURATION.get(self._emotion, 0)
        if dur > 0 and time.time() - self._emotion_start > dur:
            self._emotion = 'calm'
            self._emotion_start = time.time()
            self._frame_idx = 0
        # 缩放缓动
        self._cur_scale += (self._target_scale - self._cur_scale) * 0.15
        self.update()

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
        info = EMOTION_STICKER.get(self._emotion, EMOTION_STICKER['calm'])
        pack = info['pack']

        if pack not in self._frames or not self._frames[pack]:
            # 兜底：画一个蓝色圆
            p.setBrush(QColor(100, 150, 230))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRectF(w//2-50, h//2-50, 100, 100))
            p.end()
            return

        frames = self._frames[pack]
        fw, fh = self._frame_sizes[pack]
        fps = info.get('fps', 8)

        # 帧索引
        if info.get('loop', True):
            self._frame_idx = int(self._time * fps) % len(frames)
        else:
            self._frame_idx = min(int(self._time * fps), len(frames) - 1)

        pix = frames[self._frame_idx]

        # 计算绘制尺寸（保持比例，适配窗口）
        target_h = h * 0.85
        scale = target_h / fh
        draw_w = fw * scale * self._cur_scale
        draw_h = fh * scale * self._cur_scale
        dx = (w - draw_w) / 2
        dy = (h - draw_h) / 2 + h * 0.05

        # 说话时轻微弹跳
        bounce_y = 0
        if self._speaking:
            bounce_y = abs(math.sin(time.time() * 12)) * 4
        # 平静时呼吸
        if self._emotion == 'calm':
            breath = 1.0 + math.sin(self._time * 2) * 0.015
            draw_w *= breath
            draw_h *= breath
            dx = (w - draw_w) / 2
            dy = (h - draw_h) / 2 + h * 0.05

        # 阴影
        shadow_rect = QRectF(w//2 - draw_w*0.3, dy + draw_h*0.92, draw_w*0.6, draw_h*0.08)
        sg = QRadialGradient(shadow_rect.center(), draw_w*0.35)
        sg.setColorAt(0, QColor(0,0,0,40))
        sg.setColorAt(1, QColor(0,0,0,0))
        p.setBrush(QBrush(sg))
        p.setPen(Qt.NoPen)
        p.drawEllipse(shadow_rect)

        # 绘制表情包
        p.drawPixmap(QRectF(dx, dy + bounce_y, draw_w, draw_h), pix, QRectF(pix.rect()))

        # 特效粒子
        self._draw_effect(p, w, h, dx, dy, draw_w, draw_h)

        # 语音气泡
        if self._bubble_text:
            elapsed = time.time() - self._bubble_time
            if elapsed < 4.0:
                alpha = 1.0 if elapsed < 3.0 else max(0, 1.0 - (elapsed - 3.0) / 1.0)
                self._draw_bubble(p, w, alpha)

        p.end()

    def _draw_effect(self, p, w, h, dx, dy, dw, dh):
        if self._effect == '无' or not self._effect:
            return
        p.save()
        t = self._time
        cx = dx + dw / 2
        cy = dy + dh * 0.3
        if self._effect == '心形':
            p.setBrush(QColor(255, 100, 130, 180))
            p.setPen(Qt.NoPen)
            for i in range(3):
                ang = t * 1.5 + i * 2.1
                r = 30 + (t * 20 + i * 15) % 50
                hx = cx + math.cos(ang) * r * 0.5
                hy = cy - (t * 30 + i * 20) % 60
                size = 8 + 4 * math.sin(t*3+i)
                # 简单心形
                p.drawEllipse(QPointF(hx - size*0.4, hy), size*0.5, size*0.5)
                p.drawEllipse(QPointF(hx + size*0.4, hy), size*0.5, size*0.5)
                tri = QPolygonF([QPointF(hx-size*0.7, hy+size*0.2),
                                 QPointF(hx+size*0.7, hy+size*0.2),
                                 QPointF(hx, hy+size*1.1)])
                p.drawPolygon(tri)
        elif self._effect == '星光':
            p.setBrush(QColor(255, 240, 150, 200))
            p.setPen(Qt.NoPen)
            for i in range(5):
                ang = t * 2 + i * 1.26
                r = 25 + (t * 15 + i * 10) % 45
                sx = cx + math.cos(ang) * r
                sy = cy + math.sin(ang) * r * 0.6 - (t*10) % 30
                size = 4 + 3 * math.sin(t*4+i)
                p.drawEllipse(QPointF(sx, sy), size, size)
        elif self._effect == '音符':
            p.setPen(QColor(150, 100, 200, 200))
            f = QFont('Microsoft YaHei', 12, QFont.Bold)
            p.setFont(f)
            for i, note in enumerate(['♪', '♫', '♬']):
                ny = cy - (t * 25 + i * 20) % 70
                nx = cx + math.sin(t*2 + i) * 25
                p.drawText(QPointF(nx, ny), note)
        elif self._effect == '月亮符文':
            p.setPen(QPen(QColor(200, 180, 255, 150), 2))
            p.setBrush(Qt.NoBrush)
            rad = 35 + 10 * math.sin(t*2)
            p.drawEllipse(QPointF(cx, cy), rad, rad)
            p.drawArc(QRectF(cx-rad*0.7, cy-rad*0.7, rad*1.4, rad*1.4),
                      int(45*16), int(270*16))
        elif self._effect == '月蚀黑雾':
            p.setBrush(QColor(60, 40, 80, 100))
            p.setPen(Qt.NoPen)
            for i in range(4):
                ox = cx + math.sin(t*1.5+i*1.5) * 30
                oy = cy - 20 - (t*15+i*10) % 50
                p.drawEllipse(QPointF(ox, oy), 12, 8)
        p.restore()

    def _draw_bubble(self, p, w, alpha):
        text = self._bubble_text
        # 自动换行
        f = QFont('Microsoft YaHei', 10, QFont.Bold)
        p.setFont(f)
        metrics = p.fontMetrics()
        max_w = int(w * 0.8)
        lines = []
        cur = ''
        for ch in text:
            if metrics.horizontalAdvance(cur + ch) > max_w:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        if cur:
            lines.append(cur)
        lines = lines[:3]  # 最多3行

        line_h = metrics.height()
        bh = line_h * len(lines) + 16
        bw = max(max_w // 2, min(max_w, max(metrics.horizontalAdvance(l) for l in lines) + 24))
        bx = (w - bw) // 2
        by = 2

        p.save()
        grad = QLinearGradient(bx, by, bx, by + bh)
        grad.setColorAt(0, QColor(255, 250, 255, int(245*alpha)))
        grad.setColorAt(1, QColor(230, 225, 255, int(240*alpha)))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(QColor(175, 155, 215, int(200*alpha)), 1.5))
        p.drawRoundedRect(QRectF(bx, by, bw, bh), 12, 12)
        # 气泡尾巴
        tail = QPolygonF([QPointF(w//2-7, by+bh),
                          QPointF(w//2+7, by+bh),
                          QPointF(w//2, by+bh+9)])
        p.drawPolygon(tail)
        p.setPen(QColor(75, 55, 115, int(255*alpha)))
        ty = by + 8
        for line in lines:
            p.drawText(QRectF(bx, ty, bw, line_h), Qt.AlignCenter, line)
            ty += line_h
        p.restore()

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
                    stop:0 rgba(255,245,255,248), stop:1 rgba(225,220,255,245));
                border: 2px solid rgba(170,140,215,210);
                border-radius: 14px; padding: 8px;
            }
            QMenu::item {
                padding: 9px 30px; border-radius: 9px; margin: 2px;
                color: #523570; font-family: "Microsoft YaHei"; font-size: 10.5pt;
            }
            QMenu::item:selected {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 rgba(195,165,240,210), stop:1 rgba(230,185,255,210));
                color: #321550;
            }
            QMenu::separator { height: 1px; background: rgba(170,140,215,100); margin: 5px 14px; }
        """)

# ============================================================
# 主窗口
# ============================================================
class PetWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setMouseTracking(True)
        self.setWindowTitle('尤诺桌宠v4')

        self._drag_pos = None
        self._drag_moved = False
        self._click_time = 0
        self._double_click = False
        self._llm_worker = None
        self._tts_worker = None
        self._idle_timer = None

        pet_cfg = self.cfg.get('pet', {})
        self._pet_size = pet_cfg.get('size', 200)
        self._follow = pet_cfg.get('follow_mouse', False)
        self._topmost = pet_cfg.get('always_on_top', True)

        # 语音引擎（语气词）
        self._tone_effects = {}
        self._load_tone_effects()

        # 表情包 Widget
        self._pet = StickerWidget(self)
        h = int(self._pet_size * 1.15)
        self._pet.setFixedSize(self._pet_size, h)
        self.resize(self._pet_size, h)

        # 跟随鼠标
        if self._follow:
            self._follow_timer = QTimer(self)
            self._follow_timer.timeout.connect(self._follow_mouse)
            self._follow_timer.start(50)

        # 空闲闲聊
        if pet_cfg.get('auto_idle_talk', True):
            self._idle_timer = QTimer(self)
            self._idle_timer.timeout.connect(self._idle_talk)
            self._idle_timer.start(120000)  # 每2分钟

        # 初始位置
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - self.width() - 50, screen.height() - self.height() - 100)

        # 开场
        QTimer.singleShot(500, lambda: self._trigger('pat'))

    def _load_tone_effects(self):
        for key, info in TONE_MAP.items():
            path = os.path.join(VOICE_DIR, info['file'])
            if os.path.exists(path):
                fx = QSoundEffect(self)
                fx.setSource(QUrl.fromLocalFile(path))
                fx.setVolume(0.8)
                self._tone_effects[key] = fx

    # ---- 鼠标交互 ----
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
                    QTimer.singleShot(280, self._check_single_click)

    def _check_single_click(self):
        if not self._double_click and self._click_time > 0:
            # 单击 → 打开对话
            self._open_chat()
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
        if not self._follow or self._drag_pos is not None:
            return
        try:
            c = QCursor.pos()
            tx = c.x() - self.width() // 2 + 30
            ty = c.y() + 20
            cur = self.pos()
            self.move(int(cur.x() + (tx - cur.x()) * 0.05),
                      int(cur.y() + (ty - cur.y()) * 0.05))
        except Exception:
            pass

    # ---- 语气词触发 ----
    def _trigger(self, key):
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
                QTimer.singleShot(1500, lambda: self._pet.set_speaking(False))
        except Exception:
            traceback.print_exc()

    # ---- LLM 对话 ----
    def _open_chat(self):
        text, ok = QInputDialog.getText(self, '跟尤诺说话', '说点什么吧：',
                                         QLineEdit.Normal, '', flags=Qt.FramelessWindowHint)
        if ok and text.strip():
            self._chat(text.strip())

    def _chat(self, user_text):
        if self._llm_worker and self._llm_worker.isRunning():
            self._pet.set_bubble('（正在思考…）')
            return

        # 构建消息
        messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
        # 加入最近对话历史（最多6轮）
        history = self.cfg.get('conversation', [])[-6:]
        for msg in history:
            messages.append(msg)
        messages.append({'role': 'user', 'content': user_text})

        self._pet.set_bubble('…')
        self._pet.set_emotion('calm')

        self._llm_worker = LLMWoker(self.cfg, messages, self)
        self._llm_worker.response_ready.connect(self._on_llm_response)
        self._llm_worker.error_occurred.connect(self._on_llm_error)
        self._llm_worker.start()

    def _on_llm_response(self, text, emotion, action, effect):
        self._pet.set_bubble(text)
        self._pet.set_emotion(emotion)
        self._pet.set_effect(effect)
        # 记录历史
        self.cfg.setdefault('conversation', []).append({'role': 'user', 'content': '...'})
        self.cfg['conversation'].append({'role': 'assistant', 'content': text})
        if len(self.cfg['conversation']) > 20:
            self.cfg['conversation'] = self.cfg['conversation'][-20:]
        save_config(self.cfg)
        # TTS
        if self.cfg.get('tts', {}).get('enabled', True):
            self._speak(text)

    def _on_llm_error(self, err):
        self._pet.set_bubble(f'（{err}）')
        self._pet.set_emotion('sad')

    # ---- TTS ----
    def _speak(self, text):
        if self._tts_worker and self._tts_worker.isRunning():
            return
        self._tts_worker = TTSWorker(text, self.cfg, self)
        self._tts_worker.playback_started.connect(lambda: self._pet.set_speaking(True))
        self._tts_worker.playback_finished.connect(lambda: self._pet.set_speaking(False))
        self._tts_worker.start()

    # ---- 空闲闲聊 ----
    def _idle_talk(self):
        if self._llm_worker and self._llm_worker.isRunning():
            return
        if random.random() < 0.4:  # 40%概率触发
            prompts = ['主人在干嘛呢？', '哼，别只顾着工作嘛', '我早预见你会累的', '要不要休息一下？']
            self._chat(random.choice(prompts))

    # ---- 右键菜单 ----
    def _show_menu(self, pos):
        menu = AnimeMenu('尤诺团子 v4', self)

        a_chat = menu.addAction('跟我说话…')
        menu.addSeparator()

        a_feed = menu.addAction('喂食 🍰')
        a_sleep = menu.addAction('晚安 🌙')
        a_random = menu.addAction('随机语气词')
        menu.addSeparator()

        size_menu = menu.addMenu('调整大小')
        for label, sz in [('小', 140), ('中', 200), ('大', 280), ('超大', 380)]:
            act = size_menu.addAction(label)
            act.triggered.connect(lambda checked, s=sz: self._set_size(s))

        a_top = menu.addAction('始终置顶')
        a_top.setCheckable(True)
        a_top.setChecked(self._topmost)

        a_follow = menu.addAction('跟随鼠标')
        a_follow.setCheckable(True)
        a_follow.setChecked(self._follow)

        a_voice = menu.addAction('语音开关')
        a_voice.setCheckable(True)
        a_voice.setChecked(self.cfg.get('tts', {}).get('enabled', True))

        menu.addSeparator()
        a_settings = menu.addAction('API 设置…')
        menu.addSeparator()
        a_quit = menu.addAction('退出程序')

        action = menu.exec_(pos)
        if action == a_chat: self._open_chat()
        elif action == a_feed: self._trigger('feed')
        elif action == a_sleep: self._trigger('sleep')
        elif action == a_random: self._trigger(random.choice(list(TONE_MAP.keys())))
        elif action == a_top: self._toggle_top(a_top.isChecked())
        elif action == a_follow: self._toggle_follow(a_follow.isChecked())
        elif action == a_voice:
            self.cfg['tts']['enabled'] = a_voice.isChecked()
            save_config(self.cfg)
        elif action == a_settings: self._open_settings()
        elif action == a_quit: self.close()

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
            self._follow_timer.start(50)
        elif not on and hasattr(self, '_follow_timer'):
            self._follow_timer.stop()
            del self._follow_timer
        self.cfg['pet']['follow_mouse'] = on
        save_config(self.cfg)

    def _open_settings(self):
        """API 设置对话框"""
        llm = self.cfg.get('llm', {})
        tts = self.cfg.get('tts', {})

        # API Base
        base, ok = QInputDialog.getText(self, 'API 设置 - 1/4',
            'API Base URL（OpenAI 兼容）：', QLineEdit.Normal,
            llm.get('api_base', 'https://api.deepseek.com/v1'))
        if not ok: return
        if base.strip(): llm['api_base'] = base.strip()

        # API Key
        key, ok = QInputDialog.getText(self, 'API 设置 - 2/4',
            'API Key：', QLineEdit.Password, llm.get('api_key', ''))
        if not ok: return
        llm['api_key'] = key.strip()

        # Model
        model, ok = QInputDialog.getText(self, 'API 设置 - 3/4',
            '模型名称：', QLineEdit.Normal, llm.get('model', 'deepseek-chat'))
        if not ok: return
        if model.strip(): llm['model'] = model.strip()

        # TTS 引擎
        engine, ok = QInputDialog.getItem(self, 'API 设置 - 4/4',
            'TTS 引擎：', ['edge (Edge TTS 在线)', 'sapi (Windows 本地)'],
            0 if tts.get('engine', 'edge') == 'edge' else 1, False)
        if not ok: return
        tts['engine'] = 'edge' if 'edge' in engine else 'sapi'

        self.cfg['llm'] = llm
        self.cfg['tts'] = tts
        save_config(self.cfg)
        self._pet.set_bubble('设置已保存~')
        self._pet.set_emotion('happy')

    def closeEvent(self, e):
        try:
            if hasattr(self, '_follow_timer'): self._follow_timer.stop()
            if self._idle_timer: self._idle_timer.stop()
            if self._llm_worker: self._llm_worker.wait(2000)
            if self._tts_worker: self._tts_worker.wait(2000)
            for fx in self._tone_effects.values():
                try: fx.stop()
                except: pass
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
        # 测试各情绪切换
        emotions = ['calm', 'happy', 'angry', 'sad', 'surprised', 'tsundere']
        for i, emo in enumerate(emotions):
            QTimer.singleShot(500 + i * 800, lambda e=emo: w._pet.set_emotion(e))
        QTimer.singleShot(6000, app.quit)
        sys.exit(app.exec_())

    w = PetWindow()
    w.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
