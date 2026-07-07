"""软字幕剥离(处理骨架第 0 步)自测。

说明:按项目约定,自建数据仅允许用于本项(软字幕剥离)测试;
去除效果评测一律使用开源基准,见路线文档。

用法: .venv/bin/python tests/test_probe_softsub.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from subtitle_eraser import probe
from subtitle_eraser.ffmpeg_tools import ffmpeg_bin, probe_json, run

SRT = """1
00:00:00,500 --> 00:00:02,000
测试字幕 first cue

2
00:00:02,200 --> 00:00:03,800
second cue 中英混排
"""


def make_fixture(tmp: Path, with_sub: bool) -> Path:
    """生成 4 秒彩条测试视频(640x360@25fps + 正弦音轨),可选内嵌 mov_text 软字幕。"""
    out = tmp / ("with_sub.mp4" if with_sub else "no_sub.mp4")
    cmd = [ffmpeg_bin(), "-y",
           "-f", "lavfi", "-i", "testsrc2=duration=4:size=640x360:rate=25",
           "-f", "lavfi", "-i", "sine=frequency=440:duration=4"]
    if with_sub:
        srt = tmp / "subs.srt"
        srt.write_text(SRT, encoding="utf-8")
        cmd += ["-i", str(srt), "-map", "0:v", "-map", "1:a", "-map", "2:s",
                "-c:s", "mov_text"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
            "-c:a", "aac", str(out)]
    run(cmd)
    return out


def duration_of(path: Path) -> float:
    return float(probe_json(path).get("format", {}).get("duration", 0))


def main() -> int:
    failures = []

    def check(name: str, cond: bool, detail: str = ""):
        status = "PASS" if cond else "FAIL"
        print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
        if not cond:
            failures.append(name)

    with tempfile.TemporaryDirectory(prefix="softsub_test_") as d:
        tmp = Path(d)
        fx_sub = make_fixture(tmp, with_sub=True)
        fx_plain = make_fixture(tmp, with_sub=False)

        info = probe.analyze(fx_sub)
        check("含软字幕样本:检出 1 条字幕流", len(info.subtitle) == 1, str(info.subtitle))
        check("含软字幕样本:has_soft_subtitles=True", probe.has_soft_subtitles(fx_sub))
        check("无字幕样本:has_soft_subtitles=False", not probe.has_soft_subtitles(fx_plain))

        stripped = tmp / "stripped.mp4"
        probe.strip_soft_subtitles(fx_sub, stripped)
        info2 = probe.analyze(stripped)
        check("剥离后:字幕流为 0", len(info2.subtitle) == 0, str(info2.subtitle))
        check("剥离后:视频流保留", len(info2.video) == 1)
        check("剥离后:音频流保留", len(info2.audio) == 1)
        d0, d1 = duration_of(fx_sub), duration_of(stripped)
        check("剥离后:时长一致(±0.5s)", abs(d0 - d1) < 0.5, f"{d0:.2f}s → {d1:.2f}s")

    if failures:
        print(f"\n{len(failures)} 项失败: {failures}")
        return 1
    print("\n全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
