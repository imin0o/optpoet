"""文字数とセル数の突合と調整候補（P1-032）。"""

from __future__ import annotations

import pytest

from optpoet.errors import StageError
from optpoet.image.grid import GridSpec
from optpoet.text.fit import (
    KIND_ADD_CHARS,
    KIND_PAD_WITH_SPACE,
    KIND_REMOVE_CHARS,
    KIND_RESIZE_ROWS,
    check_fit,
    require_fit,
)

GRID = GridSpec(columns=4, rows=3)


def test_exact_match_needs_no_adjustment() -> None:
    report = check_fit("あ" * 12, GRID)
    assert report.ok
    assert report.delta == 0
    assert report.adjustments == ()


def test_newline_is_not_counted() -> None:
    assert check_fit("あ" * 6 + "\n" + "い" * 6, GRID).ok


def test_shortage_offers_adding_or_padding() -> None:
    report = check_fit("あ" * 10, GRID)
    assert report.delta == -2
    kinds = [item.kind for item in report.adjustments]
    assert kinds[:2] == [KIND_ADD_CHARS, KIND_PAD_WITH_SPACE]
    assert report.adjustments[0].amount == 2


def test_excess_offers_removing_but_never_truncates() -> None:
    text = "あ" * 15
    report = check_fit(text, GRID)
    assert report.delta == 3
    assert report.adjustments[0].kind == KIND_REMOVE_CHARS
    # 本文は触らない（暗黙削除の禁止）。
    assert len(text) == 15


def test_grid_candidates_are_offered() -> None:
    report = check_fit("あ" * 20, GRID)
    kinds = {item.kind for item in report.adjustments}
    assert KIND_RESIZE_ROWS in kinds
    rows = next(item for item in report.adjustments if item.kind == KIND_RESIZE_ROWS)
    assert rows.amount == 5


def test_require_fit_fails_with_the_candidates_in_the_hint() -> None:
    with pytest.raises(StageError) as info:
        require_fit("あ" * 10, GRID)
    assert info.value.code == "cell_count_mismatch"
    assert info.value.hint is not None
    assert "足す" in info.value.hint


def test_report_matches_the_cell_check_block() -> None:
    body = check_fit("あ" * 10, GRID).to_dict()
    assert body["expected_cells"] == 12
    assert body["displayed_chars"] == 10
    assert body["result"] == "mismatch"
