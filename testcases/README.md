# testcases/ — 测试用例目录(素材另行分发)

README 效果图所用的**真实素材测试用例**不随代码仓库分发,会以压缩包形式另行提供。
收到压缩包后,解压并把其中的 `testcases/` 文件夹放到**本仓库根目录**(即本目录),得到:

```
testcases/
  case01.mp4 ... case04.mp4     四段带硬字幕的测试片段(各约 8 秒)
  清单.txt                       文件说明与 md5 校验值
```

`case01 ~ case04` 依次对应 README 效果图中的第 1 ~ 4 行。

## 运行

```bash
# 先安装依赖(含 PP-OCRv5 检测,见仓库 README 的"快速开始")
pip install -r requirements.txt
pip install paddlepaddle paddleocr

python -m subtitle_eraser --input testcases/case01.mp4 --output out/case01.mp4 --detector paddle
```

对 case02 ~ case04 同理。输出与效果图对应行的"处理后"一致,可直接目检核对;
每次运行还会在输出旁生成 `.report.json`(字幕事件时间轴、各阶段耗时)。

> 本目录内除本说明外的一切文件均不入 git(见 `.gitignore`),放心放置素材与输出。
> 想在拿到素材前先跑通流程,可用仓库自带的合成样例 [samples/](../samples/)。
