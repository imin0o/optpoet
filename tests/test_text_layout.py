"""セル数計算と改行規則（P1-031）。"""

from __future__ import annotations

import pytest

from optpoet.errors import StageError
from optpoet.image.grid import GridSpec
from optpoet.text.layout import (
    FULL_SPACE,
    LineBreak,
    TextLayout,
    count_cells,
    layout_text,
)

GRID = GridSpec(columns=4, rows=3)


def test_counts_punctuation_and_spaces_but_not_newline() -> None:
    assert count_cells("あい、う。") == 5
    assert count_cells("あ い　う") == 5
    assert count_cells("あい\nうえ") == 4


def test_wraps_at_the_column_count() -> None:
    layout = layout_text("あいうえおか", GRID, rule=LineBreak.SIMPLE)
    assert layout.lines[:2] == ("あいうえ", "おか　　")
    assert len(layout.lines) == GRID.rows


def test_layout_always_fills_the_grid() -> None:
    layout = layout_text("あいう", GRID)
    assert len("".join(layout.lines)) == GRID.cells
    assert layout.content_cells == 3
    assert layout.filled == GRID.cells - 3


def test_newline_breaks_the_line_and_is_not_a_cell() -> None:
    layout = layout_text("あ\nい", GRID)
    assert layout.lines[0] == "あ" + FULL_SPACE * 3
    assert layout.lines[1] == "い" + FULL_SPACE * 3
    assert layout.content_cells == 2


def test_kinsoku_pushes_a_closing_char_out_of_the_line_head() -> None:
    # 素直に折ると 5 文字目の「。」が行頭へ来る。
    simple = layout_text("あいうえ。おか", GRID, rule=LineBreak.SIMPLE)
    assert simple.lines[1][0] == "。"
    kinsoku = layout_text("あいうえ。おか", GRID, rule=LineBreak.KINSOKU)
    assert kinsoku.lines[0] == "あいう" + FULL_SPACE
    assert kinsoku.lines[1] == "え。おか"


def test_kinsoku_keeps_an_opening_char_off_the_line_end() -> None:
    layout = layout_text("あいう「えお", GRID, rule=LineBreak.KINSOKU)
    assert layout.lines[0] == "あいう" + FULL_SPACE
    assert layout.lines[1] == "「えお" + FULL_SPACE


def test_kinsoku_gives_up_rather_than_emptying_a_line() -> None:
    # 行頭禁則文字だけが続く場合は列数どおりに折る（行を空にしない）。
    layout = layout_text("。。。。。。", GRID, rule=LineBreak.KINSOKU)
    assert layout.lines[0] == "。。。。"


def test_reading_order_is_left_to_right_top_to_bottom() -> None:
    layout = layout_text("あいうえおか", GRID, rule=LineBreak.SIMPLE)
    assert layout.cells[:5] == ("あ", "い", "う", "え", "お")
    assert layout.char_at(4) == "お"
    assert layout.position(4) == (1, 0)


def test_text_joins_lines_with_newline() -> None:
    layout = layout_text("あいうえおか", GRID, rule=LineBreak.SIMPLE)
    assert layout.text.split("\n") == list(layout.lines)


def test_overflow_is_rejected() -> None:
    with pytest.raises(StageError) as info:
        layout_text("あ" * (GRID.cells + 1), GRID)
    assert info.value.code == "grid_overflow"


def test_from_cells_round_trips() -> None:
    layout = layout_text("あいうえおか", GRID, rule=LineBreak.SIMPLE)
    rebuilt = TextLayout.from_cells(layout.cells, GRID, content_cells=layout.content_cells)
    assert rebuilt.lines == layout.lines


def test_from_cells_rejects_a_wrong_cell_count() -> None:
    with pytest.raises(StageError) as info:
        TextLayout.from_cells(("あ",), GRID)
    assert info.value.code == "invalid_layout"


def test_layout_dict_records_the_break_rule() -> None:
    body = layout_text("あい", GRID).to_dict()
    assert body["line_break"] == "kinsoku"
    assert body["reading_order"] == "horizontal_lr_tb"
    assert body["content_cells"] == 2
