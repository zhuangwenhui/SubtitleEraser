"""擦除后端注册表。后端以统一接口接入,选择由配置决定(不做架构分叉)。"""
from __future__ import annotations

from .base import EraseBackend
from .opencv_debug import OpenCVDebugBackend
from .flow_copy import FlowCopyBackend

_NAMES = ("opencv-debug", "flow-copy")


def get_backend(name: str, **kw) -> EraseBackend:
    if name == "opencv-debug":
        return OpenCVDebugBackend(**kw)
    if name == "flow-copy":
        return FlowCopyBackend(**kw)
    raise ValueError(f"未知擦除后端: {name}(可选: {', '.join(_NAMES)})")
