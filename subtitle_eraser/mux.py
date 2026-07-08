"""处理骨架第 6 步:输出装配。

处理后的帧流经 rawvideo 管道送入 ffmpeg 一次性完成 H.264 编码,
音轨从原片流复制(不重编码)。
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from .ffmpeg_tools import ffmpeg_bin


class FrameSink:
    """按顺序接收 BGR 帧并写入目标文件。"""

    def __init__(self, dst: str, src_for_audio: str, width: int, height: int,
                 fps: float, has_audio: bool, crf: int = 18):
        Path(dst).parent.mkdir(parents=True, exist_ok=True)  # 输出目录不存在则建
        cmd = [ffmpeg_bin(), "-y",
               "-f", "rawvideo", "-pix_fmt", "bgr24",
               "-s", f"{width}x{height}", "-r", f"{fps:.6f}", "-i", "pipe:0"]
        if has_audio:
            cmd += ["-i", src_for_audio, "-map", "0:v:0", "-map", "1:a?",
                    "-c:a", "copy", "-shortest"]
        else:
            cmd += ["-map", "0:v:0"]
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
                "-pix_fmt", "yuv420p", dst]
        self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                      stderr=subprocess.PIPE)

    def write(self, frame_bgr: np.ndarray) -> None:
        self._proc.stdin.write(np.ascontiguousarray(frame_bgr).tobytes())

    def close(self) -> None:
        self._proc.stdin.close()
        err = self._proc.stderr.read().decode(errors="ignore")
        if self._proc.wait() != 0:
            raise RuntimeError(f"输出编码失败:\n{err[-2000:]}")
