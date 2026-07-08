"""调试保底后端:OpenCV Telea 单帧修复 + 掩码区时域指数平滑。

已知局限:单帧修复逐帧独立,存在帧间闪烁;时域指数平滑(EMA)只能缓解、
不能消除。本后端仅供管线调试与最低档保底,质量优先请用 flow-copy 后端。
"""
from __future__ import annotations

import cv2
import numpy as np

from .base import EraseBackend


class OpenCVDebugBackend(EraseBackend):
    name = "opencv-debug"

    def __init__(self, inpaint_radius: int = 3, ema_alpha: float = 0.2):
        self.radius = inpaint_radius
        self.alpha = ema_alpha  # 新帧权重;越小时域越稳、拖影越重

    def erase_segment(self, frames, masks):
        out: list[np.ndarray] = []
        prev: np.ndarray | None = None
        for img, mask in zip(frames, masks):
            cur = cv2.inpaint(img, mask, self.radius, cv2.INPAINT_TELEA)
            if prev is not None:
                m = mask.astype(bool)
                blend = cur.astype(np.float32)
                blend[m] = ((1 - self.alpha) * prev.astype(np.float32)[m]
                            + self.alpha * blend[m])
                cur = blend.astype(np.uint8)
            prev = cur
            out.append(cur)
        return out
