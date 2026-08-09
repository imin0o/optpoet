"""P1 完了ゲートの実行単位（1 画像 = 1 ケース）を組み立てる。

Phase 1 は AI を使わないため、草稿は既存テキストの先頭から必要セル数ぶんを取り、それを
そのまま配置したものを **草稿配置**（最適化前）とする（evaluation-metrics.md 1 章）。
最適化後との密度 MAE を比べて AC-03 の改善率を出す。

工程の並びは architecture.md と同じ:
画像受入 → 正規化 → 前処理 → 密度マップ → 配置 → 最適化 → 描画 → 評価。
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from optpoet.config import ImageConfig
from optpoet.font import DensityDictionary, FontProfile, RenderSettings
from optpoet.image import (
    GridSpec,
    apply_preprocess,
    build_density_map,
    extract_region,
    inspect_image,
    normalize_image,
    plan_region,
)
from optpoet.render import Artwork, Metrics, RenderStyle, evaluate_outputs, render_artwork
from optpoet.text import (
    OptimizeSettings,
    TextLayout,
    build_baseline,
    check_fit,
    count_cells,
    evaluate_layout,
    layout_text,
    normalize_text,
    optimize_layout,
)

LIMITS = ImageConfig()


@dataclass(slots=True)
class Timings:
    """工程別の所要時間（秒）。P1-G05 の性能記録に使う。"""

    stages: dict[str, float] = field(default_factory=dict)

    @contextmanager
    def measure(self, name: str) -> Iterator[None]:
        start = time.perf_counter()
        yield
        self.stages[name] = self.stages.get(name, 0.0) + (time.perf_counter() - start)

    @property
    def total(self) -> float:
        return sum(self.stages.values())


@dataclass(frozen=True, slots=True)
class CaseResult:
    """1 ケースの実行結果。"""

    slot: str
    grid: GridSpec
    target: Image.Image
    draft: Artwork
    optimized: Artwork
    metrics: Metrics
    iterations: int
    accepted: int
    stopped: str
    missing_glyphs: tuple[str, ...]
    timings: Timings
    trace_entries: int
    density_mae_draft: float
    density_mae_opt: float
    density_mae_baseline: float


def take_text(source: str, cells: int) -> str:
    """本文の先頭から、ちょうど `cells` セルぶんを取る（改行はセルに数えない）。"""
    taken: list[str] = []
    used = 0
    for char in source:
        if used == cells:
            break
        taken.append(char)
        if char != "\n":
            used += 1
    if used < cells:
        raise SystemExit(f"入力文が足りない: {used} < {cells}")
    return "".join(taken)


def fit_draft(text: str, grid: GridSpec) -> TextLayout:
    """草稿配置を作る。禁則で溢れる場合は末尾を削って収める（暗黙削除はここだけ）。

    P1-032 は本文の暗黙削除を禁じるが、それは作者の文章に対する規則である。ここは
    ゲート用に既存テキストから必要量を切り出す前処理で、削った量は呼出側が記録する。
    """
    body = text
    while True:
        report = check_fit(body, grid)
        if report.delta > 0:
            body = _trim(body, report.delta)
            continue
        try:
            return layout_text(body, grid)
        except Exception:
            if count_cells(body) <= grid.cells // 2:
                raise
            body = _trim(body, max(1, grid.columns // 2))


def _trim(text: str, cells: int) -> str:
    removed = 0
    index = len(text)
    while index > 0 and removed < cells:
        index -= 1
        if text[index] != "\n":
            removed += 1
    return text[:index]


def run_case(
    slot: str,
    image_path: Path,
    source_text: str,
    grid: GridSpec,
    profile: FontProfile,
    dictionary: DensityDictionary,
    settings: RenderSettings,
    style: RenderStyle,
    *,
    optimize_settings: OptimizeSettings | None = None,
) -> CaseResult:
    """1 画像を受入から評価まで通す。"""
    timings = Timings()

    with timings.measure("image_intake"):
        inspect_image(image_path, LIMITS)
        with Image.open(image_path) as opened:
            opened.load()
            normalized = normalize_image(opened)

    with timings.measure("preprocess"):
        preprocessed = apply_preprocess(normalized.image)
        region = plan_region(preprocessed.image.size, grid)
        target = extract_region(preprocessed.image, region)

    with timings.measure("density_map"):
        density_map = build_density_map(preprocessed.image, grid, limits=LIMITS)

    with timings.measure("text_layout"):
        body = normalize_text(take_text(source_text, grid.cells))
        missing = profile.missing(set(body) - {"\n"})
        draft_layout = fit_draft(body, grid)

    with timings.measure("optimize"):
        result = optimize_layout(
            draft_layout,
            density_map,
            dictionary,
            settings=optimize_settings,
        )

    with timings.measure("render"):
        draft_art = render_artwork(draft_layout, profile, settings, style)
        optimized_art = render_artwork(result.layout, profile, settings, style)

    with timings.measure("evaluate"):
        metrics = evaluate_outputs(
            target,
            optimized_art.image,
            grid,
            draft=draft_art.image,
        )
        # 密度領域（辞書の正規化密度）の誤差も残す。最適化の目的関数はこちらで、
        # PNG 画素領域の MAE（evaluation-metrics.md 3 章）とは尺度が違う。
        baseline_mae = evaluate_layout(
            build_baseline(density_map, dictionary), density_map, dictionary
        ).mae

    return CaseResult(
        slot=slot,
        grid=grid,
        target=target,
        draft=draft_art,
        optimized=optimized_art,
        metrics=metrics,
        iterations=result.iterations,
        accepted=result.accepted,
        stopped=result.stopped,
        missing_glyphs=missing,
        timings=timings,
        trace_entries=len(result.trace.entries),
        density_mae_draft=result.initial.mae,
        density_mae_opt=result.final.mae,
        density_mae_baseline=baseline_mae,
    )


def case_record(case: CaseResult) -> dict[str, Any]:
    """JSON へ落とす 1 ケース分の記録。"""
    check = case.optimized.cell_check
    return {
        "slot": case.slot,
        "grid": {"columns": case.grid.columns, "rows": case.grid.rows, "cells": case.grid.cells},
        "cell_check": check.to_dict(),
        "missing_glyphs": list(case.missing_glyphs),
        "metrics": case.metrics.to_dict(),
        "density_metrics": {
            "mae_draft": case.density_mae_draft,
            "mae_opt": case.density_mae_opt,
            "mae_baseline": case.density_mae_baseline,
            "improvement_rate": (
                None
                if case.density_mae_draft <= 0.0
                else (case.density_mae_draft - case.density_mae_opt) / case.density_mae_draft
            ),
        },
        "optimization": {
            "iterations": case.iterations,
            "accepted": case.accepted,
            "stopped": case.stopped,
            "trace_entries": case.trace_entries,
        },
        "timings": {name: round(value, 3) for name, value in case.timings.stages.items()},
        "total_seconds": round(case.timings.total, 3),
    }
