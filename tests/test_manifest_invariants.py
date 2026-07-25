"""内部整合の不変条件（I-03 / I-04 / I-05）の検証。"""

from __future__ import annotations

import re
from typing import Any

import pytest

from optpoet.errors import ManifestError
from optpoet.manifest import MANUAL_SOURCE, validate_manifest


def test_render_settings_mismatch(manifest_data: dict[str, Any]) -> None:
    manifest_data["outputs"]["render_metadata"]["pixel_size"] = 96
    with pytest.raises(ManifestError, match="I-03"):
        validate_manifest(manifest_data)


def test_render_metadata_required_when_output_exists(manifest_data: dict[str, Any]) -> None:
    del manifest_data["outputs"]["render_metadata"]
    with pytest.raises(ManifestError, match="render_metadata がない"):
        validate_manifest(manifest_data)


def test_outputs_may_be_empty(manifest_data: dict[str, Any]) -> None:
    """描画前は outputs が空でよい（条件付き必須）。"""
    manifest_data["outputs"] = {}
    validate_manifest(manifest_data)


def test_expected_cells_mismatch(manifest_data: dict[str, Any]) -> None:
    manifest_data["grid"]["cols"] = 50
    with pytest.raises(ManifestError, match="I-04"):
        validate_manifest(manifest_data)


def test_displayed_chars_mismatch_when_ok(manifest_data: dict[str, Any]) -> None:
    manifest_data["evaluation"]["cell_check"]["displayed_chars"] = 2399
    with pytest.raises(ManifestError, match="displayed_chars"):
        validate_manifest(manifest_data)


def test_displayed_chars_mismatch_recorded_as_failure(manifest_data: dict[str, Any]) -> None:
    """不一致を検出結果として記録した manifest は保持できる。"""
    manifest_data["evaluation"]["cell_check"]["displayed_chars"] = 2399
    manifest_data["evaluation"]["cell_check"]["result"] = "mismatch"
    validate_manifest(manifest_data)


def test_evaluation_may_be_empty(manifest_data: dict[str, Any]) -> None:
    manifest_data["evaluation"] = {}
    validate_manifest(manifest_data)


def test_source_call_unresolved(manifest_data: dict[str, Any]) -> None:
    manifest_data["semantic_design"]["source_call"] = "call-9999"
    with pytest.raises(ManifestError, match="I-05"):
        validate_manifest(manifest_data)


def test_source_call_manual(manifest_data: dict[str, Any]) -> None:
    """手入力は AI 呼出を指さない予約値で表す。"""
    manifest_data["semantic_design"]["source_call"] = MANUAL_SOURCE
    validate_manifest(manifest_data)


def test_superseded_by_unresolved(manifest_data: dict[str, Any]) -> None:
    manifest_data["ai_calls"][1]["superseded_by"] = "call-9999"
    with pytest.raises(ManifestError, match="superseded_by"):
        validate_manifest(manifest_data)


def test_duplicate_call_id(manifest_data: dict[str, Any]) -> None:
    manifest_data["ai_calls"][2]["call_id"] = "call-0001"
    with pytest.raises(ManifestError, match=re.escape("ai_calls.call_id が重複")):
        validate_manifest(manifest_data)


def test_duplicate_edit_id(manifest_data: dict[str, Any]) -> None:
    manifest_data["edits"][1]["edit_id"] = "edit-0001"
    with pytest.raises(ManifestError, match=re.escape("edits.edit_id が重複")):
        validate_manifest(manifest_data)


def test_final_text_hash_mismatch(manifest_data: dict[str, Any]) -> None:
    manifest_data["outputs"]["txt_ref"]["hash"] = "sha256:" + "0" * 64
    with pytest.raises(ManifestError, match="final_ref"):
        validate_manifest(manifest_data)
