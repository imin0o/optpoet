"""比較用プレビューを作る（P1-015 / FR-03）。

FR-03 は「元画像、密度マップ、エッジ補助結果を比較でき、設定を再編集できる」ことを
求める。ここでは 4 枚（元画像 / 前処理後 / 密度マップ / エッジ結果）を同じ長辺へ
揃えて返す。設定の再編集は `Preprocess` と `DensityMethod` を差し替えて作り直すだけで
済むため、プレビュー自身は状態を持たない。

密度マップとエッジ結果は 0.00（白）〜1.00（黒）を明度へ写して描く。セル比を反映した
比率で拡大するので、元画像と並べたときに形が一致する。拡大は最近傍にし、セルの境界を
ぼかさない（どのセルがどの密度かを目で追えるようにする）。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from optpoet.image.density import Array, DensityMap

# プレビューの既定の長辺。作品規模（2,000〜5,000 セル）でも画面内に収まる大きさ。
PREVIEW_MAX_SIDE = 512


@dataclass(frozen=True, slots=True, eq=False)
class PreviewSet:
    """比較表示に渡す 4 枚。すべて新しい画像で、元の画像とは独立する。"""

    source: Image.Image
    preprocessed: Image.Image
    density: Image.Image
    edges: Image.Image


def build_previews(
    source: Image.Image,
    preprocessed: Image.Image,
    density_map: DensityMap,
    *,
    max_side: int = PREVIEW_MAX_SIDE,
) -> PreviewSet:
    """元画像・前処理後・密度マップ・エッジ結果のプレビューをまとめて作る。"""
    return PreviewSet(
        source=fit_preview(source, max_side=max_side),
        preprocessed=fit_preview(preprocessed, max_side=max_side),
        density=density_preview(density_map, max_side=max_side),
        edges=edge_preview(density_map, max_side=max_side),
    )


def fit_preview(image: Image.Image, *, max_side: int = PREVIEW_MAX_SIDE) -> Image.Image:
    """長辺を `max_side` 以内へ収めた複製を返す。元より小さい画像は拡大しない。"""
    _require_positive(max_side)
    working = image.copy()
    working.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return working


def density_preview(density_map: DensityMap, *, max_side: int = PREVIEW_MAX_SIDE) -> Image.Image:
    """密度マップを白地の濃淡画像にする。密度 1.00 が黒。"""
    return _map_preview(density_map.values, density_map, max_side)


def edge_preview(density_map: DensityMap, *, max_side: int = PREVIEW_MAX_SIDE) -> Image.Image:
    """エッジ結果を白地の濃淡画像にする。強いエッジほど黒。"""
    return _map_preview(density_map.edges, density_map, max_side)


def _map_preview(values: Array, density_map: DensityMap, max_side: int) -> Image.Image:
    _require_positive(max_side)
    levels = np.rint((1.0 - np.clip(values, 0.0, 1.0)) * 255.0).astype(np.uint8)
    cells = Image.fromarray(levels, mode="L")
    return _scaled(cells, _preview_size(density_map, max_side))


def _preview_size(density_map: DensityMap, max_side: int) -> tuple[int, int]:
    """セル比を反映した表示サイズ。長辺が `max_side` になるよう合わせる。"""
    grid = density_map.grid
    width = grid.columns * grid.cell_aspect
    height = float(grid.rows)
    scale = max_side / max(width, height)
    return (max(1, round(width * scale)), max(1, round(height * scale)))


def _scaled(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """拡大は最近傍でセル境界を残し、縮小は面積平均で潰れを抑える。"""
    if image.size == size:
        return image
    enlarging = size[0] >= image.width and size[1] >= image.height
    resample = Image.Resampling.NEAREST if enlarging else Image.Resampling.BOX
    return image.resize(size, resample)


def _require_positive(max_side: int) -> None:
    if max_side <= 0:
        raise ValueError(f"max_side は 1 以上: {max_side}")
