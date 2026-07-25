"""層 A（既知キーのみ許可・禁止キー名）と I-07 の検証。"""

from __future__ import annotations

import re
from typing import Any

import pytest

from optpoet.errors import ManifestError
from optpoet.manifest import validate_manifest


def test_sample_manifest_is_valid(manifest_data: dict[str, Any]) -> None:
    """レビュー済みサンプルが層 A と不変条件を通過する（T-01）。"""
    validate_manifest(manifest_data)


def test_unknown_top_level_key(manifest_data: dict[str, Any]) -> None:
    manifest_data["extra"] = 1
    with pytest.raises(ManifestError, match="未知の項目: extra"):
        validate_manifest(manifest_data)


def test_unknown_nested_key(manifest_data: dict[str, Any]) -> None:
    manifest_data["grid"]["extra"] = 1
    with pytest.raises(ManifestError, match=re.escape("未知の項目: grid.extra")):
        validate_manifest(manifest_data)


def test_unknown_key_in_array_element(manifest_data: dict[str, Any]) -> None:
    manifest_data["ai_calls"][0]["extra"] = 1
    with pytest.raises(ManifestError, match=r"未知の項目: ai_calls\[0\].extra"):
        validate_manifest(manifest_data)


def test_unknown_key_kept_when_read_only(manifest_data: dict[str, Any]) -> None:
    """読取専用オープンでは未知項目を拒否しない（未知項目の保持）。"""
    manifest_data["grid"]["extra"] = 1
    validate_manifest(manifest_data, allow_unknown=True)


@pytest.mark.parametrize(
    "key",
    ["api_key", "apikey", "API-KEY", "authorization", "token", "access_token", "secret", "cookie"],
)
def test_forbidden_key_name(manifest_data: dict[str, Any], key: str) -> None:
    """禁止キー名は未知キー許容時でも拒否する（D-02 / T-08）。"""
    manifest_data["manifest"][key] = "dummy"
    with pytest.raises(ManifestError, match="秘密情報を示すキー名"):
        validate_manifest(manifest_data, allow_unknown=True)


def test_known_key_containing_token_is_allowed(manifest_data: dict[str, Any]) -> None:
    """`token_usage` のような既知キーは禁止リストの正規形一致では落ちない。"""
    validate_manifest(manifest_data)
    assert "token_usage" in manifest_data["ai_calls"][0]["provenance"]


@pytest.mark.parametrize("block", ["manifest", "input", "grid", "fonts", "ai_calls", "outputs"])
def test_missing_block(manifest_data: dict[str, Any], block: str) -> None:
    del manifest_data[block]
    with pytest.raises(ManifestError, match=f"必須項目がない: {block}"):
        validate_manifest(manifest_data)


@pytest.mark.parametrize(
    ("block", "key"),
    [
        ("manifest", "project_id"),
        ("fonts", "dictionary_id"),
        ("fonts", "missing_glyphs"),
        ("grid", "normalization_form"),
        ("preprocess", "gamma"),
        ("optimization", "seed"),
    ],
)
def test_missing_required_key(manifest_data: dict[str, Any], block: str, key: str) -> None:
    del manifest_data[block][key]
    with pytest.raises(ManifestError, match=f"必須項目がない: {block}.{key}"):
        validate_manifest(manifest_data)


def test_missing_ref_field(manifest_data: dict[str, Any]) -> None:
    del manifest_data["input"]["source"]["hash"]
    with pytest.raises(ManifestError, match=re.escape("必須項目がない: input.source.hash")):
        validate_manifest(manifest_data)


def test_array_expected(manifest_data: dict[str, Any]) -> None:
    manifest_data["ai_calls"] = {}
    with pytest.raises(ManifestError, match="ai_calls は配列"):
        validate_manifest(manifest_data)


def test_object_expected(manifest_data: dict[str, Any]) -> None:
    manifest_data["grid"] = []
    with pytest.raises(ManifestError, match="grid はオブジェクト"):
        validate_manifest(manifest_data)


@pytest.mark.parametrize(
    "value",
    [
        "/var/data/portrait.jpg",
        "C:/data/portrait.jpg",
        "c:portrait.jpg",
        "~/portrait.jpg",
        "\\\\host\\share\\portrait.jpg",
        "input\\portrait.jpg",
        "../portrait.jpg",
        "input/../../portrait.jpg",
        "input//portrait.jpg",
        "",
    ],
)
def test_relative_path_required(manifest_data: dict[str, Any], value: str) -> None:
    """I-07: 絶対パス・端末固有パス・親脱出・空要素を拒否する。"""
    manifest_data["input"]["source"]["path"] = value
    with pytest.raises(ManifestError, match=re.escape("input.source.path")):
        validate_manifest(manifest_data)


def test_relative_path_checked_in_nested_ref(manifest_data: dict[str, Any]) -> None:
    manifest_data["ai_calls"][0]["provenance"]["prompt_ref"]["path"] = "/tmp/prompt.json"
    with pytest.raises(ManifestError, match=r"ai_calls\[0\].provenance.prompt_ref.path"):
        validate_manifest(manifest_data)
