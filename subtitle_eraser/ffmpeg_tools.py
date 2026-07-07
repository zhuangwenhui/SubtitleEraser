"""ffmpeg/ffprobe 定位与调用封装。

解析顺序:环境变量 FFMPEG_BIN / FFPROBE_BIN > PATH > 项目内 tools/ffmpeg/ 静态版。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools" / "ffmpeg"


def _resolve(name: str, env_key: str) -> str:
    env = os.environ.get(env_key)
    if env and Path(env).exists():
        return env
    found = shutil.which(name)
    if found:
        return found
    local = _TOOLS_DIR / name
    if local.exists():
        return str(local)
    raise FileNotFoundError(f"未找到 {name}:请安装 ffmpeg,或将静态版放入 {_TOOLS_DIR}")


def ffmpeg_bin() -> str:
    return _resolve("ffmpeg", "FFMPEG_BIN")


def ffprobe_bin() -> str:
    return _resolve("ffprobe", "FFPROBE_BIN")


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    """执行外部命令;失败时抛出含 stderr 尾部的异常。"""
    proc = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if proc.returncode != 0:
        raise RuntimeError(f"命令失败: {' '.join(cmd)}\n{proc.stderr[-2000:]}")
    return proc


def probe_json(path: str | Path) -> dict:
    proc = run([ffprobe_bin(), "-v", "error", "-print_format", "json",
                "-show_streams", "-show_format", str(path)])
    return json.loads(proc.stdout)
