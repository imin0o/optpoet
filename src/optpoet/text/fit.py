"""文字数とセル数の不足・超過と、その調整候補（P1-032 / FR-10）。

FR-10 は「最終表示文字数はセル数と一致させる」と定める。一致しない場合に本文を黙って
切り詰めたり空白で埋めたりすると、作者の文章が知らないうちに変わる。そこで本モジュールは
**判定と候補提示だけ**を行い、実際の増減はしない。暗黙削除を禁止する（P1-032）。

候補は 3 方向で出す。

- 本文側: 何セル分足す／削る必要があるか。
- 余白側: 不足分を空白セルで埋める（作者が明示した場合のみ）。
- グリッド側: 列数か行数を変えて必要セル数を本文へ寄せる。

グリッド候補は `cell_aspect` を保ったまま寸法だけを変える。実際に採るかは作者が決める。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from optpoet.errors import StageError
from optpoet.image.grid import GridSpec
from optpoet.storage import Stage
from optpoet.text.layout import count_cells

KIND_ADD_CHARS = "add_chars"
KIND_REMOVE_CHARS = "remove_chars"
KIND_PAD_WITH_SPACE = "pad_with_space"
KIND_RESIZE_ROWS = "resize_rows"
KIND_RESIZE_COLUMNS = "resize_columns"

_STAGE = str(Stage.TEXT)


@dataclass(frozen=True, slots=True)
class Adjustment:
    """1 つの調整候補。`amount` の単位は候補の種別で決まる（文字数またはセル数）。"""

    kind: str
    amount: int
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "amount": self.amount, "message": self.message}


@dataclass(frozen=True, slots=True)
class FitReport:
    """本文のセル数とグリッドのセル数の突合結果。"""

    required: int
    actual: int
    adjustments: tuple[Adjustment, ...]

    @property
    def delta(self) -> int:
        """本文が超過なら正、不足なら負。"""
        return self.actual - self.required

    @property
    def ok(self) -> bool:
        return self.delta == 0

    def to_dict(self) -> dict[str, Any]:
        """manifest の `evaluation.cell_check` へ入れられる形。"""
        return {
            "expected_cells": self.required,
            "displayed_chars": self.actual,
            "result": "ok" if self.ok else "mismatch",
            "adjustments": [item.to_dict() for item in self.adjustments],
        }


def check_fit(text: str, grid: GridSpec) -> FitReport:
    """本文のセル数とグリッドのセル数を突き合わせ、差と調整候補を返す。

    `text` は正規化済みの本文。改行はセルに数えない。差があっても失敗にはしない。
    """
    grid.validate()
    required = grid.cells
    actual = count_cells(text)
    delta = actual - required
    if delta == 0:
        return FitReport(required=required, actual=actual, adjustments=())
    return FitReport(
        required=required,
        actual=actual,
        adjustments=_adjustments(delta, actual, grid),
    )


def require_fit(text: str, grid: GridSpec) -> FitReport:
    """一致していれば結果を返し、していなければ候補付きで失敗にする。

    暗黙に切り詰めない。呼出側は候補を作者へ提示してから本文かグリッドを直す。
    """
    report = check_fit(text, grid)
    if not report.ok:
        raise _mismatch(report)
    return report


def _adjustments(delta: int, actual: int, grid: GridSpec) -> tuple[Adjustment, ...]:
    shortage = -delta
    items: list[Adjustment] = []
    if delta > 0:
        items.append(Adjustment(KIND_REMOVE_CHARS, delta, f"本文を {delta} 文字（セル）減らす"))
    else:
        items.append(Adjustment(KIND_ADD_CHARS, shortage, f"本文を {shortage} 文字（セル）足す"))
        items.append(
            Adjustment(
                KIND_PAD_WITH_SPACE,
                shortage,
                f"不足 {shortage} セルを空白で埋める（明示指定が必要）",
            )
        )
    items.extend(_grid_adjustments(actual, grid))
    return tuple(items)


def _grid_adjustments(actual: int, grid: GridSpec) -> list[Adjustment]:
    """本文の文字数に近づくグリッド寸法の候補。0 以下や現状と同じ寸法は出さない。"""
    items: list[Adjustment] = []
    rows = max(1, round(actual / grid.columns))
    if rows != grid.rows:
        items.append(
            Adjustment(
                KIND_RESIZE_ROWS,
                rows,
                f"行数を {grid.rows} から {rows} にする（{grid.columns * rows} セル）",
            )
        )
    columns = max(1, round(actual / grid.rows))
    if columns != grid.columns:
        items.append(
            Adjustment(
                KIND_RESIZE_COLUMNS,
                columns,
                f"列数を {grid.columns} から {columns} にする（{columns * grid.rows} セル）",
            )
        )
    return items


def _mismatch(report: FitReport) -> StageError:
    direction = "超過" if report.delta > 0 else "不足"
    return StageError(
        _STAGE,
        "cell_count_mismatch",
        (
            f"本文のセル数がグリッドと一致しない（{direction} {abs(report.delta)}）: "
            f"{report.actual} != {report.required}"
        ),
        hint="／".join(item.message for item in report.adjustments),
    )
