# subtitle-eraser — 视频硬字幕去除模块

输入带**硬字幕**的视频,输出去除字幕后的视频 + 处理报告 JSON。
中 / 英文,全自动(无需人工圈选),离线批处理。设计:**固定处理骨架 + 可插拔擦除后端**。

## 效果示例(处理前 → 处理后)

![字幕去除效果示例](docs/effect_demo.png)

## 处理流程

![处理管线](docs/pipeline.png)

软字幕检查 → 字幕定位 → 事件聚合 → 掩码 + ROI → 擦除后端 → 羽化回贴 → 合流编码。

## 快速开始

```bash
pip install -r requirements.txt
python -m subtitle_eraser --input in.mp4 --output out.mp4
```

默认 `--detector fixed --region bottom:0.35 --backend flow-copy`。

## 文档

完整步骤、参数、处理报告格式与后端说明见 **[技术手册.md](技术手册.md)**。
