"""处理骨架编排:软字幕检查 → 字幕定位 → 事件聚合 → 后端擦除(ROI)→ 羽化回贴 → 合流。

内存策略:两遍读取。第一遍稀疏采样做检测;第二遍流式处理,
帧只在被字幕事件覆盖时进入事件缓冲(按 chunk 分块送后端),
写出闸门保证输出帧序,内存占用与 chunk 大小同阶。
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path

import cv2
import numpy as np

from . import probe
from .backends import get_backend
from .detect import make_detector
from .events import (aggregate, build_mask, expand_bbox, feather_paste,
                     stroke_mask_in_box)
from .ffmpeg_tools import ffmpeg_bin, run as ffrun
from .mux import FrameSink
from .report import Report


@dataclass
class Config:
    input: str
    output: str
    backend: str = "opencv-debug"
    detector: str = "fixed"
    region: str = "bottom:0.35"
    sample_fps: float = 2.0
    chunk: int = 48
    assume_hard: bool = False   # True: 即使存在软字幕也继续视觉管线
    report_path: str | None = None


def run(cfg: Config) -> Report:
    rep = Report(asdict(cfg))
    rep_path = cfg.report_path or str(Path(cfg.output).with_suffix("")) + ".report.json"
    src = str(cfg.input)

    # ---- 第 0 步:软字幕检查 ----
    info = probe.analyze(src)
    rep.set("streams", info.to_dict())
    if not info.video:
        raise ValueError("输入不含视频流")
    if info.subtitle and not cfg.assume_hard:
        probe.strip_soft_subtitles(src, cfg.output)
        rep.finalize("soft-strip")
        rep.save(rep_path)
        return rep

    # ---- 第 2 步:字幕定位(第一遍读,稀疏采样) ----
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频: {src}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    stride = max(1, round(fps / cfg.sample_fps))
    detector = make_detector(cfg.detector, cfg.region)

    t0 = time.time()
    per_frame: dict[int, list] = {}
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % stride == 0:
            boxes = detector.detect(frame)
            if boxes:
                per_frame[idx] = boxes
        idx += 1
    cap.release()
    n_frames = idx
    rep.set("video_meta", {"fps": fps, "width": width, "height": height,
                           "frames": n_frames, "detect_stride": stride})

    events = aggregate(per_frame, stride)
    for e in events:
        e.frame1 = min(e.frame1, n_frames - 1)
    rep.set("events", [e.to_dict() for e in events])
    rep.set("detect_seconds", round(time.time() - t0, 2))

    if not events:
        # 无字幕事件:流复制输出(输出 = 输入,零画质损失)
        ffrun([ffmpeg_bin(), "-y", "-i", src, "-c", "copy", cfg.output])
        rep.finalize("no-events-copy")
        rep.save(rep_path)
        return rep

    # ---- 第 3-6 步:擦除(第二遍读,流式) ----
    backend = get_backend(cfg.backend)
    ev_ctx = []
    for e in events:
        roi = expand_bbox(e.bbox, (height, width))
        x1, y1, _, _ = roi
        bbox_in_roi = (e.bbox[0] - x1, e.bbox[1] - y1,
                       e.bbox[2] - x1, e.bbox[3] - y1)
        mask = build_mask((roi[3] - roi[1], roi[2] - roi[0]), bbox_in_roi)
        ev_ctx.append({"ev": e, "roi": roi, "mask": mask,
                       "bbox_in_roi": bbox_in_roi, "buf": [], "buf_idx": []})

    covered: dict[int, int] = defaultdict(int)   # 帧号 → 尚未完成修复的事件数
    for c in ev_ctx:
        for f in range(c["ev"].frame0, c["ev"].frame1 + 1):
            covered[f] += 1

    pending: dict[int, np.ndarray] = {}          # 待写出帧缓冲
    next_write = 0
    sink = FrameSink(cfg.output, src, width, height, fps,
                     has_audio=bool(info.audio))

    def flush(c: dict) -> None:
        if not c["buf"]:
            return
        # 逐帧在检测框内提字幕**笔画**掩码(而非整框),擦除只填笔画邻域,避免糊整块;
        # 某帧框内提不到亮文字则回退整框掩码,保证不漏擦。
        smasks = [stroke_mask_in_box(f, c["bbox_in_roi"]) for f in c["buf"]]
        smasks = [sm if int((sm > 127).sum()) >= 20 else c["mask"] for sm in smasks]
        repaired = backend.erase_segment(c["buf"], smasks)
        for fi, patch, sm in zip(c["buf_idx"], repaired, smasks):
            feather_paste(pending[fi], c["roi"], patch, sm)
            covered[fi] -= 1
        c["buf"], c["buf_idx"] = [], []

    t0 = time.time()
    cap = cv2.VideoCapture(src)
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        pending[idx] = frame
        if covered.get(idx, 0) > 0:
            for c in ev_ctx:
                if c["ev"].frame0 <= idx <= c["ev"].frame1:
                    x1, y1, x2, y2 = c["roi"]
                    c["buf"].append(frame[y1:y2, x1:x2].copy())
                    c["buf_idx"].append(idx)
                    if len(c["buf"]) >= cfg.chunk or idx == c["ev"].frame1:
                        flush(c)
        while next_write in pending and covered.get(next_write, 0) == 0:
            sink.write(pending.pop(next_write))
            next_write += 1
        idx += 1
    cap.release()
    for c in ev_ctx:
        flush(c)
    while next_write in pending and covered.get(next_write, 0) == 0:
        sink.write(pending.pop(next_write))
        next_write += 1
    sink.close()
    if pending:
        rep.warn(f"{len(pending)} 帧未按序写出(内部错误,请检查事件区间)")

    rep.set("erase_seconds", round(time.time() - t0, 2))
    rep.data["qc"]["outside_mask_pixels"] = (
        "结构性保证:仅字幕事件 ROI 的掩码区(含 ≤5px 羽化带)被修改;"
        "整帧经过一次 H.264 重编码(crf=18)")
    rep.finalize("erase")
    rep.save(rep_path)
    return rep
