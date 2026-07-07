"""处理报告(JSON):字幕时间轴、各阶段结果、质检结论、失败标记。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import __version__


class Report:
    def __init__(self, config: dict):
        self.data: dict = {
            "tool": "subtitle-eraser",
            "version": __version__,
            "config": config,
            "started_at": _now(),
            "mode": None,          # soft-strip | no-events-copy | erase
            "streams": None,
            "video_meta": None,
            "events": [],
            "qc": {"ocr_recheck": "not_run", "outside_mask_pixels": None},
            "warnings": [],
        }

    def set(self, key: str, value) -> None:
        self.data[key] = value

    def warn(self, msg: str) -> None:
        self.data["warnings"].append(msg)

    def finalize(self, mode: str) -> None:
        self.data["mode"] = mode
        self.data["finished_at"] = _now()

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.data, ensure_ascii=False, indent=2),
                              encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
