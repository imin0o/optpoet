"""差分・誤差ヒートマップ・密度波形（P1-044 / FR-13）。

3 枚とも「どこがどれだけずれたか」を別の粒度で見せる。

- **差分**: 画素領域。目標画像と生成結果の密度差の絶対値で、一致が白、ずれが黒。
- **ヒートマップ**: セル領域。符号付き誤差で、濃すぎるセルが赤、薄すぎるセルが青。
  符号は `DensityError`（文字密度 − 目標密度）の定義をそのまま使う。
- **密度波形**: 行（または列）ごとの平均密度を、目標と達成の 2 本の折れ線で重ねる。
  面としてのずれではなく、上下（左右）方向の傾きのずれを見るための図。

セル領域の 2 枚はセル比を反映した比率へ拡大する。拡大は最近傍にし、どのセルがどの誤差か
を目で追えるようにする（`optpoet.image.preview` と同じ方針）。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageDraw

from optpoet.image.density import DensityMap
from optpoet.image.preview import PREVIEW_MAX_SIDE, fit_preview
from optpoet.render.metrics import Array, density, resize
from optpoet.render.style import INK, PAPER
from optpoet.text.evaluate import DensityError

WAVEFORM_SIZE = (512, 160)
TARGET_COLOR = (128, 128, 128)
ACHIEVED_COLOR = INK
AXIS_COLOR = (208, 208, 208)


@dataclass(frozen=True, slots=True, eq=False)
class ComparisonSet:
    """比較表示に渡す 3 枚。すべて新しい画像で、元の画像とは独立する。"""

    difference: Image.Image
    heatmap: Image.Image
    waveform: Image.Image


def build_comparison(
    target: Image.Image,
    rendered: Image.Image,
    density_map: DensityMap,
    error: DensityError,
    *,
    max_side: int = PREVIEW_MAX_SIDE,
) -> ComparisonSet:
    """差分・ヒートマップ・密度波形をまとめて作る。"""
    return ComparisonSet(
        difference=difference_image(target, rendered, max_side=max_side),
        heatmap=error_heatmap(error, max_side=max_side),
        waveform=density_waveform(density_map, error),
    )


def difference_image(
    target: Image.Image,
    rendered: Image.Image,
    *,
    max_side: int = PREVIEW_MAX_SIDE,
) -> Image.Image:
    """密度差の絶対値を白地の濃淡にする。比較解像度は生成結果に合わせる。"""
    actual = density(rendered)
    expected = resize(density(target), (actual.shape[1], actual.shape[0]))
    gap = np.abs(actual - expected)
    levels = np.rint((1.0 - np.clip(gap, 0.0, 1.0)) * 255.0).astype(np.uint8)
    return fit_preview(Image.fromarray(levels, mode="L"), max_side=max_side)


def error_heatmap(
    error: DensityError,
    *,
    max_side: int = PREVIEW_MAX_SIDE,
    scale: float | None = None,
) -> Image.Image:
    """符号付き誤差を赤（濃すぎ）／青（薄すぎ）で塗る。`scale` は誤差の飽和点。"""
    errors = np.asarray(error.errors, dtype=np.float32)
    limit = float(np.abs(errors).max()) if scale is None else scale
    intensity = np.zeros_like(errors) if limit <= 0.0 else np.clip(np.abs(errors) / limit, 0.0, 1.0)
    faded = np.rint((1.0 - intensity) * 255.0).astype(np.uint8)
    full = np.full_like(faded, 255)

    too_dark = errors > 0.0
    red = np.where(too_dark, full, faded)
    green = faded
    blue = np.where(too_dark, faded, full)
    cells = Image.fromarray(np.stack((red, green, blue), axis=-1), mode="RGB")
    return _scaled(cells, _cell_view_size(error, max_side))


def density_waveform(
    density_map: DensityMap,
    error: DensityError,
    *,
    axis: str = "row",
    size: tuple[int, int] = WAVEFORM_SIZE,
) -> Image.Image:
    """行（または列）ごとの平均密度を、目標と達成の 2 本で重ねる。"""
    if axis not in {"row", "column"}:
        raise ValueError(f"axis は 'row' か 'column': {axis!r}")
    target = np.asarray(density_map.values, dtype=np.float32)
    achieved = target + np.asarray(error.errors, dtype=np.float32)
    reduce_axis = 1 if axis == "row" else 0

    image = Image.new("RGB", size, PAPER)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, size[0] - 1, size[1] - 1), outline=AXIS_COLOR)
    draw.line((0, size[1] // 2, size[0] - 1, size[1] // 2), fill=AXIS_COLOR)
    _plot(draw, target.mean(axis=reduce_axis), size, TARGET_COLOR)
    _plot(draw, achieved.mean(axis=reduce_axis), size, ACHIEVED_COLOR)
    return image


def _plot(
    draw: ImageDraw.ImageDraw,
    series: NDArray[np.float32] | Array,
    size: tuple[int, int],
    color: tuple[int, int, int],
) -> None:
    """0.0〜1.0 の系列を折れ線で描く。密度 1.0 が上端。"""
    width, height = size
    count = len(series)
    points = [
        (
            round(index * (width - 1) / (count - 1)) if count > 1 else 0,
            round((1.0 - float(np.clip(value, 0.0, 1.0))) * (height - 1)),
        )
        for index, value in enumerate(series)
    ]
    if len(points) == 1:
        draw.point(points[0], fill=color)
        return
    draw.line(points, fill=color, width=1)


def _cell_view_size(error: DensityError, max_side: int) -> tuple[int, int]:
    """セル比を反映した表示サイズ。長辺が `max_side` になるよう合わせる。"""
    grid = error.layout.grid
    width = grid.columns * grid.cell_aspect
    height = float(grid.rows)
    factor = max_side / max(width, height)
    return (max(1, round(width * factor)), max(1, round(height * factor)))


def _scaled(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """拡大は最近傍でセル境界を残し、縮小は面積平均で潰れを抑える。"""
    if image.size == size:
        return image
    enlarging = size[0] >= image.width and size[1] >= image.height
    resample = Image.Resampling.NEAREST if enlarging else Image.Resampling.BOX
    return image.resize(size, resample)
