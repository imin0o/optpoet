"""ファイルシステムを参照せずに判定できる不変条件。

docs/decisions/project-manifest.md「不変条件」のうち、manifest 内部だけで検証できる
I-03 / I-04 / I-05 を扱う。I-02 参照健全性（`path` の存在と `hash` 一致）は内容ハッシュ
（P1-003）が必要なため本モジュールでは扱わない。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from optpoet.errors import ManifestError

# `semantic_design.source_call` が AI 呼出ではなく手入力であることを表す予約値。
MANUAL_SOURCE = "manual"


def check_invariants(data: Mapping[str, Any]) -> None:
    """層 A を通過した manifest に対し、内部整合の不変条件を検証する。"""
    _check_render_consistency(data)
    _check_cell_consistency(data)
    # 識別子の一意性を先に見る（重複したままでは参照照合の結果が意味を持たない）。
    _check_unique_ids(data)
    _check_internal_refs(data)
    _check_final_text(data)


def _check_render_consistency(data: Mapping[str, Any]) -> None:
    """I-03 描画一貫性: render_settings と render_metadata が一致する。"""
    outputs = data["outputs"]
    metadata = outputs.get("render_metadata")
    if metadata is None:
        if "png_ref" in outputs or "txt_ref" in outputs:
            raise ManifestError("outputs に成果物があるが render_metadata がない")
        return
    if metadata != data["fonts"]["render_settings"]:
        raise ManifestError("fonts.render_settings と outputs.render_metadata が不一致（I-03）")


def _check_cell_consistency(data: Mapping[str, Any]) -> None:
    """I-04 セル整合: セル数が grid.cols × grid.rows と一致する。"""
    cell_check = data["evaluation"].get("cell_check")
    if cell_check is None:
        return
    expected = data["grid"]["cols"] * data["grid"]["rows"]
    if cell_check["expected_cells"] != expected:
        raise ManifestError(
            f"evaluation.cell_check.expected_cells が grid と不一致（I-04）: "
            f"{cell_check['expected_cells']} != {expected}"
        )
    # 不一致の記録自体は残す。result が ok のときだけ一致を要求する。
    if cell_check.get("result") == "ok" and cell_check["displayed_chars"] != expected:
        raise ManifestError(
            f"cell_check.result が ok だが displayed_chars がセル数と不一致（I-04）: "
            f"{cell_check['displayed_chars']} != {expected}"
        )


def _check_internal_refs(data: Mapping[str, Any]) -> None:
    """I-05 内部参照解決: call_id を指す参照がすべて ai_calls に存在する。"""
    call_ids = {call["call_id"] for call in data["ai_calls"]}
    source_call = data["semantic_design"].get("source_call")
    if source_call is not None and source_call != MANUAL_SOURCE and source_call not in call_ids:
        raise ManifestError(f"semantic_design.source_call が未解決（I-05）: {source_call!r}")
    for call in data["ai_calls"]:
        superseded = call.get("superseded_by")
        if superseded is not None and superseded not in call_ids:
            raise ManifestError(f"ai_calls.superseded_by が未解決（I-05）: {superseded!r}")


def _check_unique_ids(data: Mapping[str, Any]) -> None:
    """追記のみの履歴が識別子で一意に参照できる。"""
    _require_unique("ai_calls.call_id", (call["call_id"] for call in data["ai_calls"]))
    _require_unique("edits.edit_id", (edit["edit_id"] for edit in data["edits"]))


def _check_final_text(data: Mapping[str, Any]) -> None:
    """最終文章と出力 TXT が同一内容である（project-manifest.md `final_ref`）。"""
    final_ref = data["text"].get("final_ref")
    txt_ref = data["outputs"].get("txt_ref")
    if final_ref is None or txt_ref is None:
        return
    if final_ref["hash"] != txt_ref["hash"]:
        raise ManifestError("text.final_ref と outputs.txt_ref の hash が不一致")


def _require_unique(label: str, values: Iterable[Any]) -> None:
    seen: set[Any] = set()
    for value in values:
        if value in seen:
            raise ManifestError(f"{label} が重複: {value!r}")
        seen.add(value)
