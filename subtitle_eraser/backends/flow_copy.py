"""经典时序传播后端(flow-copy)—— 无模型,纯视觉算法。

思路:字幕(尤其静态条带)遮住的背景,常在**别的帧**里露出来过。对每帧掩码区,
按时间由近及远搜索"该像素在其中未被遮挡"的邻帧,用 Farneback 稠密光流把那一帧
warp 到当前帧坐标后搬运真像素回来;整段都没露出过的残余像素再用单帧 Telea 兜底;
最后对掩码区做轻度时域指数平滑抑制闪烁。

适用:静态或缓变背景下的字幕(尤其固定字幕条带)。运动剧烈或整段从未露出的区域
由单帧 Telea 兜底;与单帧基线 opencv-debug 相比,时域传播能显著抑制帧间闪烁。
"""
from __future__ import annotations

import cv2
import numpy as np

from .base import EraseBackend


class FlowCopyBackend(EraseBackend):
    name = "flow-copy"

    def __init__(self, window: int = 16, ema_alpha: float = 0.5,
                 telea_radius: int = 3):
        self.window = window          # 每侧最多搜索多少帧找"露出帧"
        self.alpha = ema_alpha        # 掩码区时域平滑:新帧权重
        self.radius = telea_radius

    def erase_segment(self, frames, masks):
        n = len(frames)
        if n == 0:
            return []
        h, w = frames[0].shape[:2]
        grays = [cv2.cvtColor(f, cv2.COLOR_GRAY2BGR) if f.ndim == 2 else f for f in frames]
        grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in grays]
        bin_masks = [(m > 127) for m in masks]
        gx, gy = np.meshgrid(np.arange(w, dtype=np.float32),
                             np.arange(h, dtype=np.float32))

        out: list[np.ndarray] = []
        prev: np.ndarray | None = None
        for i in range(n):
            hole = bin_masks[i]
            filled = frames[i].copy()
            if not hole.any():
                out.append(filled)
                prev = filled
                continue
            remaining = hole.copy()

            # 由近及远搜索露出该像素的邻帧,光流对齐后搬运
            for r in range(1, self.window + 1):
                if not remaining.any():
                    break
                for j in (i - r, i + r):
                    if j < 0 or j >= n or not remaining.any():
                        continue
                    revealed = remaining & (~bin_masks[j])   # i 处遮挡、j 处露出
                    if not revealed.any():
                        continue
                    flow = cv2.calcOpticalFlowFarneback(
                        grays[i], grays[j], None, 0.5, 3, 21, 3, 5, 1.2, 0)
                    map_x = gx + flow[..., 0]
                    map_y = gy + flow[..., 1]
                    warp = cv2.remap(frames[j], map_x, map_y, cv2.INTER_LINEAR,
                                     borderMode=cv2.BORDER_REPLICATE)
                    # 只采纳 warp 落点仍在 j 的露出区内的像素(避免搬来另一处的字幕)
                    warp_valid = cv2.remap((~bin_masks[j]).astype(np.uint8), map_x, map_y,
                                           cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT) > 0
                    take = revealed & warp_valid
                    if take.any():
                        filled[take] = warp[take]
                        remaining &= ~take

            # 整段未露出的残余 → 单帧 Telea 兜底
            if remaining.any():
                filled = cv2.inpaint(filled, (remaining * 255).astype(np.uint8),
                                     self.radius, cv2.INPAINT_TELEA)

            # 掩码区时域平滑(抑制帧间闪烁)
            if prev is not None:
                m = hole
                blended = filled.astype(np.float32)
                blended[m] = ((1 - self.alpha) * prev.astype(np.float32)[m]
                              + self.alpha * blended[m])
                filled = blended.astype(np.uint8)
            prev = filled
            out.append(filled)
        return out
