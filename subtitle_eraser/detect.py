"""处理骨架第 2 步(前半):字幕定位 — 文本检测接口与实现。

v0.1 提供两种检测器:
- fixed  : 固定区域(如画面底部 35%),用于字幕位置已知的场景与无 GPU 冒烟运行;
- paddle : PP-OCRv5 文本检测(懒加载;需另装 paddlepaddle-gpu + paddleocr,
           未安装不影响模块其余功能)。仅做检测(文字在哪),不做识别(文字是什么)。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass
class TextBox:
    x1: int
    y1: int
    x2: int
    y2: int
    score: float = 1.0


class TextDetector(ABC):
    name = "base"

    @abstractmethod
    def detect(self, frame_bgr: np.ndarray) -> list[TextBox]:
        ...


class FixedRegionDetector(TextDetector):
    """固定区域"检测":恒定返回配置区域。配合 --region bottom:<ratio> 使用。"""

    name = "fixed"

    def __init__(self, region: str = "bottom:0.35"):
        kind, _, val = region.partition(":")
        if kind != "bottom":
            raise ValueError(f"暂只支持 bottom:<ratio> 形式的区域,收到: {region}")
        self.ratio = float(val or 0.35)

    def detect(self, frame_bgr: np.ndarray) -> list[TextBox]:
        h, w = frame_bgr.shape[:2]
        return [TextBox(0, int(h * (1 - self.ratio)), w, h)]


class PaddleTextDetector(TextDetector):
    """PP-OCRv5 文本检测器(懒加载)。

    注意:PaddleOCR 3.x 的 TextDetection 接口尚未在本机联调,
    安装后请先跑 tests/ 冒烟再接入正式管线。
    """

    name = "paddle"

    def __init__(self, model_name: str = "PP-OCRv5_server_det"):
        try:
            from paddleocr import TextDetection  # PaddleOCR 3.x
        except ImportError as e:
            raise RuntimeError(
                "未安装 paddleocr:请执行 `pip install paddlepaddle-gpu paddleocr` 后重试"
            ) from e
        self._impl = TextDetection(model_name=model_name)

    def detect(self, frame_bgr: np.ndarray) -> list[TextBox]:
        """PaddleOCR 3.x:predict() 返回 TextDetResult 列表,
        dt_polys 为 (N,4,2) ndarray,dt_scores 为 list。"""
        boxes: list[TextBox] = []
        for item in self._impl.predict(frame_bgr):
            polys = item["dt_polys"]
            scores = item["dt_scores"]
            n = 0 if polys is None else len(polys)
            for i in range(n):
                poly = np.asarray(polys[i])
                xs, ys = poly[:, 0], poly[:, 1]
                score = float(scores[i]) if i < len(scores) else 1.0
                boxes.append(TextBox(int(xs.min()), int(ys.min()),
                                     int(xs.max()), int(ys.max()), score))
        return boxes


def make_detector(name: str, region: str) -> TextDetector:
    if name == "fixed":
        return FixedRegionDetector(region)
    if name == "paddle":
        return PaddleTextDetector()
    raise ValueError(f"未知检测器: {name}(可选: fixed, paddle)")
