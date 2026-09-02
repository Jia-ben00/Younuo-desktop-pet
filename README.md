# 鸣潮 · 尤诺团子 桌面宠物（Iuno Dango Desktop Pet）

《鸣潮》尤诺（玩家常称「尤洛」）团子的 Windows 桌面宠物。

- **v1**：透明无边框置顶桌宠 —— 拖动 / 跟随鼠标 / 滚轮缩放 / 键盘跳跃 / 右键菜单
- **v2**：加入人设（角色卡）、动态协议（情绪 × 动作 × 特效状态机）、语音模块（AI TTS 风格参考，非真人克隆），附 Open-LLM-VTuber 适配配置

> 角色与素材版权归《鸣潮》/ 库洛游戏及相关原画作者所有，仓库默认私有，仅供个人学习交流，请勿商用或公开传播角色素材。

## 目录

```
├── README.md
├── .gitignore
├── v1/                      # 第一版：静态透明桌宠
│   ├── src/iuno_pet.py
│   ├── assets/              # 透明底角色图、图标、原始素材
│   └── docs/使用说明.md
└── v2/                      # 第二版：人设 + 动态协议 + 语音
    ├── src/iuno_pet_v2.py
    ├── assets/
    │   ├── iuno_pet.png     # 透明底角色图
    │   └── voice/           # 5 条尤诺风格语气词 WAV
    └── docs/                # 人设卡 / 动态协议 / Open-LLM-VTuber YAML / 使用说明
```

## 快速开始

```bash
# 成品 EXE（未入库，见 releases 或自行打包）
dist/尤诺桌宠.exe       # v1
dist/尤诺桌宠v2.exe     # v2

# 源码运行（需 PyQt5）
python v1/src/iuno_pet.py
python v2/src/iuno_pet_v2.py
```

## v2 亮点

- **人设**：傲娇·月相谕女团子化（`v2/docs/人设卡.md`）
- **动态协议**：平静/开心/生气/难过/惊讶/傲娇 六态状态机，特效含脸红、冒烟、月亮符文、眼泪、比心、耳朵、尾巴；参数命名对齐 Live2D Cubism（`v2/docs/动态协议.md`）
- **语音模块**：单击/双击/拖拽/喂食/晚安/键盘 触发语气词，AI TTS 风格参考生成（非真人克隆）；说话口型跟随音频电平；长文本自动跳过语音
- **Open-LLM-VTuber 适配**：`v2/docs/character_config.yaml` 可直接粘贴

## 打包

各版本 docs 或源码头部注释。注意：PyInstaller 对中文路径与 conda Python 有坑，
建议英文路径 + 独立 venv + pip 版 PyQt5 构建。
