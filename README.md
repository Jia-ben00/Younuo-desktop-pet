# 鸣潮 · 尤诺团子 桌面宠物（Iuno Dango Desktop Pet）

《鸣潮》尤诺（玩家常称「尤洛」）团子的 Windows 桌面宠物。

- **v1**：透明无边框置顶桌宠 —— 拖动 / 跟随鼠标 / 滚轮缩放 / 键盘跳跃 / 右键菜单
- **v2**：加入人设、动态协议（情绪 × 动作 × 特效）、语音模块（AI TTS 风格参考，非真人克隆）

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
    ├── assets/              # 精灵图 + 语气词语音
    └── docs/                # 人设卡 / 动态协议 / Open-LLM-VTuber YAML
```

## 快速开始

```bash
# v1
dist/尤诺桌宠.exe   # 或运行: python v1/src/iuno_pet.py

# v2
python v2/src/iuno_pet_v2.py
```

## 打包

见各版本 docs 或源码头部注释（注意：PyInstaller 对中文路径与 conda Python 有坑，建议英文路径 + venv + pip 版 PyQt5）。
