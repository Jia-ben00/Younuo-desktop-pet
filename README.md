# 尤诺团子 · Windows 桌面宠物

[![smoke](https://github.com/Jia-ben00/Younuo-desktop-pet/actions/workflows/smoke.yml/badge.svg)](https://github.com/Jia-ben00/Younuo-desktop-pet/actions/workflows/smoke.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![PyQt5](https://img.shields.io/badge/PyQt5-5.15-green)](https://pypi.org/project/PyQt5/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

基于 PyQt5 的 Windows 桌面宠物：透明无边框窗口常驻桌面，支持拖拽 / 缩放 / 右键菜单 /
等级成长 / 好感度系统 / 39 句语音互动，全部渲染与状态管理都在本地完成。

**完整走过了 V1 → V10 十个版本的迭代**，每一版的取舍与踩坑都保留在
[版本历史](#版本历史) 与 [`玩法说明.md`](玩法说明.md) 里。

---

## 目录

- [快速开始](#快速开始)
- [功能](#功能)
- [架构：为什么把逻辑和 UI 拆开](#架构为什么把逻辑和-ui-拆开)
- [测试](#测试)
- [一个真实的 bug：喂食会清空好感度](#一个真实的-bug喂食会清空好感度)
- [版本历史](#版本历史)
- [技术栈](#技术栈)
- [语音方案对比](#语音方案对比与最终选择)
- [崩溃根因总结](#崩溃根因总结避坑指南)
- [项目结构](#项目结构)
- [素材与版权](#素材与版权)

---

## 快速开始

环境要求：Python 3.9+，Windows（依赖 `winsound` 做语音兜底）。

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行
cd v10/src
python iuno_pet_v10.py
```

跑测试（**不需要 PyQt5、不需要图形环境**）：

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

> EXE 打包素材（v3–v6，共约 228MB）已从仓库移除 —— 构建产物不该进版本库。
> 需要可执行文件请按 [打包](#打包-exe) 一节自行构建。

## 功能

| 模块 | 说明 |
| --- | --- |
| **窗口** | 透明无边框、始终置顶、托盘图标；左键拖拽移动、滚轮缩放（0.4x–3.0x） |
| **右键菜单** | 月夜星空主题，15 个 SVG 图标（V6 起） |
| **情绪系统** | 6 种情绪单帧形象 + `QPainter` 程序驱动形变（呼吸 / 弹跳 / 抖动 / 拉伸 / 侧转） |
| **成长系统** | Lv 1–20；喂月亮糕得经验；月亮糕每 5 分钟产出 1 个，上限 30，支持离线累积 |
| **好感度** | 0–100 分 5 档（疏离 / 熟悉 / 亲近 / 心动 / 倾心）；带每日上限防刷 |
| **语音** | 39 句语音；7 状态 × 5 档好感度联动；`edge-tts` 优先，`winsound` 兜底 |
| **LLM 对话** | OpenAI 兼容接口（默认 DeepSeek）；模型用 `【情绪：开心】` 这类标记返回结构化指令 |
| **持久化** | 成长与好感度存同一个 `yuno_v10_data.json` |

**核心人设**：七丘四方殿谕女，诞生于月食之时，傲娇系少女，嘴硬心软，
口头禅「哼，这种程度……我当然早就预见啦。」

## 架构：为什么把逻辑和 UI 拆开

V10 做了一次结构重构 —— **把纯逻辑从 GUI 主程序里抽出来**：

```
v10/src/
├── pet_core.py        # 纯逻辑：等级曲线 / 好感度 / 台词解析 / 存档读写
│                      #   零 Qt 依赖 → 可在任何环境用 pytest 直接测
├── iuno_pet_v10.py    # GUI 层：窗口、绘制、事件、菜单（import PyQt5）
└── v7_menu.py         # 右键菜单组件
```

原先所有逻辑都写在 `iuno_pet_v10.py` 里，而该模块顶层 `import PyQt5`，
导致**任何逻辑都无法在没有图形环境的机器上测试**（CI 里装 Qt 又慢又需要显示环境）。
拆开后：

- 单元测试不需要 PyQt5、不需要图形环境，CI 里一秒内跑完；
- 数值平衡（升级曲线、好感度上限）可以脱离 GUI 单独验证；
- 存档格式有唯一入口（`merge_save`），损坏风险可控。

主程序通过薄封装复用这套逻辑，行为不变：

```python
class GrowthManager(_GrowthManagerCore):
    """逻辑已抽到 pet_core，这里只负责定位存档路径。"""
    def __init__(self):
        super().__init__(growth_data_path())
```

重构后主程序从 1436 行降到 1310 行，逻辑集中到 `pet_core.py` 的 326 行。

## 测试

```bash
python -m pytest tests/ -v
```

**56 个测试，全部通过**，覆盖四个层面：

| 测试组 | 覆盖内容 |
| --- | --- |
| `TestParseReply` | 台词解析的正则边界：空正文回退、未知情绪兜底、全/半角冒号、标记剥离 |
| `TestExpCurve` / `TestAffectionTier` | 升级曲线、好感度分档边界（19/20、49/50、79/80、99/100） |
| `TestGrowthManager` / `TestAffectionManager` | 喂食/互动/在线计时、每日上限、跨天重置、离线月亮糕累积（含零头保留） |
| `TestSaveFile` | 存档健壮性：文件缺失/损坏不崩、原子写无残留、**跨管理器字段不互相覆盖** |

CI（`.github/workflows/smoke.yml`）在每次 push 时跑两件事：单元测试，以及
V1–V10 全部历史版本的语法检查（防止误改坏历史快照）。

## 一个真实的 bug：喂食会清空好感度

这是开发 V10 时发现的缺陷，也是本项目测试里最关键的一条回归用例。

**现象**：喂一次食，好感度从 42 直接归零。

**原因**：成长系统和好感度系统共用同一个存档文件 `yuno_v10_data.json`，
但两个管理器的写入方式不一致 ——

```python
# 成长：全量覆盖，只写自己的 5 个字段
json.dump({'level': ..., 'exp': ..., 'food': ...}, f)

# 好感度：读-改-写，保留别人的字段
d = json.load(f); d.update({...}); json.dump(d, f)
```

于是每次喂食（触发成长写入）都会把好感度、每日计数一并抹掉。

**修复**：抽出唯一的存档写入口 `merge_save()`，强制所有写入走
read-modify-write，并改用「先写临时文件再 `os.replace`」的原子写避免写坏存档。

**回归测试**（`tests/test_pet_core.py::test_feeding_must_not_wipe_affection`）：
先加满好感度、再喂食，断言好感度字段依然存在。这条测试在修复前的实现上会失败 ——
它与另一条反方向的用例（`test_affection_write_does_not_wipe_growth`）共同锁住这个不变量。

## 版本历史

十次迭代，每次解决一个具体问题：

| 版本 | 主题 | 关键变化 |
| --- | --- | --- |
| **V1** | 基础桌宠 | 透明置顶窗口 + 图片显示 + 拖拽 |
| **V2** | 人设 + 语音 | 人设卡、语音触发、`winsound` 播放 |
| **V3** | 2.5D 渲染 | 尝试透视形变 |
| **V4** | Bongo Cat 方向 | 交互反馈探索 |
| **V5** | 自绘团子界面 | 放弃截图表情包，改 `QPainter` 自绘 + peeking 动画 |
| **V6** | 月夜星空菜单 | 15 个 SVG 图标菜单；`QSvgRenderer` 渲染 |
| **V7** | 稳定性优化 | 全 `QThread` 异步；菜单拆成独立模块 |
| **V8** | 形象扩展 | 贴纸素材扩充 |
| **V9** | 随机形象池 | 随机切换 + 测试模式 |
| **V10** | **成长系统 + 逻辑分层** | 等级 / 好感度 / 存档原子写；**逻辑抽到 `pet_core.py` 并补测试** |

各版本的详细动机见 `v*/docs/` 目录（V2/V3 保留了人设卡与动态协议设计文档）。

**7 种状态 × 5 档好感度**：同一状态在不同好感度下会挑选不同台词，
因此同样「戳一下」，疏离期和倾心期的回应完全不同。

## 技术栈

- **GUI**：PyQt5 5.15（`QWidget` 无边框窗口 + `QPainter` 自绘）
- **多媒体**：`QSoundEffect`（低延迟音效）、`winsound`（兜底）
- **异步**：`QThread` 承载 LLM 请求与 TTS 合成，避免阻塞 UI
- **TTS**：`edge-tts` 优先，失败回退 Windows SAPI
- **LLM**：OpenAI 兼容接口，通过结构化标记解析情绪/动作/特效
- **测试**：pytest（仅覆盖纯逻辑层，不依赖 GUI）

## 语音方案对比与最终选择

试过三种方案，最终选择 **`winsound` 为主、`QSoundEffect` 备选（V5 参考）**：

| 方案 | 优点 | 问题 |
| --- | --- | --- |
| `QSoundEffect` | 延迟低、支持音量控制 | 在 Windows 上偶发不播放；对象被 GC 后中断 |
| `winsound.PlaySound` | 系统原生、稳定 | 无法调音量；`SND_ASYNC` 下无法精确控制停止 |
| `edge-tts` 实时合成 | 音质好 | 需要联网，首次延迟高 |

**最终策略**：`edge-tts` 生成后缓存为 WAV，播放走 `winsound`（`SND_ASYNC |
SND_FILENAME`），保证「触发新语音自动打断上一条」；音量控制交给系统混音。

```python
winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)  # 异步播放
winsound.PlaySound(None, winsound.SND_PURGE)                          # 立即停止
```

## 崩溃根因总结（避坑指南）

迭代中踩过的坑，留档备查：

1. **`QSoundEffect` 对象被 GC 回收** → 声音播放到一半中断。
   必须持有引用（存到 `self`），不能只放在局部变量里。
2. **在 `QThread` 里直接操作 UI** → 随机崩溃。
   跨线程只能通过信号槽传递。
3. **`QPainter` 在 `paintEvent` 外使用** → 绘制错乱。
   所有自定义绘制都收敛到 `paintEvent` 内。
4. **资源路径硬编码** → 打包成 EXE 后找不到素材。
   统一走 `resource_path()`，兼容 PyInstaller 的 `sys._MEIPASS`。
5. **存档写入非原子** → 进程被杀时存档损坏，下次启动丢全部进度。
   改为临时文件 + `os.replace`。

## 项目结构

```
.
├── v10/                      # 最新版本（推荐从这里读代码）
│   ├── src/
│   │   ├── pet_core.py       # 纯逻辑（无 Qt 依赖，有测试覆盖）
│   │   ├── iuno_pet_v10.py   # GUI 主程序
│   │   └── v7_menu.py        # 右键菜单
│   └── assets/               # 形象 / 语音 / 图标 / 动画
├── tests/
│   └── test_pet_core.py      # 56 个单元测试
├── .github/workflows/
│   └── smoke.yml             # CI：单元测试 + 历史版本语法检查
├── v1/ … v9/                 # 历史版本快照（仅供对照，不再维护）
├── requirements.txt          # 运行时依赖
├── requirements-dev.txt      # 开发依赖
└── 玩法说明.md                # 玩法与人设说明
```

### 打包 EXE

```bash
pip install pyinstaller
cd v10/src
pyinstaller --noconfirm --clean --windowed \
  --add-data "../assets;assets" \
  --name "尤诺桌宠v10" iuno_pet_v10.py
```

构建产物落在 `dist/`（已在 `.gitignore` 中忽略）。

## 素材与版权

- 角色「尤诺」版权归**库洛游戏**所有，本项目为个人学习作品。
- 语音素材由 AI 生成（Seed Audio 1.0），仅供学习交流。
- **不可商用。**

本仓库的 MIT 许可证（见 [LICENSE](LICENSE)）仅覆盖自行编写的源代码，
不包含角色形象与语音素材。

## 致谢

- 《鸣潮》库洛游戏 —— 尤诺角色
- Seed Audio 1.0 —— 语音生成
- PyQt5 —— GUI 框架
