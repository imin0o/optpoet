"""位置ごとの密度誤差（P1-033）と基準配置（P1-034）。MAE は AC-03 の判定値
（evaluation-metrics.md 3.1）。"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from optpoet.errors import StageError
from optpoet.font.charset import CharsetSpec, build_charset
from optpoet.font.dictionary import DensityDictionary, build_dictionary
from optpoet.font.profile import load_font_profile
from optpoet.font.render import RenderSettings
from optpoet.image.density import DensityMap
from optpoet.image.grid import GridSpec, plan_region
from optpoet.text.baseline import build_baseline
from optpoet.text.evaluate import (
    density_table,
    evaluate_layout,
    normalized_density,
)
from optpoet.text.layout import layout_text

SETTINGS = RenderSettings(pixel_size=20, cell_width=24, cell_height=24)
SPEC = CharsetSpec(name="test", version="1.0", ranges=((0x3041, 0x3096),), extra="鬱永光の 　")
GRID = GridSpec(columns=4, rows=3)


@pytest.fixture(scope="module")
def dictionary(font_file: Path) -> DensityDictionary:
    return build_dictionary(load_font_profile(font_file), build_charset(SPEC), SETTINGS, levels=8)


def _density_map(values: list[float], grid: GridSpec = GRID) -> DensityMap:
    array = np.asarray(values, dtype=np.float32).reshape(grid.rows, grid.columns)
    return DensityMap(
        values=array,
        edges=np.zeros_like(array),
        grid=grid,
        region=plan_region((grid.columns, grid.rows), grid),
    )


def test_density_table_spans_zero_to_one(dictionary: DensityDictionary) -> None:
    table = density_table(dictionary)
    values = list(table.values())
    assert min(values) == pytest.approx(0.0)
    assert max(values) == pytest.approx(1.0)
    assert table["鬱"] > table["の"]


def test_normalized_density_rejects_unknown_chars(dictionary: DensityDictionary) -> None:
    with pytest.raises(StageError) as info:
        normalized_density(dictionary, "漢")
    assert info.value.code == "unknown_char"


def test_error_is_signed_per_position(dictionary: DensityDictionary) -> None:
    layout = layout_text("鬱" * 12, GRID)
    result = evaluate_layout(layout, _density_map([0.0] * 12), dictionary)
    # 目標が真っ白なのに最も濃い文字を置いたので、全位置で正の誤差になる。
    assert float(result.errors.min()) > 0.0
    assert result.mae == pytest.approx(1.0, abs=1e-5)


def test_metrics_are_zero_for_a_perfect_match(dictionary: DensityDictionary) -> None:
    table = density_table(dictionary)
    layout = layout_text("鬱" * 12, GRID)
    result = evaluate_layout(layout, _density_map([table["鬱"]] * 12), dictionary)
    assert result.mae == pytest.approx(0.0, abs=1e-6)
    assert result.rmse == pytest.approx(0.0, abs=1e-6)


def test_worst_positions_come_first(dictionary: DensityDictionary) -> None:
    layout = layout_text("鬱" * 12, GRID)
    targets = [0.0] * 12
    targets[5] = 1.0
    result = evaluate_layout(layout, _density_map(targets), dictionary)
    assert result.worst_indices(1) == (0,)
    assert result.worst_indices()[-1] == 5


def test_grid_mismatch_is_rejected(dictionary: DensityDictionary) -> None:
    layout = layout_text("あ" * 12, GRID)
    other = GridSpec(columns=3, rows=4)
    with pytest.raises(StageError) as info:
        evaluate_layout(layout, _density_map([0.0] * 12, other), dictionary)
    assert info.value.code == "grid_mismatch"


def test_baseline_beats_a_uniform_placement(dictionary: DensityDictionary) -> None:
    targets = [index / 11 for index in range(12)]
    density_map = _density_map(targets)
    baseline = build_baseline(density_map, dictionary)
    uniform = layout_text("あ" * 12, GRID)
    assert (
        evaluate_layout(baseline, density_map, dictionary).mae
        < evaluate_layout(uniform, density_map, dictionary).mae
    )


def test_baseline_is_deterministic(dictionary: DensityDictionary) -> None:
    density_map = _density_map([index / 11 for index in range(12)])
    first = build_baseline(density_map, dictionary)
    second = build_baseline(density_map, dictionary)
    assert first.lines == second.lines


def test_baseline_picks_the_extremes(dictionary: DensityDictionary) -> None:
    table = density_table(dictionary)
    lightest = min(table, key=lambda char: (table[char], ord(char)))
    heaviest = max(table, key=lambda char: (table[char], -ord(char)))
    layout = build_baseline(_density_map([0.0] * 6 + [1.0] * 6), dictionary)
    assert layout.cells[0] == lightest
    assert layout.cells[-1] == heaviest
