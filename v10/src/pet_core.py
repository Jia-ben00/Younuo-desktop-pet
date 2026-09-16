"""宠物核心逻辑 —— 与 GUI 无关的纯逻辑层。

为什么单独拆出来：

  原先所有逻辑都写在 `iuno_pet_v10.py` 里，模块顶层 `import PyQt5`，
  导致**任何逻辑都无法在没有图形环境的机器上测试**（CI 里装 Qt 又慢又需要
  显示环境）。把成长 / 好感度 / 台词解析这些纯逻辑拆到这里，
  就可以用 `pytest` 直接跑，不依赖 GUI、不依赖 Windows。

  本模块**只做计算与文件读写**，不 import 任何 Qt。
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime

# ---------------------------------------------------------------------------
# 成长 / 好感度数值（改这些常量即可调平衡，无需动主程序）
# ---------------------------------------------------------------------------

MAX_LEVEL = 20
EXP_PER_FEED = 10

MAX_FOOD = 30
FOOD_INTERVAL_SEC = 300  # 每 5 分钟产出 1 个月亮糕

MAX_AFFECTION = 100
AFFECTION_PER_FEED = 2
AFFECTION_PER_INTERACT = 1
AFFECTION_DAILY_FEED_CAP = 15
AFFECTION_DAILY_INTERACT_CAP = 20
AFFECTION_ONLINE_TICK_MIN = 10  # 在线每 10 分钟 +1

# 好感度分档：(下限, 称号, 档位序号)，从高到低匹配
AFFECTION_TIERS = [
    (100, '倾心', 5),
    (80, '心动', 4),
    (50, '亲近', 3),
    (20, '熟悉', 2),
    (0, '疏离', 1),
]


def exp_needed(level: int) -> int:
    """升到下一级所需经验。满级返回 0。"""
    if level >= MAX_LEVEL:
        return 0
    return level * 100


def get_affection_tier(affection: int) -> tuple[str, int]:
    """好感度 → (称号, 档位序号 1-5)。"""
    for floor, name, idx in AFFECTION_TIERS:
        if affection >= floor:
            return name, idx
    return '疏离', 1


# ---------------------------------------------------------------------------
# 台词解析（LLM 输出 → 结构化指令）
# ---------------------------------------------------------------------------

EMOTION_MAP = {
    '开心': 'happy',
    '生气': 'angry',
    '难过': 'sad',
    '惊讶': 'surprised',
    '傲娇': 'tsundere',
    '平静': 'calm',
}

_TAG_RE = {
    'emotion': re.compile(r'【情绪[：:]\s*([^】]+)】'),
    'action': re.compile(r'【动作[：:]\s*([^】]+)】'),
    'effect': re.compile(r'【特效[：:]\s*([^】]+)】'),
}

_ALL_TAGS_RE = re.compile(r'【[^】]*】')
_PREFIX_LINE_RE = re.compile(r'^(情绪|动作|特效|视频)[：:].*$', flags=re.MULTILINE)

EMPTY_LINE_FALLBACK = '……'
DEFAULT_EMOTION = 'calm'
DEFAULT_ACTION = '待机'
DEFAULT_EFFECT = '无'


def parse_reply(content: str) -> tuple[str, str, str, str]:
    """把 LLM 回复解析为 (台词, 情绪, 动作, 特效)。

    模型被要求用【情绪：开心】这类标记输出，这里把它们摘出来，
    正文里剩余的标记全部剥掉。正文为空时回退为 `……`，避免出现空气泡。

    情绪标记里的中文值经 EMOTION_MAP 转成内部英文 id；
    未识别的值回退为 'happy'（沿用原实现行为）。
    """
    text = content or ''
    emotion = DEFAULT_EMOTION
    action = DEFAULT_ACTION
    effect = DEFAULT_EFFECT

    m = _TAG_RE['emotion'].search(text)
    if m:
        emotion = EMOTION_MAP.get(m.group(1).strip(), 'happy')
    m = _TAG_RE['action'].search(text)
    if m:
        action = m.group(1).strip()
    m = _TAG_RE['effect'].search(text)
    if m:
        effect = m.group(1).strip()

    text = _ALL_TAGS_RE.sub('', text).strip()
    text = _PREFIX_LINE_RE.sub('', text).strip()
    if not text:
        text = EMPTY_LINE_FALLBACK
    return text, emotion, action, effect


# ---------------------------------------------------------------------------
# 存档读写：单文件多字段，必须「读-改-写」
# ---------------------------------------------------------------------------

def _atomic_write(path: str, data: dict) -> None:
    """先写临时文件再替换，避免写入中途崩溃导致存档损坏。"""
    tmp = f'{path}.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def load_save(path: str) -> dict:
    """读存档；文件缺失或损坏时返回空 dict（不抛异常）。"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def merge_save(path: str, patch: dict) -> None:
    """把 patch 合并进既有存档并落盘。

    这是**唯一**允许写存档的入口。原实现里 GrowthManager 直接全量覆盖文件，
    把 AffectionManager 写的字段（affection / date / feed_count / ...）一起抹掉 ——
    表现为「喂一次食，好感度清零」。所有写入都必须走 read-modify-write。
    """
    data = load_save(path)
    data.update(patch)
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        _atomic_write(path, data)
    except OSError:
        pass  # 存档写失败不应让桌宠崩掉


# ---------------------------------------------------------------------------
# 成长
# ---------------------------------------------------------------------------

class GrowthManager:
    """等级 / 经验 / 月亮糕。所有状态持久化到同一个存档文件。"""

    def __init__(self, save_path: str):
        self.save_path = save_path
        self.level = 1
        self.exp = 0
        self.food = 5
        self.last_food_time = time.time()
        self.lover_mode = False
        self.load()

    def load(self) -> None:
        d = load_save(self.save_path)
        self.level = int(d.get('level', 1))
        self.exp = int(d.get('exp', 0))
        self.food = int(d.get('food', 5))
        self.last_food_time = float(d.get('last_food_time', time.time()))
        self.lover_mode = bool(d.get('lover_mode', False))
        self._offline_food()

    def save(self) -> None:
        """只更新自己负责的字段，不碰存档里的其他键。"""
        merge_save(self.save_path, {
            'level': self.level,
            'exp': self.exp,
            'food': self.food,
            'last_food_time': self.last_food_time,
            'lover_mode': self.lover_mode,
        })

    def _offline_food(self, now: float | None = None) -> int:
        """离线期间累积月亮糕。返回本次补了几个。"""
        now = time.time() if now is None else now
        gained = int((now - self.last_food_time) // FOOD_INTERVAL_SEC)
        if gained > 0:
            self.food = min(MAX_FOOD, self.food + gained)
            # 保留不足一个周期的零头，否则每次登录都会丢掉余数
            self.last_food_time += gained * FOOD_INTERVAL_SEC
        return gained

    def tick_food(self, now: float | None = None) -> bool:
        """在线定时补月亮糕。真的补了才落盘。"""
        now = time.time() if now is None else now
        if now - self.last_food_time < FOOD_INTERVAL_SEC:
            return False
        self.food = min(MAX_FOOD, self.food + 1)
        self.last_food_time = now
        self.save()
        return True

    def can_feed(self) -> bool:
        return self.food > 0 and self.level < MAX_LEVEL

    def feed(self) -> tuple[bool, int]:
        """喂食。返回 (是否成功, 本次升到的等级；没升级为 0)。"""
        if not self.can_feed():
            return False, 0
        self.food -= 1
        self.exp += EXP_PER_FEED
        new_level = 0
        while self.level < MAX_LEVEL and self.exp >= exp_needed(self.level):
            self.exp -= exp_needed(self.level)
            self.level += 1
            new_level = self.level
        self.save()
        return True, new_level

    def exp_needed(self) -> int:
        return exp_needed(self.level)


# ---------------------------------------------------------------------------
# 好感度
# ---------------------------------------------------------------------------

def today_str() -> str:
    """当天日期（YYYY-MM-DD）。抽出成函数便于测试时替换时钟。"""
    return datetime.now().strftime('%Y-%m-%d')


class AffectionManager:
    """好感度 0-100，带每日上限（防止刷）。

    `clock` 是日期来源，默认取系统当天。测试时可注入固定时钟，
    从而验证「跨天重置」这类跟日期相关的分支。
    """

    def __init__(self, save_path: str, clock=today_str):
        self.save_path = save_path
        self._clock = clock
        self.affection = 0
        self._date = self._clock()
        self._feed_count = 0
        self._interact_count = 0
        self._online_minutes = 0
        self.load()

    def load(self) -> None:
        d = load_save(self.save_path)
        self.affection = int(d.get('affection', 0))
        self._date = d.get('date', self._clock())
        self._feed_count = int(d.get('feed_count', 0))
        self._interact_count = int(d.get('interact_count', 0))
        self._online_minutes = int(d.get('online_minutes', 0))
        if self._date != self._clock():
            self._date = self._clock()
            self._feed_count = 0
            self._interact_count = 0

    def save(self) -> None:
        merge_save(self.save_path, {
            'affection': self.affection,
            'date': self._date,
            'feed_count': self._feed_count,
            'interact_count': self._interact_count,
            'online_minutes': self._online_minutes,
        })

    def _roll_date(self) -> bool:
        """跨天则重置每日计数。返回是否发生了跨天。"""
        today = self._clock()
        if self._date != today:
            self._date = today
            self._feed_count = 0
            self._interact_count = 0
            return True
        return False

    def on_feed(self) -> bool:
        self._roll_date()
        if self._feed_count >= AFFECTION_DAILY_FEED_CAP:
            return False
        self.affection = min(MAX_AFFECTION, self.affection + AFFECTION_PER_FEED)
        self._feed_count += 1
        self.save()
        return True

    def on_interact(self) -> bool:
        self._roll_date()
        if self._interact_count >= AFFECTION_DAILY_INTERACT_CAP:
            return False
        self.affection = min(MAX_AFFECTION, self.affection + AFFECTION_PER_INTERACT)
        self._interact_count += 1
        self.save()
        return True

    def on_online(self, minutes: int = 1) -> bool:
        """在线时长累积，每满 AFFECTION_ONLINE_TICK_MIN 分钟 +1。"""
        self._roll_date()
        self._online_minutes += minutes
        ticks = self._online_minutes // AFFECTION_ONLINE_TICK_MIN
        if ticks <= 0:
            return False
        gained = 0
        for _ in range(ticks):
            if self.affection >= MAX_AFFECTION:
                break
            self.affection += 1
            gained += 1
        self._online_minutes %= AFFECTION_ONLINE_TICK_MIN
        if gained:
            self.save()
        return gained > 0

    @property
    def tier(self) -> tuple[str, int]:
        return get_affection_tier(self.affection)

    def can_confess(self, level: int) -> bool:
        """告白条件：满级 + 好感度满。"""
        return level >= MAX_LEVEL and self.affection >= MAX_AFFECTION
