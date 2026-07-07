"""处理骨架第 2 步(后半):字幕事件聚合与掩码生成。

「字幕事件」= 同一条字幕从出现到消失的时间区间。事件内共用一个稳定包围盒/掩码,
避免逐帧检测框抖动引起的修复闪烁。v0.1 用 IoU 贪心关联 + 间隙容忍实现。
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .detect import TextBox


@dataclass
class SubtitleEvent:
    frame0: int                      # 闭区间起始帧
    frame1: int                      # 闭区间结束帧
    bbox: tuple[int, int, int, int]  # 事件级联合包围盒 (x1,y1,x2,y2)
    n_hits: int = 0                  # 命中采样帧数

    def to_dict(self) -> dict:
        return {"frame0": self.frame0, "frame1": self.frame1,
                "bbox": list(self.bbox), "n_hits": self.n_hits}


def _iou(a: tuple, b: tuple) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    if inter == 0:
        return 0.0
    area = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / max(area, 1)


def aggregate(per_frame: dict[int, list[TextBox]], stride: int,
              iou_thr: float = 0.3, max_gap_frames: int = 15,
              min_hits: int = 2) -> list[SubtitleEvent]:
    """把稀疏采样帧上的检测框聚合为字幕事件。

    per_frame: {原视频帧号: [TextBox, ...]},帧号按 stride 采样。
    同一轨迹允许 max_gap_frames 的检测间隙(容忍闪失);
    命中次数 < min_hits 的孤立框按误检丢弃。
    """
    tracks: list[dict] = []
    events: list[SubtitleEvent] = []

    def close(tr: dict) -> SubtitleEvent:
        return SubtitleEvent(frame0=max(0, tr["first"] - stride // 2),
                             frame1=tr["last"] + stride // 2,
                             bbox=tuple(tr["bbox"]), n_hits=tr["hits"])

    for f in sorted(per_frame):
        boxes = per_frame[f]
        used: set[int] = set()
        for tr in tracks:
            best_i, best_v = None, iou_thr
            for i, b in enumerate(boxes):
                if i in used:
                    continue
                v = _iou(tr["bbox"], (b.x1, b.y1, b.x2, b.y2))
                if v >= best_v:
                    best_i, best_v = i, v
            if best_i is not None:
                b = boxes[best_i]
                used.add(best_i)
                x1, y1, x2, y2 = tr["bbox"]
                tr["bbox"] = [min(x1, b.x1), min(y1, b.y1), max(x2, b.x2), max(y2, b.y2)]
                tr["last"] = f
                tr["hits"] += 1
        alive = []
        for tr in tracks:
            if f - tr["last"] > max_gap_frames:
                events.append(close(tr))
            else:
                alive.append(tr)
        tracks = alive
        for i, b in enumerate(boxes):
            if i not in used:
                tracks.append({"bbox": [b.x1, b.y1, b.x2, b.y2],
                               "first": f, "last": f, "hits": 1})

    events.extend(close(tr) for tr in tracks)
    events = [e for e in events if e.n_hits >= min_hits]
    return sorted(events, key=lambda e: e.frame0)


def expand_bbox(bbox: tuple[int, int, int, int], shape_hw: tuple[int, int],
                margin_y_ratio: float = 0.75, margin_x_ratio: float = 0.10
                ) -> tuple[int, int, int, int]:
    """事件包围盒 → ROI(感兴趣区域):按字高比例上下留余量,给修复算法背景上下文。"""
    h, w = shape_hw
    x1, y1, x2, y2 = bbox
    box_h = max(1, y2 - y1)
    my = int(box_h * margin_y_ratio)
    mx = int((x2 - x1) * margin_x_ratio)
    return (max(0, x1 - mx), max(0, y1 - my), min(w, x2 + mx), min(h, y2 + my))


def build_mask(roi_shape_hw: tuple[int, int], bbox_in_roi: tuple[int, int, int, int],
               dilate_ratio: float = 0.18) -> np.ndarray:
    """在 ROI 坐标系内生成事件掩码;按字高比例膨胀,覆盖描边/抗锯齿边缘。"""
    mask = np.zeros(roi_shape_hw, dtype=np.uint8)
    x1, y1, x2, y2 = bbox_in_roi
    mask[max(0, y1):y2, max(0, x1):x2] = 255
    k = max(3, int((y2 - y1) * dilate_ratio) | 1)  # 奇数核
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
    return cv2.dilate(mask, kernel)


def stroke_mask_in_box(frame_bgr: np.ndarray, bbox: tuple[int, int, int, int],
                       min_thresh: int = 165, k: int = 9) -> np.ndarray:
    """在检测框内提取字幕**笔画**掩码(而非整框):框内亮像素阈值 → 闭运算连通 →
    膨胀盖住描边/抗锯齿。擦除只填笔画邻域,面积远小于整框,避免把框内背景一起糊掉。
    亮文字(白字/描边字)适用;框内无亮文字时返回空掩码(该帧不改动)。"""
    h, w = frame_bgr.shape[:2]
    x1, y1, x2, y2 = bbox
    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
    m = np.zeros((h, w), dtype=np.uint8)
    if x2 - x1 < 3 or y2 - y1 < 3:
        return m
    roi = frame_bgr[y1:y2, x1:x2]
    g = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
    th = max(min_thresh, int(g.mean() + 0.8 * g.std()))
    s = (g > th).astype(np.uint8) * 255
    rect = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
    ell = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    s = cv2.morphologyEx(s, cv2.MORPH_CLOSE, rect)
    s = cv2.dilate(s, ell, iterations=2)
    m[y1:y2, x1:x2] = s
    return m


def feather_paste(frame: np.ndarray, roi: tuple[int, int, int, int],
                  repaired_roi: np.ndarray, mask_roi: np.ndarray,
                  feather_px: int = 5) -> None:
    """把修复后的 ROI 以羽化边缘贴回整帧(原地修改)。掩码外像素保持原样。"""
    x1, y1, x2, y2 = roi
    alpha = cv2.GaussianBlur(mask_roi, (feather_px * 2 + 1, feather_px * 2 + 1), 0)
    alpha = (alpha.astype(np.float32) / 255.0)[..., None]
    region = frame[y1:y2, x1:x2].astype(np.float32)
    frame[y1:y2, x1:x2] = (region * (1 - alpha) +
                           repaired_roi.astype(np.float32) * alpha).astype(np.uint8)
