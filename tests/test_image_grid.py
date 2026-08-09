"""グリッド寸法と実測セル比からの縮小領域計算の検証（P1-013 / FR-02）。"""

from __future__ import annotations

import math

import pytest
from PIL import Image

from optpoet.config import GridConfig
from optpoet.errors import ErrorKind, StageError
from optpoet.image import Fit, GridSpec, ReduceRegion, extract_region, plan_region


def _image(width: int, height: int, color: tuple[int, int, int] = (10, 10, 10)) -> Image.Image:
    return Image.new("RGB", (width, height), color)


def test_square_cells_give_grid_aspect_from_cell_counts() -> None:
    grid = GridSpec(columns=60, rows=40)
    assert grid.cells == 2400
    assert grid.aspect == pytest.approx(1.5)


def test_cell_aspect_stretches_the_grid_aspect() -> None:
    """セルが縦長（比 0.5）なら、同じセル数でもグリッドは横に狭くなる。"""
    grid = GridSpec(columns=60, rows=40, cell_aspect=0.5)
    assert grid.aspect == pytest.approx(0.75)


def test_from_cell_size_measures_the_ratio() -> None:
    grid = GridSpec.from_cell_size(10, 5, cell_width=24, cell_height=48)
    assert grid.cell_aspect == pytest.approx(0.5)


def test_from_config_takes_cell_counts() -> None:
    grid = GridSpec.from_config(GridConfig(columns=8, rows=4), cell_aspect=0.5)
    assert (grid.columns, grid.rows, grid.cell_aspect) == (8, 4, 0.5)


def test_cover_crops_the_wider_side() -> None:
    """画像が横長すぎる場合、高さを残して左右を捨てる。"""
    region = plan_region((400, 100), GridSpec(columns=2, rows=1), Fit.COVER)
    assert (region.width, region.height) == (200, 100)
    assert (region.x, region.y) == (100, 0)


def test_cover_crops_the_taller_side() -> None:
    region = plan_region((100, 400), GridSpec(columns=2, rows=1), Fit.COVER)
    assert (region.width, region.height) == (100, 50)
    assert (region.x, region.y) == (0, 175)


def test_cover_region_stays_inside_the_image() -> None:
    region = plan_region((400, 100), GridSpec(columns=3, rows=2), Fit.COVER)
    assert not region.padded_against((400, 100))


def test_contain_expands_beyond_the_image() -> None:
    """画像全体を残すため、足りない側は画像外へ広げる（後で背景色が入る）。"""
    region = plan_region((400, 100), GridSpec(columns=1, rows=1), Fit.CONTAIN)
    assert (region.width, region.height) == (400, 400)
    assert region.y == -150
    assert region.padded_against((400, 100))


def test_stretch_uses_the_whole_image() -> None:
    region = plan_region((400, 100), GridSpec(columns=1, rows=1), Fit.STRETCH)
    assert (region.x, region.y, region.width, region.height) == (0, 0, 400, 100)


def test_matching_aspect_keeps_the_whole_image_in_every_fit() -> None:
    grid = GridSpec(columns=4, rows=2)
    for fit in Fit:
        region = plan_region((200, 100), grid, fit)
        assert (region.x, region.y, region.width, region.height) == (0, 0, 200, 100)


def test_region_aspect_follows_cell_aspect() -> None:
    """セル比を変えると、同じセル数でも切り出す矩形の形が変わる。"""
    grid = GridSpec(columns=4, rows=4, cell_aspect=0.5)
    region = plan_region((400, 400), grid, Fit.COVER)
    assert region.width / region.height == pytest.approx(grid.aspect)


def test_region_carries_target_cell_counts() -> None:
    region = plan_region((100, 100), GridSpec(columns=7, rows=3), Fit.COVER)
    assert (region.columns, region.rows) == (7, 3)
    assert region.pixels == region.width * region.height


def test_region_payload_is_serializable() -> None:
    region = plan_region((100, 50), GridSpec(columns=4, rows=2), Fit.COVER)
    assert region.to_dict() == {
        "x": 0,
        "y": 0,
        "width": 100,
        "height": 50,
        "columns": 4,
        "rows": 2,
        "fit": "cover",
    }


def test_grid_payload_matches_manifest_keys() -> None:
    assert GridSpec(columns=60, rows=40, cell_aspect=0.5).to_dict() == {
        "cols": 60,
        "rows": 40,
        "cell_aspect": 0.5,
    }


@pytest.mark.parametrize(
    "grid",
    [
        GridSpec(columns=0, rows=4),
        GridSpec(columns=4, rows=0),
        GridSpec(columns=4, rows=4, cell_aspect=0.0),
        GridSpec(columns=4, rows=4, cell_aspect=-1.0),
        GridSpec(columns=4, rows=4, cell_aspect=math.nan),
    ],
)
def test_invalid_grid_is_rejected(grid: GridSpec) -> None:
    with pytest.raises(StageError) as excinfo:
        plan_region((100, 100), grid, Fit.COVER)
    error = excinfo.value
    assert error.stage == "density_map"
    assert error.code == "invalid_grid"
    assert error.kind is ErrorKind.NEEDS_CONFIG


def test_invalid_cell_size_is_rejected() -> None:
    with pytest.raises(StageError) as excinfo:
        GridSpec.from_cell_size(4, 4, cell_width=0, cell_height=10)
    assert excinfo.value.code == "invalid_grid"


def test_extract_region_cuts_the_rectangle() -> None:
    source = _image(10, 10)
    source.putpixel((5, 5), (255, 0, 0))
    region = ReduceRegion(x=4, y=4, width=4, height=4, columns=2, rows=2, fit=Fit.COVER)
    cut = extract_region(source, region)
    assert cut.size == (4, 4)
    assert cut.getpixel((1, 1)) == (255, 0, 0)


def test_extract_region_pads_with_background() -> None:
    """はみ出した分は黒ではなく背景色で埋める。"""
    region = ReduceRegion(x=-2, y=0, width=8, height=4, columns=2, rows=1, fit=Fit.CONTAIN)
    cut = extract_region(_image(4, 4), region, background=(0, 255, 0))
    assert cut.size == (8, 4)
    assert cut.getpixel((0, 0)) == (0, 255, 0)
    assert cut.getpixel((2, 0)) == (10, 10, 10)


def test_extract_region_does_not_mutate_the_source() -> None:
    source = _image(10, 10)
    before = source.tobytes()
    region = plan_region(source.size, GridSpec(columns=4, rows=1), Fit.CONTAIN)
    extract_region(source, region)
    assert source.tobytes() == before
