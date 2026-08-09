"""比較用プレビュー生成の検証（P1-015 / FR-03）。"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from optpoet.image import (
    DensityMap,
    GridSpec,
    PreviewSet,
    build_density_map,
    build_previews,
    density_preview,
    edge_preview,
    fit_preview,
)


def _split(size: tuple[int, int] = (40, 20)) -> Image.Image:
    """左半分が黒、右半分が白の画像。"""
    image = Image.new("RGB", size, (255, 255, 255))
    for x in range(size[0] // 2):
        for y in range(size[1]):
            image.putpixel((x, y), (0, 0, 0))
    return image


def _map(columns: int = 4, rows: int = 2, cell_aspect: float = 1.0) -> DensityMap:
    grid = GridSpec(columns=columns, rows=rows, cell_aspect=cell_aspect)
    return build_density_map(_split(), grid)


def _darkest(image: Image.Image) -> int:
    return int(np.asarray(image).min())


def test_build_previews_returns_four_images() -> None:
    source = _split()
    previews = build_previews(source, source, _map(), max_side=64)
    assert isinstance(previews, PreviewSet)
    for image in (previews.source, previews.preprocessed, previews.density, previews.edges):
        assert isinstance(image, Image.Image)
        assert max(image.size) <= 64


def test_source_preview_does_not_share_the_original() -> None:
    source = _split(size=(200, 100))
    before = source.size
    preview = fit_preview(source, max_side=50)
    assert source.size == before
    assert max(preview.size) == 50


def test_fit_preview_keeps_the_aspect() -> None:
    preview = fit_preview(_split(size=(200, 100)), max_side=50)
    assert preview.size == (50, 25)


def test_fit_preview_does_not_enlarge() -> None:
    source = _split(size=(20, 10))
    assert fit_preview(source, max_side=512).size == (20, 10)


def test_density_preview_maps_density_to_darkness() -> None:
    """左半分が黒（密度 1.00）なので、プレビューの左が暗く右が明るい。"""
    preview = density_preview(_map(), max_side=64)
    assert preview.mode == "L"
    assert preview.getpixel((0, 0)) == 0
    assert preview.getpixel((preview.width - 1, 0)) == 255


def test_density_preview_matches_the_grid_aspect() -> None:
    preview = density_preview(_map(columns=4, rows=2), max_side=64)
    assert preview.size == (64, 32)


def test_density_preview_reflects_cell_aspect() -> None:
    """セルが縦長なら、同じセル数でもプレビューは横に狭くなる。"""
    preview = density_preview(_map(columns=4, rows=2, cell_aspect=0.5), max_side=64)
    assert preview.size == (64, 64)


def test_density_preview_keeps_cell_edges_sharp() -> None:
    """拡大は最近傍。セル境界の前後で値が切り替わり、間の階調を作らない。"""
    preview = density_preview(_map(columns=2, rows=1), max_side=64)
    levels = {preview.getpixel((x, 0)) for x in range(preview.width)}
    assert levels == {0, 255}


def test_edge_preview_shows_the_boundary() -> None:
    preview = edge_preview(_map(), max_side=64)
    assert preview.mode == "L"
    assert _darkest(preview) < 255


def test_edge_preview_is_white_on_a_flat_image() -> None:
    flat = Image.new("RGB", (40, 20), (128, 128, 128))
    density_map = build_density_map(flat, GridSpec(columns=4, rows=2))
    assert _darkest(edge_preview(density_map, max_side=64)) == 255


def test_previews_shrink_a_large_grid() -> None:
    grid = GridSpec(columns=100, rows=50)
    density_map = build_density_map(_split(size=(200, 100)), grid)
    assert density_preview(density_map, max_side=40).size == (40, 20)


@pytest.mark.parametrize("max_side", [0, -1])
def test_non_positive_max_side_is_rejected(max_side: int) -> None:
    with pytest.raises(ValueError):
        fit_preview(_split(), max_side=max_side)
    with pytest.raises(ValueError):
        density_preview(_map(), max_side=max_side)
