"""意味を考慮しない基準配置（P1-034 / AC-03）。

各セルへ、目標密度に最も近い文字を許可文字集合から独立に選ぶ。文章としての意味・文法・
読みは一切見ない。したがって結果は読めない文字列になるが、**その配置で到達しうる密度誤差**
が分かる。これが最適化（P1-035）の比較用ベースラインになる。

比較の読み方:

- 基準配置の MAE = 文字選択だけで到達できる誤差の下限（同じ辞書・同じグリッドで）。
- 本文をそのまま置いた配置の MAE = 最適化前の出発点。
- 最適化後の MAE = 意味を保ったまま下限へどれだけ寄れたか。

同差の場合は密度の低い文字、さらに同値なら符号位置の小さい文字を採る。並びを固定して
おかないと、同じ入力から違う基準配置が出て比較にならない（P1-026 と同じ理由）。
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from optpoet.font.dictionary import DensityDictionary
from optpoet.image.density import DensityMap
from optpoet.text.evaluate import density_table
from optpoet.text.layout import LineBreak, TextLayout


def build_baseline(density_map: DensityMap, dictionary: DensityDictionary) -> TextLayout:
    """密度だけで各セルの文字を決めた配置を返す。"""
    chars, values = _sorted_by_density(dictionary)
    targets = density_map.sequence()

    # 昇順の密度列に対する挿入位置を取り、その左右の候補だけを比べる。
    right = np.searchsorted(values, targets, side="left")
    left = np.clip(right - 1, 0, len(values) - 1)
    right = np.clip(right, 0, len(values) - 1)
    # 同差なら密度の低い側（left）を採るため `<=` で比較する。
    take_left = np.abs(values[left] - targets) <= np.abs(values[right] - targets)
    picked = np.where(take_left, left, right)

    cells = tuple(chars[int(index)] for index in picked)
    return TextLayout.from_cells(cells, density_map.grid, rule=LineBreak.SIMPLE)


def _sorted_by_density(
    dictionary: DensityDictionary,
) -> tuple[tuple[str, ...], NDArray[np.float32]]:
    """正規化密度の昇順に並べた (文字, 密度)。同値は符号位置の昇順にする。"""
    table = density_table(dictionary)
    ordered = sorted(table.items(), key=lambda item: (item[1], ord(item[0])))
    chars = tuple(char for char, _ in ordered)
    values = np.asarray([value for _, value in ordered], dtype=np.float32)
    return chars, values
