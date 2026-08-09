"""差分・誤差ヒートマップ・密度波形（P1-044 / FR-13）。"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from optpoet.image.density import DensityMap, DensityMethod
from optpoet.image.grid import Fit, GridSpec, plan_region
from optpoet.render.compare import (
    WAVEFORM_SIZE,
    build_comparison,
    density_waveform,
    difference_image,
    error_heatmap,
)
from optpoet.text.evaluate import DensityError
from optpoet.text.layout import TextLayout

GRID = GridSpec(columns=4, rows=2)


def build_error(values: list[list[float]]) -> DensityError:
    errors = np.asarray(values, dtype=np.float32)
    layout = TextLayout.from_cells(tuple("あいうえおかきく"), GRID)
    return DensityError(errors=errors, layout=layout)


def build_density_map(values: list[list[float]]) -> DensityMap:
    array = np.asarray(values, dtype=np.float32)
    return DensityMap(
        values=array,
        edges=np.zeros_like(array),
        grid=GRID,
        region=plan_region((64, 32), GRID, Fit.COVER),
        method=DensityMethod(),
    )


def test_difference_is_white_where_images_match() -> None:
    image = Image.new("L", (32, 32), 128)
    result = difference_image(image, image)
    assert result.mode == "L"
    assert np.asarray(result).min() == 255


def test_difference_is_dark_where_images_differ() -> None:
    result = difference_image(Image.new("L", (32, 32), 0), Image.new("L", (32, 32), 255))
    assert np.asarray(result).max() == 0


def test_heatmap_colors_follow_error_sign() -> None:
    error = build_error([[0.5, -0.5, 0.0, 0.5], [0.0, 0.0, -0.5, 0.0]])
    heatmap = error_heatmap(error, max_side=8)
    pixels = np.asarray(heatmap)
    assert heatmap.mode == "RGB"
    # 濃すぎ（誤差 > 0）は赤、薄すぎ（誤差 < 0）は青、一致は白。
    assert tuple(pixels[0, 0]) == (255, 0, 0)
    assert tuple(pixels[0, 2]) == (0, 0, 255)
    assert tuple(pixels[0, 4]) == (255, 255, 255)


def test_heatmap_keeps_cell_grid_aspect() -> None:
    error = build_error([[0.0] * 4, [0.0] * 4])
    assert error_heatmap(error, max_side=8).size == (8, 4)


def test_waveform_has_fixed_size() -> None:
    density_map = build_density_map([[0.2, 0.4, 0.6, 0.8], [0.1, 0.3, 0.5, 0.7]])
    error = build_error([[0.0] * 4, [0.1] * 4])
    waveform = density_waveform(density_map, error)
    assert waveform.size == WAVEFORM_SIZE
    assert waveform.mode == "RGB"


def test_waveform_rejects_unknown_axis() -> None:
    density_map = build_density_map([[0.0] * 4, [0.0] * 4])
    with pytest.raises(ValueError):
        density_waveform(density_map, build_error([[0.0] * 4, [0.0] * 4]), axis="diagonal")


def test_build_comparison_returns_three_views() -> None:
    image = Image.new("L", (32, 32), 200)
    density_map = build_density_map([[0.2, 0.4, 0.6, 0.8], [0.1, 0.3, 0.5, 0.7]])
    error = build_error([[0.1, -0.1, 0.0, 0.2], [0.0, 0.0, -0.2, 0.0]])
    views = build_comparison(image, image, density_map, error, max_side=16)
    assert views.difference.size == (16, 16)
    assert views.heatmap.size == (16, 8)
    assert views.waveform.size == WAVEFORM_SIZE
