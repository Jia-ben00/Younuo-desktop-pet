# -*- coding: utf-8 -*-
"""pet_core 单元测试。

这些测试**不依赖 PyQt5、不依赖 Windows、不需要图形环境** —— pet_core 是纯逻辑层。
在 CI 里只需 `pip install pytest` 就能跑。

覆盖三类东西：
  1. 数值逻辑（升级曲线、好感度分档、每日上限）
  2. 台词解析（正则边界：空文本回退、未知情绪、标记剥离）
  3. 存档读写（**回归测试**：喂食不能抹掉好感度 —— 这是原实现真实存在过的 bug）
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v10' / 'src'))

import pet_core as pc  # noqa: E402


# ---------------------------------------------------------------------------
# 台词解析
# ---------------------------------------------------------------------------

class TestParseReply:
    def test_extracts_all_three_tags(self):
        text, emotion, action, effect = pc.parse_reply('【情绪：开心】你好呀【动作：跳】【特效：星星】')
        assert text == '你好呀'
        assert emotion == 'happy'
        assert action == '跳'
        assert effect == '星星'

    def test_defaults_when_no_tags(self):
        text, emotion, action, effect = pc.parse_reply('就一句普通的话')
        assert text == '就一句普通的话'
        assert emotion == pc.DEFAULT_EMOTION
        assert action == pc.DEFAULT_ACTION
        assert effect == pc.DEFAULT_EFFECT

    def test_empty_content_falls_back_to_ellipsis(self):
        # 全是标记、正文为空时必须回退，否则会出现空气泡
        text, _, _, _ = pc.parse_reply('【情绪：开心】【动作：跳】')
        assert text == pc.EMPTY_LINE_FALLBACK

    def test_none_content_does_not_crash(self):
        text, emotion, _, _ = pc.parse_reply(None)
        assert text == pc.EMPTY_LINE_FALLBACK
        assert emotion == pc.DEFAULT_EMOTION

    @pytest.mark.parametrize(
        ('cn', 'en'),
        [('开心', 'happy'), ('生气', 'angry'), ('难过', 'sad'),
         ('惊讶', 'surprised'), ('傲娇', 'tsundere'), ('平静', 'calm')],
    )
    def test_emotion_map_covers_all_six(self, cn, en):
        _, emotion, _, _ = pc.parse_reply(f'【情绪：{cn}】台词')
        assert emotion == en

    def test_unknown_emotion_falls_back_to_happy(self):
        _, emotion, _, _ = pc.parse_reply('【情绪：摸鱼】台词')
        assert emotion == 'happy'

    def test_accepts_halfwidth_colon(self):
        # 模型有时输出半角冒号
        text, emotion, _, _ = pc.parse_reply('【情绪:难过】呜呜')
        assert text == '呜呜'
        assert emotion == 'sad'

    def test_strips_bare_prefix_lines(self):
        text, _, _, _ = pc.parse_reply('情绪：开心\n动作：跳\n真正的台词在这里')
        assert text == '真正的台词在这里'

    def test_whitespace_only_after_stripping_falls_back(self):
        text, _, _, _ = pc.parse_reply('   【情绪：开心】   ')
        assert text == pc.EMPTY_LINE_FALLBACK


# ---------------------------------------------------------------------------
# 数值逻辑
# ---------------------------------------------------------------------------

class TestExpCurve:
    def test_exp_needed_scales_with_level(self):
        assert pc.exp_needed(1) == 100
        assert pc.exp_needed(5) == 500
        assert pc.exp_needed(19) == 1900

    def test_max_level_needs_no_exp(self):
        assert pc.exp_needed(pc.MAX_LEVEL) == 0
        assert pc.exp_needed(pc.MAX_LEVEL + 5) == 0


class TestAffectionTier:
    @pytest.mark.parametrize(
        ('affection', 'name', 'idx'),
        [(0, '疏离', 1), (19, '疏离', 1), (20, '熟悉', 2), (49, '熟悉', 2),
         (50, '亲近', 3), (79, '亲近', 3), (80, '心动', 4), (99, '心动', 4),
         (100, '倾心', 5)],
    )
    def test_boundaries(self, affection, name, idx):
        assert pc.get_affection_tier(affection) == (name, idx)

    def test_over_max_still_caps_at_top_tier(self):
        assert pc.get_affection_tier(999) == ('倾心', 5)


# ---------------------------------------------------------------------------
# 成长
# ---------------------------------------------------------------------------

class TestGrowthManager:
    def test_starts_with_defaults(self, tmp_path):
        g = pc.GrowthManager(str(tmp_path / 's.json'))
        assert (g.level, g.exp, g.food) == (1, 0, 5)

    def test_feed_consumes_food_and_adds_exp(self, tmp_path):
        g = pc.GrowthManager(str(tmp_path / 's.json'))
        ok, new_level = g.feed()
        assert ok is True
        assert g.food == 4
        assert g.exp == pc.EXP_PER_FEED
        assert new_level == 0

    def test_feed_levels_up_and_carries_remainder(self, tmp_path):
        g = pc.GrowthManager(str(tmp_path / 's.json'))
        g.food = 100
        g.exp = 95
        ok, new_level = g.feed()
        assert ok and new_level == 2
        # Lv1 需要 100 经验：95+10=105 → 扣 100 升到 2 级，余 5
        assert (g.level, g.exp) == (2, 5)

    def test_cannot_feed_without_food(self, tmp_path):
        g = pc.GrowthManager(str(tmp_path / 's.json'))
        g.food = 0
        assert g.feed() == (False, 0)
        assert g.food == 0

    def test_cannot_feed_at_max_level(self, tmp_path):
        g = pc.GrowthManager(str(tmp_path / 's.json'))
        g.level = pc.MAX_LEVEL
        g.food = 10
        assert g.feed() == (False, 0)

    def test_multi_level_up_in_one_feed(self, tmp_path):
        g = pc.GrowthManager(str(tmp_path / 's.json'))
        g.food = 10
        g.exp = 100 + 200  # 足够连升到 3 级
        ok, new_level = g.feed()
        assert ok and new_level == 3
        assert g.level == 3

    def test_offline_food_accumulates(self, tmp_path):
        g = pc.GrowthManager(str(tmp_path / 's.json'))
        g.food = 0
        start = 1000.0
        g.last_food_time = start
        gained = g._offline_food(now=start + pc.FOOD_INTERVAL_SEC * 3 + 30)
        assert gained == 3
        assert g.food == 3
        # 零头必须保留：多出的 30 秒不能被吞掉
        assert g.last_food_time == start + pc.FOOD_INTERVAL_SEC * 3

    def test_offline_food_caps_at_max(self, tmp_path):
        g = pc.GrowthManager(str(tmp_path / 's.json'))
        g.food = 0
        start = 1000.0
        g.last_food_time = start
        g._offline_food(now=start + pc.FOOD_INTERVAL_SEC * 100)
        assert g.food == pc.MAX_FOOD

    def test_tick_food_skips_before_interval(self, tmp_path):
        g = pc.GrowthManager(str(tmp_path / 's.json'))
        g.food = 0
        start = 1000.0
        g.last_food_time = start
        assert g.tick_food(now=start + 10) is False
        assert g.food == 0

    def test_tick_food_fires_after_interval(self, tmp_path):
        g = pc.GrowthManager(str(tmp_path / 's.json'))
        g.food = 0
        start = 1000.0
        g.last_food_time = start
        assert g.tick_food(now=start + pc.FOOD_INTERVAL_SEC) is True
        assert g.food == 1

    def test_exp_needed_method_matches_module_function(self, tmp_path):
        g = pc.GrowthManager(str(tmp_path / 's.json'))
        g.level = 7
        assert g.exp_needed() == pc.exp_needed(7)


# ---------------------------------------------------------------------------
# 好感度
# ---------------------------------------------------------------------------

class TestAffectionManager:
    def test_starts_at_zero(self, tmp_path):
        a = pc.AffectionManager(str(tmp_path / 's.json'))
        assert a.affection == 0
        assert a.tier == ('疏离', 1)

    def test_feed_adds_two(self, tmp_path):
        a = pc.AffectionManager(str(tmp_path / 's.json'))
        assert a.on_feed() is True
        assert a.affection == pc.AFFECTION_PER_FEED

    def test_interact_adds_one(self, tmp_path):
        a = pc.AffectionManager(str(tmp_path / 's.json'))
        assert a.on_interact() is True
        assert a.affection == 1

    def test_daily_feed_cap(self, tmp_path):
        a = pc.AffectionManager(str(tmp_path / 's.json'))
        for _ in range(pc.AFFECTION_DAILY_FEED_CAP):
            assert a.on_feed() is True
        assert a.on_feed() is False
        assert a.affection == pc.AFFECTION_DAILY_FEED_CAP * pc.AFFECTION_PER_FEED

    def test_daily_interact_cap(self, tmp_path):
        a = pc.AffectionManager(str(tmp_path / 's.json'))
        for _ in range(pc.AFFECTION_DAILY_INTERACT_CAP):
            a.on_interact()
        assert a.on_interact() is False

    def test_affection_never_exceeds_max(self, tmp_path):
        a = pc.AffectionManager(str(tmp_path / 's.json'))
        a.affection = pc.MAX_AFFECTION
        a.on_feed()
        a.on_interact()
        assert a.affection == pc.MAX_AFFECTION

    def test_online_tick_grants_after_ten_minutes(self, tmp_path):
        a = pc.AffectionManager(str(tmp_path / 's.json'))
        for _ in range(pc.AFFECTION_ONLINE_TICK_MIN - 1):
            assert a.on_online() is False
        assert a.affection == 0
        assert a.on_online() is True
        assert a.affection == 1

    def test_new_day_resets_daily_caps(self, tmp_path):
        # 注入可控时钟：先停在 09-15，跑满每日上限，再把时钟拨到 09-16
        day = {'v': '2026-09-15'}
        a = pc.AffectionManager(str(tmp_path / 's.json'), clock=lambda: day['v'])
        for _ in range(pc.AFFECTION_DAILY_FEED_CAP):
            a.on_feed()
        assert a.on_feed() is False
        assert a._roll_date() is False  # 同一天，不重置

        # 跨天：计数清零，可以继续加好感
        day['v'] = '2026-09-16'
        assert a._roll_date() is True
        assert a.on_feed() is True

    def test_day_rolls_over_on_any_action(self, tmp_path):
        """跨天重置不能只在显式调用 _roll_date 时发生。"""
        day = {'v': '2026-09-15'}
        a = pc.AffectionManager(str(tmp_path / 's.json'), clock=lambda: day['v'])
        for _ in range(pc.AFFECTION_DAILY_INTERACT_CAP):
            a.on_interact()
        assert a.on_interact() is False
        day['v'] = '2026-09-16'
        assert a.on_interact() is True  # on_interact 内部会先 _roll_date

    def test_stale_date_in_save_resets_counters_on_load(self, tmp_path):
        """存档里是昨天，重启后每日计数必须清零。"""
        save = tmp_path / 's.json'
        save.write_text(json.dumps({
            'affection': 30, 'date': '2026-09-15',
            'feed_count': 15, 'interact_count': 20,
        }), encoding='utf-8')
        a = pc.AffectionManager(str(save), clock=lambda: '2026-09-16')
        assert a.affection == 30          # 好感度本身保留
        assert a._feed_count == 0         # 但每日计数清零
        assert a._interact_count == 0
        assert a.on_feed() is True

    def test_confess_requires_both_conditions(self, tmp_path):
        a = pc.AffectionManager(str(tmp_path / 's.json'))
        assert a.can_confess(pc.MAX_LEVEL) is False
        a.affection = pc.MAX_AFFECTION
        assert a.can_confess(pc.MAX_LEVEL) is True
        assert a.can_confess(pc.MAX_LEVEL - 1) is False


# ---------------------------------------------------------------------------
# 存档：这是最关键的一组 —— 锁住「喂食抹掉好感度」的回归
# ---------------------------------------------------------------------------

class TestSaveFile:
    def test_missing_file_yields_empty_dict(self, tmp_path):
        assert pc.load_save(str(tmp_path / 'nope.json')) == {}

    def test_corrupt_file_does_not_raise(self, tmp_path):
        p = tmp_path / 'bad.json'
        p.write_text('{ 这不是 json', encoding='utf-8')
        assert pc.load_save(str(p)) == {}

    def test_merge_preserves_other_keys(self, tmp_path):
        p = tmp_path / 's.json'
        p.write_text(json.dumps({'a': 1, 'b': 2}), encoding='utf-8')
        pc.merge_save(str(p), {'b': 99, 'c': 3})
        assert json.loads(p.read_text(encoding='utf-8')) == {'a': 1, 'b': 99, 'c': 3}

    def test_merge_creates_parent_directory(self, tmp_path):
        p = tmp_path / 'nested' / 'deep' / 's.json'
        pc.merge_save(str(p), {'x': 1})
        assert json.loads(p.read_text(encoding='utf-8')) == {'x': 1}

    def test_feeding_must_not_wipe_affection(self, tmp_path):
        """回归测试：原实现 GrowthManager.save() 全量覆盖存档，
        把 AffectionManager 的字段一起抹掉 —— 表现为「喂一次食，好感度清零」。
        两个管理器共用同一个存档文件，任何写入都必须是 read-modify-write。
        """
        save = tmp_path / 's.json'
        grow = pc.GrowthManager(str(save))
        aff = pc.AffectionManager(str(save))

        aff.on_feed()
        aff.on_interact()
        aff.on_interact()
        assert aff.affection == pc.AFFECTION_PER_FEED + 2 * pc.AFFECTION_PER_INTERACT

        grow.feed()  # 这一次写入曾经会抹掉上面全部好感度

        after = json.loads(save.read_text(encoding='utf-8'))
        assert after.get('affection') == aff.affection, '喂食后好感度被抹掉了'
        assert after.get('feed_count') == 1
        assert after.get('interact_count') == 2

    def test_affection_write_does_not_wipe_growth(self, tmp_path):
        """反方向也要成立：加好感不能把等级/经验清零。"""
        save = tmp_path / 's.json'
        grow = pc.GrowthManager(str(save))
        aff = pc.AffectionManager(str(save))

        grow.food = 10
        grow.feed()
        grow.feed()
        assert (grow.level, grow.exp) == (1, 2 * pc.EXP_PER_FEED)

        aff.on_interact()

        after = json.loads(save.read_text(encoding='utf-8'))
        assert after.get('level') == 1
        assert after.get('exp') == 2 * pc.EXP_PER_FEED

    def test_survives_reload(self, tmp_path):
        save = tmp_path / 's.json'
        grow = pc.GrowthManager(str(save))
        grow.food = 10
        grow.feed()
        aff = pc.AffectionManager(str(save))
        aff.on_feed()

        # 重新构造（模拟重启桌宠）
        grow2 = pc.GrowthManager(str(save))
        aff2 = pc.AffectionManager(str(save))
        assert grow2.exp == pc.EXP_PER_FEED
        assert aff2.affection == pc.AFFECTION_PER_FEED

    def test_no_leftover_tmp_file(self, tmp_path):
        """原子写必须清理临时文件。"""
        save = tmp_path / 's.json'
        pc.merge_save(str(save), {'a': 1})
        assert not (tmp_path / 's.json.tmp').exists()
