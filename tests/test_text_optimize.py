"""表記候補による局所探索とトレース（P1-035 / P1-036 / P1-037）。"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from optpoet.errors import StageCancelledError, StageError
from optpoet.font.charset import CharsetSpec, build_charset
from optpoet.font.dictionary import DensityDictionary, build_dictionary
from optpoet.font.profile import load_font_profile
from optpoet.font.render import RenderSettings
from optpoet.image.density import DensityMap
from optpoet.image.grid import GridSpec, plan_region
from optpoet.pipeline.cancel import CancelToken
from optpoet.pipeline.progress import StageProgress
from optpoet.storage import Stage
from optpoet.text.evaluate import density_table, evaluate_layout
from optpoet.text.layout import layout_text
from optpoet.text.optimize import (
    STOPPED_CONVERGED,
    STOPPED_MAX_ITERATIONS,
    OptimizeSettings,
    optimize_layout,
)
from optpoet.text.trace import OptimizationTrace, TraceEntry
from optpoet.text.variants import VariantTable, default_variants

SETTINGS = RenderSettings(pixel_size=20, cell_width=24, cell_height=24)
SPEC = CharsetSpec(
    name="test",
    version="1.0",
    ranges=((0x3041, 0x3096), (0x30A1, 0x30F6)),
    extra="、，。．ー― 　",
)
GRID = GridSpec(columns=4, rows=3)
TEXT = "あいうえおかきくけこさし"


@pytest.fixture(scope="module")
def dictionary(font_file: Path) -> DensityDictionary:
    return build_dictionary(load_font_profile(font_file), build_charset(SPEC), SETTINGS, levels=8)


def _density_map(values: list[float]) -> DensityMap:
    array = np.asarray(values, dtype=np.float32).reshape(GRID.rows, GRID.columns)
    return DensityMap(
        values=array,
        edges=np.zeros_like(array),
        grid=GRID,
        region=plan_region((GRID.columns, GRID.rows), GRID),
    )


def _katakana_target(dictionary: DensityDictionary) -> DensityMap:
    """本文をすべてカタカナへ置換したときの密度を目標にする。"""
    table = density_table(dictionary)
    return _density_map([table[chr(ord(char) + 0x60)] for char in TEXT])


def test_default_variants_swap_kana_and_punctuation() -> None:
    table = default_variants()
    assert table.candidates("あ") == ("ア",)
    assert table.candidates("ア") == ("あ",)
    assert table.candidates("、") == ("，",)
    assert table.candidates("　") == (" ",)


def test_variants_are_restricted_to_the_dictionary(dictionary: DensityDictionary) -> None:
    limited = default_variants().restricted(frozenset(dictionary.chars))
    assert all(item in dictionary.chars for items in limited.mapping.values() for item in items)


def test_optimization_reduces_the_error(dictionary: DensityDictionary) -> None:
    density_map = _katakana_target(dictionary)
    layout = layout_text(TEXT, GRID)
    result = optimize_layout(layout, density_map, dictionary)
    assert result.final.mae < result.initial.mae
    assert result.improvement > 0.0
    assert result.improvement_rate > 0.0
    # 到達点はカタカナ表記。読みは変わらない。
    assert result.layout.cells[0] == "ア"


def test_optimization_keeps_the_cell_count(dictionary: DensityDictionary) -> None:
    result = optimize_layout(layout_text(TEXT, GRID), _katakana_target(dictionary), dictionary)
    assert len(result.layout.cells) == GRID.cells
    assert result.layout.content_cells == len(TEXT)


def test_no_improvement_stops_immediately(dictionary: DensityDictionary) -> None:
    density_map = _katakana_target(dictionary)
    layout = layout_text(TEXT, GRID)
    optimized = optimize_layout(layout, density_map, dictionary).layout
    again = optimize_layout(optimized, density_map, dictionary)
    assert again.iterations == 1
    assert again.accepted == 0
    assert again.stopped == STOPPED_CONVERGED


def test_iteration_cap_is_respected(dictionary: DensityDictionary) -> None:
    result = optimize_layout(
        layout_text(TEXT, GRID),
        _katakana_target(dictionary),
        dictionary,
        settings=OptimizeSettings(max_iterations=1, min_improvement=0.0),
    )
    assert result.iterations == 1
    assert result.stopped == STOPPED_MAX_ITERATIONS


def test_worse_candidates_are_not_accepted(dictionary: DensityDictionary) -> None:
    table = density_table(dictionary)
    # 現状の表記がそのまま最適な目標を与える。
    density_map = _density_map([table[char] for char in TEXT])
    layout = layout_text(TEXT, GRID)
    result = optimize_layout(layout, density_map, dictionary)
    assert result.accepted == 0
    assert result.layout.cells == layout.cells


def test_empty_variant_table_changes_nothing(dictionary: DensityDictionary) -> None:
    result = optimize_layout(
        layout_text(TEXT, GRID),
        _katakana_target(dictionary),
        dictionary,
        variants=VariantTable(mapping={}),
    )
    assert result.accepted == 0
    assert result.trace.evaluated == 0


@pytest.mark.parametrize(
    "settings",
    [
        OptimizeSettings(max_iterations=0),
        OptimizeSettings(min_improvement=-0.5),
        OptimizeSettings(max_trace_entries=-1),
    ],
)
def test_invalid_settings_are_rejected(
    dictionary: DensityDictionary, settings: OptimizeSettings
) -> None:
    with pytest.raises(StageError) as info:
        optimize_layout(
            layout_text(TEXT, GRID),
            _katakana_target(dictionary),
            dictionary,
            settings=settings,
        )
    assert info.value.code == "invalid_settings"


def test_cancel_stops_the_search(dictionary: DensityDictionary) -> None:
    token = CancelToken()
    token.cancel()
    progress = StageProgress(str(Stage.OPTIMIZE), total=GRID.cells, cancel=token)
    with pytest.raises(StageCancelledError):
        optimize_layout(
            layout_text(TEXT, GRID),
            _katakana_target(dictionary),
            dictionary,
            progress=progress,
        )


def test_trace_records_candidates_and_verdicts(dictionary: DensityDictionary) -> None:
    result = optimize_layout(layout_text(TEXT, GRID), _katakana_target(dictionary), dictionary)
    assert result.trace.evaluated > 0
    assert result.trace.accepted == result.accepted
    entry = next(item for item in result.trace.entries if item.accepted)
    assert entry.error_after < entry.error_before
    assert entry.gain > 0.0
    body = result.trace.to_dict()
    assert body["params"]["dictionary_id"] == dictionary.dictionary_id
    assert body["params"]["algorithm"]["name"] == "local_search"
    assert len(body["entries"]) == result.trace.evaluated


def test_trace_marks_truncation_without_losing_the_count() -> None:
    trace = OptimizationTrace(max_entries=1)
    for index in range(3):
        trace.record(
            TraceEntry(
                iteration=1,
                index=index,
                char="あ",
                candidate="ア",
                error_before=0.5,
                error_after=0.4,
                accepted=True,
            )
        )
    assert trace.evaluated == 3
    assert len(trace.entries) == 1
    assert trace.truncated


def test_trace_bytes_are_stable(dictionary: DensityDictionary) -> None:
    density_map = _katakana_target(dictionary)
    first = optimize_layout(layout_text(TEXT, GRID), density_map, dictionary).trace
    second = optimize_layout(layout_text(TEXT, GRID), density_map, dictionary).trace
    assert first.to_bytes() == second.to_bytes()
    assert first.cache_key() == second.cache_key()


def test_result_dict_carries_the_algorithm_and_metrics(dictionary: DensityDictionary) -> None:
    result = optimize_layout(layout_text(TEXT, GRID), _katakana_target(dictionary), dictionary)
    body = result.to_dict()
    assert body["algorithm"] == {"name": "local_search", "version": "1.0"}
    assert body["mae_final"] <= body["mae_initial"]
    assert body["stopped"] in {STOPPED_CONVERGED, STOPPED_MAX_ITERATIONS}


def test_optimized_layout_evaluates_to_the_reported_error(dictionary: DensityDictionary) -> None:
    density_map = _katakana_target(dictionary)
    result = optimize_layout(layout_text(TEXT, GRID), density_map, dictionary)
    recomputed = evaluate_layout(result.layout, density_map, dictionary)
    assert recomputed.mae == pytest.approx(result.final.mae)
