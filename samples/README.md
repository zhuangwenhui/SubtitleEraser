# samples/ — 随附样例(可端到端复现与量化验证)

一段**自行生成、无版权顾虑**的合成样例。无需额外安装任何模型或依赖(仅 `numpy` + `opencv` + 系统 `ffmpeg`),即可端到端复现"去硬字幕"效果并量化验证。

## 文件

| 文件 | 说明 |
|---|---|
| `subbed.mp4` | **输入**:底部烧录了一条中英文硬字幕的视频(6 秒,1280×720) |
| `clean_reference.mp4` | **参考**:同素材未加字幕的干净原片,仅用于量化验证 |
| `before_after.png` | 处理前 / 处理后 / 干净原片 三联对照图 |
| `verify.py` | 量化验证脚本(计算字幕带 PSNR) |

## 一键复现(默认检测器,零额外依赖)

```bash
python -m subtitle_eraser --input samples/subbed.mp4 --output samples/erased.mp4
```

字幕在画面底部,默认 `fixed` 检测器即可定位;运行结束会在旁边生成 `erased.report.json`。
> 需要系统 `ffmpeg`/`ffprobe`(获取方式见 [tools/README.md](../tools/README.md))。

## 量化验证

```bash
python samples/verify.py samples/erased.mp4
```

会打印字幕带 PSNR:**处理前 ≈15 dB → 处理后 ≈37 dB**,越高越接近干净原片,即字幕被抹除、背景被还原:

```
字幕带 PSNR  处理前(含字幕) = 14.89 dB
字幕带 PSNR  处理后        = 36.72 dB
结论:字幕已抹除、背景已还原
```

> README 与技术手册中"效果示例"用的是真实素材(结论一致);此处的合成样例用于让你**在本机一条命令即可复现并核对数值**。
