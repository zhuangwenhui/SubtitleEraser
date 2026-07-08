"""样例效果的量化验证。

对比"去字幕输出"与"干净原片参考",计算字幕所在底部条带的 PSNR:
处理前(含字幕)约 14 dB,处理后应升到 35 dB 以上——即字幕被抹除、背景被还原。

用法:
    python samples/verify.py samples/erased.mp4
    python samples/verify.py <你的输出> --clean <干净原片> --subbed <含字幕输入>
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent


def read_frames(path: str) -> list[np.ndarray]:
    cap = cv2.VideoCapture(path)
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    cap.release()
    if not frames:
        raise SystemExit(f"读不到帧:{path}")
    return frames


def psnr(a: np.ndarray, b: np.ndarray) -> float:
    mse = np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2)
    return 99.0 if mse < 1e-6 else 10.0 * np.log10(255.0 * 255.0 / mse)


def main() -> None:
    ap = argparse.ArgumentParser(description="样例效果量化验证(字幕带 PSNR)")
    ap.add_argument("erased", help="去字幕后的输出视频")
    ap.add_argument("--clean", default=str(HERE / "clean_reference.mp4"), help="干净原片参考")
    ap.add_argument("--subbed", default=str(HERE / "subbed.mp4"), help="含字幕输入(作对照基线)")
    ap.add_argument("--band", type=float, default=0.25, help="底部字幕带高度占比")
    args = ap.parse_args()

    clean = read_frames(args.clean)
    erased = read_frames(args.erased)
    subbed = read_frames(args.subbed)
    n = min(len(clean), len(erased), len(subbed))
    h = clean[0].shape[0]
    band = slice(int(h * (1 - args.band)), h)

    before = np.mean([psnr(subbed[i][band], clean[i][band]) for i in range(n)])
    after = np.mean([psnr(erased[i][band], clean[i][band]) for i in range(n)])
    full = np.mean([psnr(erased[i], clean[i]) for i in range(n)])

    print(f"对比帧数:{n}")
    print(f"字幕带 PSNR  处理前(含字幕) = {before:5.2f} dB")
    print(f"字幕带 PSNR  处理后        = {after:5.2f} dB   (越高越接近干净原片)")
    print(f"整帧   PSNR  处理后        = {full:5.2f} dB")
    verdict = "字幕已抹除、背景已还原" if after >= 30 else "提升有限,请检查检测区域/后端"
    print(f"结论:{verdict}")


if __name__ == "__main__":
    main()
