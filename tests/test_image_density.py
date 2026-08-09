"""密度マップ生成の検証（P1-014 / FR-03）。"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from optpoet.config import ImageConfig
from optpoet.errors import ErrorKind, StageError
from optpoet.image import DensityMap, DensityMethod, Fit, GridSpec, build_density_map

BLACK = (0, 0, 0)
GRAY = (128, 128, 128)
WHITE_RGB = (255, 255, 255)


def _solid(color: tuple[int, int, int], size: tuple[int, int] = (40, 20)) -> Image.Image:
    return Image.new("RGB", size, color)


def _split(size: tuple[int, int] = (40, 20)) -> Image.Image:
    """左半分が黒、右半分が白の画像。"""
    image = Image.new("RGB", size, WHITE_RGB)
    for x in range(size[0] // 2):
        for y in range(size[1]):
            image.putpixel((x, y), BLACK)
    return image


def test_white_image_has_zero_density() -> None:
    result = build_density_map(_solid(WHITE_RGB), GridSpec(columns=4, rows=2))
    assert isinstance(result, DensityMap)
    assert np.allclose(result.values, 0.0)


def test_black_image_has_full_density() -> None:
    result = build_density_map(_solid(BLACK), GridSpec(columns=4, rows=2))
    assert np.allclose(result.values, 1.0)


def test_shape_follows_the_grid() -> None:
    result = build_density_map(_solid(GRAY), GridSpec(columns=5, rows=3))
    assert result.shape == (3, 5)
    assert result.values.shape == (3, 5)
    assert result.edges.shape == (3, 5)


def test_values_stay_in_range() -> None:
    result = build_density_map(_split(), GridSpec(columns=4, rows=2))
    assert float(result.values.min()) >= 0.0
    assert float(result.values.max()) <= 1.0


def test_dark_cells_get_higher_density() -> None:
    """左半分が黒なら、左の列だけ密度 1.00 になる。"""
    result = build_density_map(_split(), GridSpec(columns=4, rows=2))
    assert result.values[0, 0] == pytest.approx(1.0)
    assert result.values[0, 3] == pytest.approx(0.0)


def test_mean_luminance_is_the_base() -> None:
    result = build_density_map(_solid(GRAY), GridSpec(columns=2, rows=2))
    assert float(result.values[0, 0]) == pytest.approx(1.0 - 128 / 255, abs=1e-3)


def test_gamma_above_one_lowers_midtone_density() -> None:
    grid = GridSpec(columns=2, rows=2)
    plain = build_density_map(_solid(GRAY), grid)
    curved = build_density_map(_solid(GRAY), grid, DensityMethod(gamma=2.0))
    assert float(curved.values[0, 0]) < float(plain.values[0, 0])
    assert float(curved.values[0, 0]) == pytest.approx(float(plain.values[0, 0]) ** 2, abs=1e-4)


def test_gamma_keeps_the_extremes() -> None:
    result = build_density_map(_solid(BLACK), GridSpec(columns=2, rows=2), DensityMethod(gamma=3.0))
    assert np.allclose(result.values, 1.0)


def test_local_contrast_reads_variation_inside_a_cell() -> None:
    """1 セルに白黒が半々なら局所コントラストは最大。平均明度だけなら 0.5 になる。"""
    method = DensityMethod(contrast_weight=1.0)
    result = build_density_map(_split(size=(20, 20)), GridSpec(columns=1, rows=1), method)
    assert float(result.values[0, 0]) == pytest.approx(1.0, abs=1e-3)


def test_local_contrast_is_zero_on_a_flat_cell() -> None:
    method = DensityMethod(contrast_weight=1.0)
    result = build_density_map(_solid(GRAY), GridSpec(columns=2, rows=2), method)
    assert np.allclose(result.values, 0.0, atol=1e-3)


def test_edges_are_flat_on_a_uniform_image() -> None:
    result = build_density_map(_solid(GRAY), GridSpec(columns=4, rows=2))
    assert np.allclose(result.edges, 0.0, atol=1e-6)


def test_edges_rise_at_a_boundary() -> None:
    """境界のある列でエッジが立ち、離れた列では立たない。"""
    result = build_density_map(_split(size=(40, 20)), GridSpec(columns=4, rows=2))
    assert float(result.edges[0, 1]) > float(result.edges[0, 0])
    assert float(result.edges[0, 0]) == pytest.approx(0.0, abs=1e-6)


def test_edges_are_kept_even_without_weight() -> None:
    """比較材料として常に持つ（重み 0 でも作り直させない）。"""
    result = build_density_map(_split(), GridSpec(columns=4, rows=2))
    assert result.method.edge_weight == 0.0
    assert float(result.edges.max()) > 0.0


def test_edge_weight_changes_the_values() -> None:
    grid = GridSpec(columns=4, rows=2)
    plain = build_density_map(_split(), grid)
    weighted = build_density_map(_split(), grid, DensityMethod(edge_weight=0.5))
    assert not np.allclose(plain.values, weighted.values)


def test_sequence_is_reading_order() -> None:
    result = build_density_map(_split(), GridSpec(columns=4, rows=2))
    sequence = result.sequence()
    assert sequence.shape == (8,)
    assert sequence[0] == pytest.approx(float(result.values[0, 0]))
    assert sequence[4] == pytest.approx(float(result.values[1, 0]))


def test_sequence_is_a_copy() -> None:
    result = build_density_map(_solid(GRAY), GridSpec(columns=2, rows=2))
    sequence = result.sequence()
    sequence[0] = 0.0
    assert float(result.values[0, 0]) != 0.0


def test_region_is_recorded_with_the_fit() -> None:
    method = DensityMethod(fit=Fit.CONTAIN)
    result = build_density_map(_solid(GRAY, size=(40, 10)), GridSpec(columns=2, rows=2), method)
    assert result.region.fit is Fit.CONTAIN
    assert result.region.height > 10


def test_cover_ignores_the_cropped_area() -> None:
    """COVER で捨てる帯の色は密度へ入らない。"""
    image = Image.new("RGB", (20, 60), WHITE_RGB)
    for y in range(50, 60):
        for x in range(20):
            image.putpixel((x, y), BLACK)
    result = build_density_map(image, GridSpec(columns=2, rows=2), DensityMethod(fit=Fit.COVER))
    assert np.allclose(result.values, 0.0)


def test_source_image_is_not_mutated() -> None:
    source = _split()
    before = source.tobytes()
    build_density_map(source, GridSpec(columns=4, rows=2), DensityMethod(edge_weight=0.3))
    assert source.tobytes() == before


def test_same_settings_give_the_same_map() -> None:
    source = _split()
    grid = GridSpec(columns=4, rows=2)
    method = DensityMethod(gamma=1.2, contrast_weight=0.2, edge_weight=0.2)
    first = build_density_map(source, grid, method)
    second = build_density_map(source, grid, method)
    assert np.array_equal(first.values, second.values)


def test_payload_carries_method_grid_and_region() -> None:
    method = DensityMethod(gamma=1.5, contrast_weight=0.1, edge_weight=0.2)
    result = build_density_map(_split(), GridSpec(columns=4, rows=2), method)
    payload = result.to_dict()
    assert payload["method"] == {
        "base": "mean_luminance",
        "gamma": 1.5,
        "contrast_weight": 0.1,
        "edge_weight": 0.2,
        "fit": "cover",
    }
    assert payload["grid"] == {"cols": 4, "rows": 2, "cell_aspect": 1.0}
    assert payload["region"]["fit"] == "cover"


@pytest.mark.parametrize(
    "method",
    [
        DensityMethod(gamma=0.0),
        DensityMethod(gamma=20.0),
        DensityMethod(contrast_weight=-0.1),
        DensityMethod(edge_weight=1.5),
        DensityMethod(contrast_weight=0.6, edge_weight=0.6),
    ],
)
def test_invalid_method_is_rejected(method: DensityMethod) -> None:
    with pytest.raises(StageError) as excinfo:
        build_density_map(_solid(GRAY), GridSpec(columns=2, rows=2), method)
    error = excinfo.value
    assert error.stage == "density_map"
    assert error.code == "invalid_method"
    assert error.kind is ErrorKind.NEEDS_CONFIG


def test_grid_larger_than_the_image_still_produces_cells() -> None:
    """セル数が画素数を超えても止めない。面積平均ではなく補間で埋める。"""
    result = build_density_map(_solid(GRAY, size=(4, 4)), GridSpec(columns=8, rows=8))
    assert result.values.shape == (8, 8)


def test_working_memory_limit_stops_before_computing() -> None:
    limits = ImageConfig(max_working_bytes=1024)
    with pytest.raises(StageError) as excinfo:
        build_density_map(_solid(GRAY), GridSpec(columns=4, rows=2), limits=limits)
    error = excinfo.value
    assert error.code == "memory_limit"
    assert error.hint is not None
