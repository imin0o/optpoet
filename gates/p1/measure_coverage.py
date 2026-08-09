"""検証データセットのカバレッジ実測（P0-032 / validation-dataset.md 6 章）を再計算する。

実行: `python gates/p1/measure_coverage.py`

計算式を実行可能な形で固定し、画像を差し替えたときに同じ手順で表を作り直せるようにする。
定義は validation-dataset.md 6 章と同じ:

- 長辺 1024px へ縮小（面積平均）し、Rec.709 の輝度 0.0–1.0 へ変換する。
- 平均 / RMS（標準偏差）/ レンジ（第98−第2百分位）
- 暗部% = 輝度 < 0.15、明部% = 輝度 > 0.85
- 細線% = Sobel(ksize=3) の勾配強度（カーネル正規化 1/4）> 0.12
- 平坦% = 8×8 ブロックの標準偏差 < 0.03
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
from dataset import IMAGES
from numpy.typing import NDArray

LONG_SIDE = 1024
DARK = 0.15
BRIGHT = 0.85
EDGE = 0.12
FLAT_BLOCK = 8
FLAT_STD = 0.03
SOBEL_NORM = 4.0

Gray = NDArray[np.float64]


def to_gray(path: Path) -> Gray:
    """長辺 1024px へ縮小し、Rec.709 の輝度 0.0–1.0 を返す。"""
    data = np.fromfile(str(path), dtype=np.uint8)
    bgr = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if bgr is None:
        raise SystemExit(f"画像を読めない: {path}")
    height, width = bgr.shape[:2]
    scale = LONG_SIDE / max(height, width)
    size = (round(width * scale), round(height * scale))
    interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LANCZOS4
    rgb = cv2.resize(bgr, size, interpolation=interpolation)[:, :, ::-1].astype(np.float64)
    return (0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]) / 255.0


def measure(gray: Gray) -> dict[str, float]:
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3) / SOBEL_NORM
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3) / SOBEL_NORM
    magnitude = np.hypot(gx, gy)
    low, high = np.percentile(gray, [2, 98])
    height, width = gray.shape
    rows, columns = height // FLAT_BLOCK, width // FLAT_BLOCK
    blocks = gray[: rows * FLAT_BLOCK, : columns * FLAT_BLOCK].reshape(
        rows, FLAT_BLOCK, columns, FLAT_BLOCK
    )
    return {
        "mean": round(float(gray.mean()), 2),
        "rms": round(float(gray.std()), 2),
        "range": round(float(high - low), 2),
        "dark": round(float((gray < DARK).mean() * 100), 1),
        "bright": round(float((gray > BRIGHT).mean() * 100), 1),
        "edge": round(float((magnitude > EDGE).mean() * 100), 1),
        "flat": round(float((blocks.std(axis=(1, 3)) < FLAT_STD).mean() * 100), 1),
    }


def main() -> int:
    missing = [a.slot for a in IMAGES if not a.path.is_file()]
    if missing:
        raise SystemExit(f"資産が未取得: {missing}（先に fetch_assets.py を実行する）")
    print("| slot | 平均 | RMS | レンジ | 暗部% | 明部% | 細線% | 平坦% |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for asset in IMAGES:
        row = measure(to_gray(asset.path))
        print(
            f"| {asset.slot} | {row['mean']:.2f} | {row['rms']:.2f} | {row['range']:.2f} "
            f"| {row['dark']:.1f} | {row['bright']:.1f} | {row['edge']:.1f} | {row['flat']:.1f} |"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
