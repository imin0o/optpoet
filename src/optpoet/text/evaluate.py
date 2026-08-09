"""位置ごとの目標密度と文字密度の誤差（P1-033 / FR-09）。

密度マップの値は 0.00（白）〜1.00（黒）で全域を使う。一方、文字の黒画素率は実測で概ね
0.04〜0.13 に集まる（pixel-identity-spike.md）。そのまま引き算すると、どの文字を選んでも
暗部で大きな誤差が残り、最適化の勾配が消える。

そこで文字側を辞書内の最小〜最大で正規化してから比べる（`density_table`）。辞書は
`min_ratio` / `max_ratio` を持つので、この写像は辞書が決まれば一意に定まる。

誤差は符号付き（文字密度 − 目標密度）で持つ。位置ごとの符号は「濃すぎる／薄すぎる」を
そのまま示し、比較表示（P1-044）とヒートマップで使える。集計は MAE を主指標にする
（AC-03 / docs/environment/evaluation-metrics.md）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from optpoet.errors import StageError
from optpoet.font.dictionary import DensityDictionary
from optpoet.image.density import DensityMap
from optpoet.storage import Stage
from optpoet.text.layout import TextLayout

_STAGE = str(Stage.OPTIMIZE)

Array = NDArray[np.float32]


@dataclass(frozen=True, slots=True)
class CellError:
    """1 セル分の誤差。比較表示と最適化トレースの提示に使う。"""

    index: int
    row: int
    column: int
    char: str
    target: float
    actual: float

    @property
    def error(self) -> float:
        return self.actual - self.target

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "row": self.row,
            "column": self.column,
            "char": self.char,
            "target": self.target,
            "actual": self.actual,
            "error": self.error,
        }


@dataclass(frozen=True, slots=True, eq=False)
class DensityError:
    """配置全体の密度誤差。`errors` は形状 (rows, columns) の符号付き誤差。"""

    errors: Array
    layout: TextLayout

    @property
    def mae(self) -> float:
        return float(np.abs(self.errors).mean())

    @property
    def rmse(self) -> float:
        return float(np.sqrt(np.square(self.errors, dtype=np.float32).mean()))

    @property
    def max_error(self) -> float:
        return float(np.abs(self.errors).max())

    def worst_indices(self, count: int | None = None) -> tuple[int, ...]:
        """誤差の大きい順のセル位置。同値なら読み順の早い方を先にする。"""
        flat = np.abs(self.errors).reshape(-1)
        order = np.argsort(-flat, kind="stable")
        limit = len(order) if count is None else min(count, len(order))
        return tuple(int(index) for index in order[:limit])

    def worst(self, count: int = 10, *, targets: Array | None = None) -> tuple[CellError, ...]:
        """誤差の大きいセルを詳細付きで返す。"""
        flat_errors = self.errors.reshape(-1)
        flat_targets = targets.reshape(-1) if targets is not None else None
        cells = self.layout.cells
        result: list[CellError] = []
        for index in self.worst_indices(count):
            row, column = self.layout.position(index)
            error = float(flat_errors[index])
            target = float(flat_targets[index]) if flat_targets is not None else 0.0
            result.append(
                CellError(
                    index=index,
                    row=row,
                    column=column,
                    char=cells[index],
                    target=target,
                    actual=target + error,
                )
            )
        return tuple(result)

    def to_dict(self) -> dict[str, Any]:
        """manifest の `evaluation.metrics` へ入れる集計値。"""
        return {"mae": self.mae, "rmse": self.rmse, "max_error": self.max_error}


def density_table(dictionary: DensityDictionary) -> dict[str, float]:
    """文字 → 密度マップと同じ 0.0〜1.0 の値。辞書内の最小〜最大で正規化する。"""
    low = dictionary.min_ratio
    span = dictionary.max_ratio - low
    if span <= 0.0:
        # 全文字が同じ黒画素率になるのは 1 文字だけの辞書など。写像は定数にする。
        return dict.fromkeys(dictionary.chars, 0.0)
    return {
        char: (ratio - low) / span
        for char, ratio in zip(dictionary.chars, dictionary.ratios, strict=True)
    }


def normalized_density(dictionary: DensityDictionary, char: str) -> float:
    """1 文字の正規化密度。辞書に無い文字は暗黙に 0 とせず失敗にする。"""
    low = dictionary.min_ratio
    span = dictionary.max_ratio - low
    ratio = dictionary.ratio_of(char)
    return 0.0 if span <= 0.0 else (ratio - low) / span


def evaluate_layout(
    layout: TextLayout,
    density_map: DensityMap,
    dictionary: DensityDictionary,
    *,
    table: dict[str, float] | None = None,
) -> DensityError:
    """配置と密度マップの位置ごとの誤差を求める。グリッドが違えば失敗にする。"""
    _require_same_grid(layout, density_map)
    table = table if table is not None else density_table(dictionary)
    cells = layout.cells
    try:
        actual = np.asarray([table[char] for char in cells], dtype=np.float32)
    except KeyError as exc:
        raise _unknown_char(str(exc.args[0])) from None
    errors = actual - density_map.sequence()
    return DensityError(errors=errors.reshape(density_map.shape), layout=layout)


def _require_same_grid(layout: TextLayout, density_map: DensityMap) -> None:
    grid = layout.grid
    other = density_map.grid
    if (grid.columns, grid.rows) != (other.columns, other.rows):
        raise StageError(
            _STAGE,
            "grid_mismatch",
            (
                f"配置と密度マップのセル数が違う: "
                f"{grid.columns}x{grid.rows} != {other.columns}x{other.rows}"
            ),
            hint="同じグリッド寸法で密度マップを作り直す。",
        )


def _unknown_char(char: str) -> StageError:
    return StageError(
        _STAGE,
        "unknown_char",
        f"密度辞書に無い文字が配置されている: {char!r} (U+{ord(char):04X})",
        hint="許可文字集合へ含めて辞書を作り直すか、本文から取り除く。",
    )
