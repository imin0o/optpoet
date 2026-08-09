"""表記候補による局所探索と停止条件（P1-035 / P1-036 / FR-09 第 4 段階）。

アーキテクチャは「MVP ではビームサーチまたは局所探索」と定める（architecture.md 第4段階）。
Phase 1 の評価値は位置ごとの密度誤差だけで、セル間に相互作用が無い（1 セルの文字を変えても
他セルの誤差は変わらない）。この構造では山登り 1 回で各セルの最適候補へ届くため、状態を
複数保つビームサーチは利得が無い。よって **局所探索（山登り）** を採る。

1 反復で全セルを誤差の大きい順に走査し、各セルで候補を総当たりして最良を採る。反復は
評価値の改善が `min_improvement`（MAE 換算）以下になったら止め（改善停止）、それ以前に
`max_iterations` へ達したらそこで止める。取消は `StageProgress` 経由で位置ごとに確認する
（FR-18）。中断しても、そこまでに採用した配置は `StageCancelledError` 側では返らないため、
呼出側は中断前の配置（入力）を保持し続ける。

候補と採否と評価値は `OptimizationTrace` へ記録する（P1-037）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from optpoet.errors import StageError
from optpoet.font.dictionary import DensityDictionary
from optpoet.image.density import DensityMap
from optpoet.pipeline.progress import StageProgress
from optpoet.storage import Stage
from optpoet.text.evaluate import DensityError, density_table, evaluate_layout
from optpoet.text.layout import TextLayout
from optpoet.text.trace import DEFAULT_MAX_ENTRIES, OptimizationTrace, TraceEntry
from optpoet.text.variants import VariantTable, default_variants

ALGORITHM_NAME = "local_search"
ALGORITHM_VERSION = "1.0"

STOPPED_CONVERGED = "converged"
STOPPED_MAX_ITERATIONS = "max_iterations"

_STAGE = str(Stage.OPTIMIZE)


@dataclass(frozen=True, slots=True)
class OptimizeSettings:
    """探索の停止条件。manifest の `optimization` へそのまま書ける。"""

    max_iterations: int = 8
    min_improvement: float = 1e-4
    """1 反復で MAE がこれ以下しか改善しなければ止める（改善停止）。"""
    max_trace_entries: int = DEFAULT_MAX_ENTRIES

    def validate(self) -> None:
        if self.max_iterations < 1:
            raise _invalid_settings("max_iterations", self.max_iterations, "1 以上にする。")
        if self.min_improvement < 0.0:
            raise _invalid_settings("min_improvement", self.min_improvement, "0.0 以上にする。")
        if self.max_trace_entries < 0:
            raise _invalid_settings("max_trace_entries", self.max_trace_entries, "0 以上にする。")

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_iterations": self.max_iterations,
            "min_improvement": self.min_improvement,
            "max_trace_entries": self.max_trace_entries,
        }


@dataclass(frozen=True, slots=True, eq=False)
class OptimizeResult:
    """最適化の結果と経緯。"""

    layout: TextLayout
    initial: DensityError
    final: DensityError
    iterations: int
    accepted: int
    stopped: str
    trace: OptimizationTrace

    @property
    def improvement(self) -> float:
        """MAE の減少量。負にはならない（悪化する候補は採らない）。"""
        return self.initial.mae - self.final.mae

    @property
    def improvement_rate(self) -> float:
        """MAE の改善率（AC-03 の評価に使う）。初期誤差が 0 なら 0.0。"""
        return 0.0 if self.initial.mae <= 0.0 else self.improvement / self.initial.mae

    def to_dict(self) -> dict[str, Any]:
        return {
            "algorithm": {"name": ALGORITHM_NAME, "version": ALGORITHM_VERSION},
            "iterations": self.iterations,
            "accepted": self.accepted,
            "stopped": self.stopped,
            "mae_initial": self.initial.mae,
            "mae_final": self.final.mae,
            "improvement_rate": self.improvement_rate,
        }


def optimize_layout(
    layout: TextLayout,
    density_map: DensityMap,
    dictionary: DensityDictionary,
    *,
    variants: VariantTable | None = None,
    settings: OptimizeSettings | None = None,
    progress: StageProgress | None = None,
) -> OptimizeResult:
    """配置の密度誤差を、意味を変えない表記置換だけで下げる。"""
    settings = settings or OptimizeSettings()
    settings.validate()
    table = default_variants() if variants is None else variants
    table = table.restricted(frozenset(dictionary.chars))

    densities = density_table(dictionary)
    initial = evaluate_layout(layout, density_map, dictionary, table=densities)
    targets = density_map.sequence()
    cells = list(layout.cells)
    trace = OptimizationTrace(
        params=_trace_params(settings, table, dictionary),
        max_entries=settings.max_trace_entries,
    )

    current = initial
    accepted = 0
    iterations = 0
    stopped = STOPPED_MAX_ITERATIONS
    for iteration in range(1, settings.max_iterations + 1):
        iterations = iteration
        gained = _pass(
            iteration,
            cells,
            targets,
            densities,
            table,
            current,
            trace,
            progress,
        )
        accepted += gained.accepted
        current = evaluate_layout(
            _rebuild(cells, layout),
            density_map,
            dictionary,
            table=densities,
        )
        if gained.total / len(cells) <= settings.min_improvement:
            stopped = STOPPED_CONVERGED
            break
        if progress is not None:
            progress.report(iteration)

    final_layout = _rebuild(cells, layout)
    if progress is not None:
        progress.finish()
    return OptimizeResult(
        layout=final_layout,
        initial=initial,
        final=current,
        iterations=iterations,
        accepted=accepted,
        stopped=stopped,
        trace=trace,
    )


@dataclass(frozen=True, slots=True)
class _PassResult:
    total: float
    accepted: int


def _pass(
    iteration: int,
    cells: list[str],
    targets: NDArray[np.float32],
    densities: dict[str, float],
    table: VariantTable,
    current: DensityError,
    trace: OptimizationTrace,
    progress: StageProgress | None,
) -> _PassResult:
    """誤差の大きい順に 1 巡し、改善する置換だけを採る。`cells` を直接書き換える。"""
    total = 0.0
    accepted = 0
    for index in current.worst_indices():
        if progress is not None:
            progress.check_cancelled()
        char = cells[index]
        options = table.candidates(char)
        if not options:
            continue
        target = float(targets[index])
        before = abs(densities[char] - target)
        scored = sorted((abs(densities[option] - target), option) for option in options)
        best_error, best_char = scored[0]
        improves = best_error < before
        for error, option in scored:
            trace.record(
                TraceEntry(
                    iteration=iteration,
                    index=index,
                    char=char,
                    candidate=option,
                    error_before=before,
                    error_after=error,
                    accepted=improves and option == best_char,
                )
            )
        if improves:
            cells[index] = best_char
            total += before - best_error
            accepted += 1
    return _PassResult(total=total, accepted=accepted)


def _rebuild(cells: list[str], source: TextLayout) -> TextLayout:
    return TextLayout.from_cells(
        tuple(cells),
        source.grid,
        content_cells=source.content_cells,
        rule=source.rule,
        fill=source.fill,
    )


def _trace_params(
    settings: OptimizeSettings,
    table: VariantTable,
    dictionary: DensityDictionary,
) -> dict[str, Any]:
    return {
        "algorithm": {"name": ALGORITHM_NAME, "version": ALGORITHM_VERSION},
        "settings": settings.to_dict(),
        "variants": table.to_dict(),
        "dictionary_id": dictionary.dictionary_id,
    }


def _invalid_settings(name: str, value: float, hint: str) -> StageError:
    return StageError(
        _STAGE,
        "invalid_settings",
        f"optimization.{name} の値が不正: {value!r}",
        hint=hint,
    )
