# 尤诺团子桌面宠物 · 开发全记录

> 《鸣潮》角色尤诺（团子形态）Windows 桌面宠物程序
> 从 V1 到 V10，历经 10 个版本迭代，完整记录开发过程与踩坑经验

---

## 项目简介

尤诺团子是一个基于 PyQt5 的 Windows 桌面宠物程序，以《鸣潮》角色「尤诺」的 Q 版团子形象常驻桌面。支持鼠标拖拽、滚轮缩放、右键菜单、等级成长、好感度系统、39 句尤诺声线语音等功能。

**核心人设**：七丘四方殿谕女，诞生于月食之时，傲娇系少女，嘴硬心软，口头禅「哼，这种程度……我当然早就预见啦。」

---

## 功能特性

### 基础功能
- 透明无边框窗口，始终置顶
- 左键拖拽移动位置
- 滚轮调整大小
- 右键菜单（月夜星空主题）
- 托盘图标

### 成长系统（V10 新增）
- **等级系统**：Lv 1-20，喂食月亮糕获得经验
- **月亮糕**：每 5 分钟产出 1 个，上限 30 个，离线累积
- **好感度系统**：0-100，分 5 档（疏离/熟悉/亲近/心动/倾心）
- **告白解锁**：Lv20 + 好感 100 双条件触发
- 数据持久化：`yuno_v10_data.json`

### 语音系统
- 39 句尤诺声线语音（傲娇系少女音）
- 7 状态 × 5 档好感度 = 35 句互动台词
- 升级语音 + 告白语音 3 句
- 语音开关控制
- 触发新语音自动打断上一条

### 形象系统
- 6 张 design assets 静态形象
- peeking 偷看动画
- 每 10 秒随机切换形象
- 7 种情绪状态对应不同形象

---

## 版本历史

### V1 · 基础桌宠
- 透明窗口、无边框、始终置顶
- 左键拖拽、滚轮缩放
- 右键菜单：调整大小、置顶开关、退出
- 鼠标/键盘动作同步

### V2 · 人设 + 语音
- 加入尤诺人设和六情绪系统
- AI TTS 实时语音（方案 A：音色描述生成）
- 动态协议 → Live2D 参数映射
- 语气词库：摸头/戳脸/拖拽/喂食/晚安

### V3 · 2.5D 渲染
- 尝试 2.5D 模型渲染
- 三视图 + 3D 动态建模
- 稳定性问题：容易卡退

### V4 · Bongo Cat 方向
- 切换到 Bongo Cat 架构
- 从 GitHub 获取尤诺表情包
- 接入 LLM API + TTS 实时语音
- 按【情绪/动作】标签驱动动画

### V5 · 自绘团子界面
- 自绘团子主界面
- 语气词重制（"呀"→"哇塞"，加长增加灵动感）
- 鼠标跟随功能
- 部位点击（头/脸/身体）
- 使用说明界面

### V6 · 月夜星空主题菜单
- 深蓝紫渐变背景 + 金色星光
- 毛玻璃圆角面板
- 金色月华渐变胶囊主按钮
- 满月/月牙造型开关
- 三区分组：互动区/外观区/系统区

### V7 · 稳定性优化
- 菜单实例复用（不每次新建）
- 30 秒稳定性测试：0 崩溃
- 30 次菜单打开关闭测试：0 崩溃
- 修复 QProgressBar 未导入导致的崩溃

### V8 · 形象扩展
- 从互联网搜索 4 张 Q 版形象
- 删除 tsundere 表情
- 互动区增加翘腿动作
- 菜单左上角添加尤诺团子形象

### V9 · 随机形象池
- 主桌宠用 design assets 6 张 + peeking 动画
- 每 10 秒随机切换形象
- 测试按钮依次显示 7 张图
- 稳定版基准：桌宠 200×230，菜单宽度 260，内存 8.4MB

### V10 · 成长系统 + 语音修复
- 基于 V9 稳定架构重新实现
- GrowthManager：等级/经验/月亮糕
- AffectionManager：好感度 5 档
- 39 句尤诺声线语音
- 语音方案最终确定为 winsound
- 菜单去掉"跟我说话"，添加成长区
- 互动区改为喂食/玩耍/戳脸

---

## 技术栈

| 组件 | 技术 |
|------|------|
| GUI 框架 | PyQt5 5.15.11 |
| 打包工具 | PyInstaller 6.22.2 |
| 语音播放 | winsound（Python 标准库） |
| 语音生成 | Seed Audio 1.0（TTS） |
| 图像处理 | PIL / 自绘 |
| 数据存储 | JSON |
| 构建环境 | Python 3.x + venv |

---

## 语音方案对比与最终选择

### 方案对比

| 方案 | 优点 | 缺点 | 结果 |
|------|------|------|------|
| QSoundEffect | Qt 原生，API 简单 | V10 的 WAV（40000Hz/16位/立体声）导致堆崩溃 0xC0000374 | ❌ 崩溃 |
| QMediaPlayer | 支持格式多 | 打包后没声音 | ❌ 无声 |
| ctypes + winmm | 底层控制 | PyInstaller 打包后启动崩溃（_ctypes DLL 加载失败） | ❌ 启动崩溃 |
| **winsound** | Python 标准库，零依赖，Windows 原生 | 仅支持 WAV，功能简单 | ✅ **最终选择** |

### 关键发现
- V5 使用 QSoundEffect 能正常工作，是因为 V5 的 WAV 格式不同
- V10 的 WAV 是 40000Hz/16 位/立体声，QSoundEffect 不兼容
- winsound 直接调用 Windows PlaySound API，最稳定

### winsound 用法
```python
import winsound
# 播放（异步）
winsound.PlaySound(file_path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
# 停止
winsound.PlaySound(None, winsound.SND_PURGE)
```

---

## 崩溃根因总结（避坑指南）

以下是开发过程中遇到的所有崩溃根因，**必须继续避免**：

| 根因 | 现象 | 解决方案 |
|------|------|----------|
| QSoundEffect 播放 WAV | 随机崩溃（堆损坏 0xC0000374） | 改用 winsound |
| ctypes 导入 | PyInstaller 打包后启动崩溃 | 禁用 ctypes |
| QMediaPlayer | 不崩溃但没声音 | 改用 winsound |
| SmoothPixmapTransform | 绘制时崩溃 | 使用 FastTransformation |
| p.rotate() | 随机 0xC0000409 崩溃 | 避免旋转绘制 |
| QRadialGradient 阴影 | 绘制时崩溃 | 避免径向渐变 |
| QPointF/QRectF 浮点绘制 | 崩溃 | 使用整数类型 |
| QProgressBar 未导入 | 菜单打开即崩溃 | 确保导入所有使用的组件 |
| 菜单每次新建 | 30 次测试后内存泄漏 | 菜单实例复用 |

---

## 项目结构

```
桌宠/
├── v10/                    # V10 最新版本
│   ├── src/
│   │   ├── iuno_pet_v10.py    # 主程序
│   │   └── v7_menu.py         # 菜单
│   ├── assets/
│   │   ├── stickers/          # 形象图片
│   │   ├── voice_v10/         # 39 个 WAV 语音
│   │   ├── icons/             # 图标
│   │   └── animations/        # 动画
│   └── test_*.py              # 测试脚本
├── v9/                     # V9 稳定版（参考基准）
├── v5/                     # V5（QSoundEffect 参考）
├── bongo-cat/              # Bongo Cat 分支（PySide6）
├── dist/
│   ├── 尤诺桌宠v10.exe         # V10 可执行文件
│   ├── 尤诺桌宠v9.exe          # V9 可执行文件
│   └── voice_v10/             # 语音文件（必须与 EXE 同目录）
├── design assets/          # 设计素材
└── 玩法说明.md              # 玩法说明
```

---

## 安装与使用

### 直接运行
1. 下载 `dist/尤诺桌宠v10.exe`
2. 确保 `voice_v10/` 文件夹与 EXE 在同一目录
3. 双击 EXE 运行

### 从源码运行
```bash
# 创建虚拟环境
python -m venv venv
venv\Scripts\activate

# 安装依赖
pip install PyQt5==5.15.11

# 运行
cd v10/src
python iuno_pet_v10.py
```

### 打包 EXE
```bash
# 使用 spec 文件打包
cd C:\Users\bing\iuno_build_v7
pyinstaller iuno_v7.spec --noconfirm --clean

# 复制到 dist
copy dist\尤诺桌宠v10.exe C:\Users\bing\Desktop\桌宠\dist\
```

---

## 互动说明

| 操作 | 效果 |
|------|------|
| 左键单击 | 戳脸互动（呆萌语音） |
| 左键拖拽 | 移动 + 害羞语音 |
| 右键单击 | 打开菜单 |
| 滚轮 | 调整大小 |
| 菜单→喂食 | 消耗月亮糕 +10 经验 |
| 菜单→玩耍 | 开心状态 + 语音 |
| 菜单→戳脸 | 呆萌状态 + 语音 |

---

## 7 种状态 × 5 档好感度

| 状态 | 形象 | 语音文件 |
|------|------|----------|
| 翘腿 | design_1 | qiaotui_1~5.wav |
| 害羞 | design_2 | haixiu_1~5.wav |
| 撒娇 | design_3 | sajiao_1~5.wav |
| 开心 | design_happy | kaixin_1~5.wav |
| 伤心 | design_sad | shangxin_1~5.wav |
| 呆萌 | design_surprised | daimeng_1~5.wav |
| 偷看 | peeking 动画 | toukan_1~5.wav |
| 升级 | - | levelup.wav |
| 告白 | - | gaobai_1~3.wav |

好感度档位：疏离(1) / 熟悉(2) / 亲近(3) / 心动(4) / 倾心(5)

---

## 开发心得

1. **稳定性优先**：V3/V4 追求炫技导致频繁崩溃，V7 后专注稳定性，30 秒 0 崩溃
2. **语音方案选择**：不要迷信 Qt 多媒体，winsound 虽然简单但最稳定
3. **菜单复用**：每次新建菜单会导致内存泄漏和崩溃，实例复用是关键
4. **导入检查**：所有使用的 Qt 组件必须显式导入，否则打包后崩溃
5. **避免浮点绘制**：PyQt5 在某些系统上浮点类型绘制会崩溃
6. **数据持久化**：成长数据用 JSON 存储，简单可靠
7. **版本管理**：每个版本独立文件夹，便于回退和对比

---

## 许可证

本项目仅供学习交流使用。尤诺角色版权归库洛游戏所有，语音为 AI 生成，不可商用。

---

## 致谢

- 《鸣潮》库洛游戏 - 尤诺角色
- Seed Audio 1.0 - 语音生成
- PyQt5 - GUI 框架
