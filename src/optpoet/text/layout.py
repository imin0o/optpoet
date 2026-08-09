"""セル数計算と改行規則（P1-031 / FR-07 / FR-10）。

セルの数え方（FR-10）:

- 表示文字、句読点、全角・半角空白は各 1 セル。
- 改行はセルに数えない。段落の区切りとして扱い、そこで行を変える。

読み順は横書き（左→右、上→下）固定（FR-07）。`TextLayout.cells` の並びは密度列
（`DensityMap.sequence()`）と同じ順序で、位置ごとの誤差計算（P1-033）が添字だけで済む。

**改行規則**は 2 つ。

- `SIMPLE`: 列数で機械的に折り返す。
- `KINSOKU`: 行頭・行末の禁則文字を追い出しで避ける。切り位置を最大 `MAX_PUSH_OUT` 文字
  まで手前へ戻し、それでも解けない場合は諦めて機械的に折り返す（行を空にしない）。

追い出しと段落末で生じる余白は `fill`（既定は全角空白）で埋める。埋めた分もセルを占める
ため、`TextLayout` は常に `grid.cells` 個の文字を持つ。本文が占めたセル数は
`content_cells`、余白は `filled` で分けて数える。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from optpoet.errors import StageError
from optpoet.image.grid import GridSpec
from optpoet.storage import Stage
from optpoet.text.normalize import NEWLINE

FULL_SPACE = "　"
HALF_SPACE = " "

NO_LINE_START = frozenset(
    "、。，．・：；！？」』）〉》〕】ー―…‥ゝゞヽヾぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ"
)
"""行頭に置かない文字（JIS X 4051 の行頭禁則に相当する範囲）。"""

NO_LINE_END = frozenset("「『（〈《〔【")
"""行末に置かない文字。"""

MAX_PUSH_OUT = 4
"""禁則で切り位置を手前へ戻せる最大文字数。"""

_STAGE = str(Stage.TEXT)


class LineBreak(StrEnum):
    """改行規則。manifest へは文字列のまま記録する。"""

    SIMPLE = "simple"
    KINSOKU = "kinsoku"


def count_cells(text: str) -> int:
    """本文が占めるセル数。改行は数えない（FR-10）。"""
    return sum(1 for char in text if char != NEWLINE)


@dataclass(frozen=True, slots=True)
class TextLayout:
    """グリッドへ配置し終えた文字。行数・列数はグリッドと必ず一致する。"""

    lines: tuple[str, ...]
    grid: GridSpec
    content_cells: int
    rule: LineBreak = LineBreak.SIMPLE
    fill: str = FULL_SPACE

    def __post_init__(self) -> None:
        if len(self.lines) != self.grid.rows:
            raise _invalid_layout(
                f"行数がグリッドと一致しない: {len(self.lines)} != {self.grid.rows}"
            )
        for row, line in enumerate(self.lines):
            if len(line) != self.grid.columns:
                raise _invalid_layout(
                    f"{row + 1} 行目の文字数がグリッドと一致しない: "
                    f"{len(line)} != {self.grid.columns}"
                )

    @classmethod
    def from_cells(
        cls,
        cells: tuple[str, ...],
        grid: GridSpec,
        *,
        content_cells: int | None = None,
        rule: LineBreak = LineBreak.SIMPLE,
        fill: str = FULL_SPACE,
    ) -> TextLayout:
        """読み順のセル列から作る。密度優先の配置（P1-034）と最適化結果で使う。"""
        if len(cells) != grid.cells:
            raise _invalid_layout(f"セル数がグリッドと一致しない: {len(cells)} != {grid.cells}")
        lines = tuple(
            "".join(cells[row * grid.columns : (row + 1) * grid.columns])
            for row in range(grid.rows)
        )
        return cls(
            lines=lines,
            grid=grid,
            content_cells=grid.cells if content_cells is None else content_cells,
            rule=rule,
            fill=fill,
        )

    @property
    def cells(self) -> tuple[str, ...]:
        """読み順に並べたセル列。密度列と同じ並び。"""
        return tuple("".join(self.lines))

    @property
    def text(self) -> str:
        """TXT 出力の元。行を改行で区切る（改行はセルに数えない）。"""
        return NEWLINE.join(self.lines)

    @property
    def filled(self) -> int:
        """余白として埋めたセル数。"""
        return self.grid.cells - self.content_cells

    def position(self, index: int) -> tuple[int, int]:
        """読み順の添字を (行, 列) へ変換する。いずれも 0 起点。"""
        if not 0 <= index < self.grid.cells:
            raise _invalid_layout(f"セル位置が範囲外: {index}")
        return divmod(index, self.grid.columns)

    def char_at(self, index: int) -> str:
        row, column = self.position(index)
        return self.lines[row][column]

    def to_dict(self) -> dict[str, Any]:
        """manifest の `grid` / `text` と突合できる形。本文そのものは実体側に持つ。"""
        return {
            "line_break": str(self.rule),
            "fill": self.fill,
            "reading_order": "horizontal_lr_tb",
            "normalization_form": "NFC",
            "grid": self.grid.to_dict(),
            "content_cells": self.content_cells,
            "filled_cells": self.filled,
        }


def layout_text(
    text: str,
    grid: GridSpec,
    *,
    rule: LineBreak = LineBreak.KINSOKU,
    fill: str = FULL_SPACE,
) -> TextLayout:
    """正規化済みの本文をグリッドへ配置する。`text` は許可文字検査を通した文字列。"""
    grid.validate()
    if len(fill) != 1:
        raise _invalid_layout(f"fill は 1 文字: {fill!r}")

    lines: list[str] = []
    for paragraph in text.split(NEWLINE):
        lines.extend(_wrap(paragraph, grid.columns, rule))
    if len(lines) > grid.rows:
        raise _overflow(len(lines), grid)

    padded = [line.ljust(grid.columns, fill) for line in lines]
    padded.extend(fill * grid.columns for _ in range(grid.rows - len(lines)))
    return TextLayout(
        lines=tuple(padded),
        grid=grid,
        content_cells=count_cells(text),
        rule=rule,
        fill=fill,
    )


def _wrap(paragraph: str, columns: int, rule: LineBreak) -> list[str]:
    """1 段落を列数で折り返す。空段落は空行 1 つになる。"""
    if not paragraph:
        return [""]
    lines: list[str] = []
    rest = paragraph
    while len(rest) > columns:
        cut = _kinsoku_cut(rest, columns) if rule is LineBreak.KINSOKU else columns
        lines.append(rest[:cut])
        rest = rest[cut:]
    lines.append(rest)
    return lines


def _kinsoku_cut(text: str, columns: int) -> int:
    """禁則を満たす切り位置を返す。手前へ戻せない場合は列数のまま切る。"""
    limit = max(1, columns - MAX_PUSH_OUT)
    cut = columns
    while cut > limit and (text[cut] in NO_LINE_START or text[cut - 1] in NO_LINE_END):
        cut -= 1
    # 戻し切れなかった場合は禁則を諦める。行を空にする方が読み順を壊す。
    if text[cut] in NO_LINE_START or text[cut - 1] in NO_LINE_END:
        return columns
    return cut


def _overflow(lines: int, grid: GridSpec) -> StageError:
    return StageError(
        _STAGE,
        "grid_overflow",
        f"本文の行数がグリッドの行数を超えた: {lines} 行 > {grid.rows} 行",
        hint="本文を減らすか、グリッドの行数・列数を増やす（調整候補は fit.check_fit）。",
    )


def _invalid_layout(message: str) -> StageError:
    return StageError(
        _STAGE,
        "invalid_layout",
        message,
        hint="グリッド寸法と本文の文字数を見直す。",
    )
