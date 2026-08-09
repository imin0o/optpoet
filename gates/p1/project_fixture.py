"""ゲート用のプロジェクト一式（manifest ＋ 実体 ＋ 描画結果）を組み立てる。

保存・再生（P1-G04）と容量不足（P1-G03）は、スキーマ検証と参照健全性（I-02）を通る
manifest が要る。レビュー済みサンプル（docs/samples/manifest.sample.json）を土台にし、
全 ref の実体を作ってハッシュを実測値へ揃える（tests/conftest.py と同じ手順）。

Phase 1 は AI を使わないため、`ai_calls` は空にし、`semantic_design.source_call` は
手動（`MANUAL_SOURCE`）にする。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from optpoet.font import RenderSettings, load_font_profile
from optpoet.hashing import hash_bytes
from optpoet.image import GridSpec
from optpoet.manifest.invariants import MANUAL_SOURCE
from optpoet.render import Artwork, RenderStyle, render_artwork
from optpoet.storage import ProjectLayout, iter_refs
from optpoet.text import layout_text

SAMPLE = Path(__file__).resolve().parents[2] / "docs" / "samples" / "manifest.sample.json"

GRID = GridSpec(columns=6, rows=2)
TEXT = "いろはにほへとちりぬるを"
SETTINGS = RenderSettings(pixel_size=24, cell_width=32, cell_height=32)
STYLE = RenderStyle()


def render_case(font: Path, *, text: str = TEXT, grid: GridSpec = GRID) -> Artwork:
    """1 組の描画結果を作る。"""
    return render_artwork(layout_text(text, grid), load_font_profile(font), SETTINGS, STYLE)


def build_manifest(layout: ProjectLayout, settings: RenderSettings = SETTINGS) -> dict[str, Any]:
    """サンプルを土台に、全 ref の実体を作った manifest を返す。"""
    data: dict[str, Any] = json.loads(SAMPLE.read_text(encoding="utf-8"))
    data["ai_calls"] = []
    data["semantic_design"]["source_call"] = MANUAL_SOURCE
    payload = b"optpoet-p1-gate"
    digest = hash_bytes(payload)
    for _label, ref in iter_refs(data):
        mutable = cast(dict[str, Any], ref)
        target = layout.resolve(mutable["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        mutable["hash"] = digest
        if "bytes" in mutable:
            mutable["bytes"] = len(payload)
    data["fonts"]["render_settings"] = settings.to_dict()
    return data


def build_project(root: Path, font: Path) -> tuple[ProjectLayout, dict[str, Any], Artwork]:
    """プロジェクト領域・manifest・描画結果を作って返す（保存はしない）。"""
    layout = ProjectLayout(root)
    layout.create()
    return layout, build_manifest(layout), render_case(font)
