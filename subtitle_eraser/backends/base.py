"""擦除后端统一接口。

约定:后端在「字幕事件的 ROI 片段」粒度工作——输入某事件一段连续帧的
ROI 裁剪与对应掩码,输出修复后的 ROI 帧。骨架负责裁剪、分块与羽化回贴,
后端只关心"把掩码区域的内容补出来"。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class EraseBackend(ABC):
    name = "base"

    @abstractmethod
    def erase_segment(self, frames: list[np.ndarray],
                      masks: list[np.ndarray]) -> list[np.ndarray]:
        """修复一段连续 ROI 帧。

        frames: BGR uint8 ROI 帧列表(同尺寸);
        masks : 与 frames 对齐的 uint8 掩码(255=待修复区域);
        返回  : 修复后的 ROI 帧列表,长度与输入一致。
        """
        ...
