"""处理骨架第 0 步:软字幕检查与剥离。

若输入容器内含字幕流(软字幕),直接流复制剥轨返回,不进入视觉管线;
无重编码、无画质损失。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .ffmpeg_tools import ffmpeg_bin, probe_json, run


@dataclass
class StreamInfo:
    video: list[dict] = field(default_factory=list)
    audio: list[dict] = field(default_factory=list)
    subtitle: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"video": self.video, "audio": self.audio, "subtitle": self.subtitle}


def analyze(path: str | Path) -> StreamInfo:
    """列出输入的视频/音频/字幕流(封面图流不计入视频)。"""
    info = StreamInfo()
    for s in probe_json(path).get("streams", []):
        entry = {
            "index": s.get("index"),
            "codec": s.get("codec_name"),
            "lang": (s.get("tags") or {}).get("language"),
        }
        kind = s.get("codec_type")
        if kind == "video":
            if (s.get("disposition") or {}).get("attached_pic") == 1:
                continue  # 封面图
            info.video.append(entry)
        elif kind == "audio":
            info.audio.append(entry)
        elif kind == "subtitle":
            info.subtitle.append(entry)
    return info


def has_soft_subtitles(path: str | Path) -> bool:
    return len(analyze(path).subtitle) > 0


def strip_soft_subtitles(src: str | Path, dst: str | Path) -> None:
    """剥离全部字幕流,其余流复制。

    注:输出容器由 dst 后缀决定,建议与输入同容器;
    mkv 内嵌字体附件等特殊流暂不处理(v0.1 已知限制)。
    """
    run([ffmpeg_bin(), "-y", "-i", str(src),
         "-map", "0", "-map", "-0:s", "-c", "copy", str(dst)])
