"""命令行入口(模块契约见 技术手册.md)。"""
from __future__ import annotations

import argparse

from .pipeline import Config, run


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="subtitle-eraser",
        description="视频硬字幕去除(v0.1 骨架):输入视频,输出去字幕视频 + 处理报告 JSON")
    p.add_argument("--input", required=True, help="输入视频路径")
    p.add_argument("--output", required=True, help="输出视频路径")
    p.add_argument("--backend", default="flow-copy",
                   choices=["flow-copy", "opencv-debug"],
                   help="擦除后端:flow-copy=光流时序传播(默认,抑制闪烁);"
                        "opencv-debug=单帧快速基线")
    p.add_argument("--detector", default="fixed", choices=["fixed", "paddle"],
                   help="字幕定位方式:fixed=固定区域;paddle=PP-OCRv5 文本检测")
    p.add_argument("--region", default="bottom:0.35",
                   help="fixed 检测器的区域,格式 bottom:<比例>(默认 bottom:0.35)")
    p.add_argument("--sample-fps", type=float, default=2.0,
                   help="检测采样帧率(默认 2.0)")
    p.add_argument("--chunk", type=int, default=48,
                   help="送入后端的分块帧数(默认 48)")
    p.add_argument("--assume-hard", action="store_true",
                   help="即使检测到软字幕流也继续视觉管线(默认发现软字幕即剥轨返回)")
    p.add_argument("--report", dest="report_path", default=None,
                   help="处理报告 JSON 路径(默认与输出同名 .report.json)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = Config(input=args.input, output=args.output, backend=args.backend,
                 detector=args.detector, region=args.region,
                 sample_fps=args.sample_fps, chunk=args.chunk,
                 assume_hard=args.assume_hard, report_path=args.report_path)
    rep = run(cfg)
    mode = rep.data["mode"]
    n_ev = len(rep.data["events"])
    print(f"[subtitle-eraser] 完成 mode={mode} 字幕事件={n_ev} → {args.output}")
    return 0
