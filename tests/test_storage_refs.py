"""ref 健全性検証（I-02）の検証。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from optpoet.errors import ArtifactCorruptedError, ManifestError, StorageError
from optpoet.hashing import hash_bytes
from optpoet.storage import ProjectLayout, iter_refs, verify_refs


@pytest.fixture
def layout(tmp_path: Path) -> ProjectLayout:
    result = ProjectLayout(tmp_path)
    result.create()
    return result


def _ref(layout: ProjectLayout, relative: str, data: bytes) -> dict[str, Any]:
    target = layout.resolve(relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return {
        "path": relative,
        "hash": hash_bytes(data),
        "media_type": "application/octet-stream",
        "bytes": len(data),
    }


def test_iter_refs_finds_nested_refs(manifest_data: dict[str, Any]) -> None:
    labels = [label for label, _ in iter_refs(manifest_data)]
    assert "input.source" in labels
    assert "ai_calls[0].provenance.prompt_ref" in labels


def test_iter_refs_ignores_non_ref_objects() -> None:
    data = {"grid": {"cols": 60, "rows": 40}}
    assert list(iter_refs(data)) == []


def test_verify_refs_passes(layout: ProjectLayout) -> None:
    data = {
        "input": {"source": _ref(layout, "input/portrait.jpg", b"jpeg")},
        "outputs": {"txt_ref": _ref(layout, "outputs/artwork.txt", b"text")},
    }
    assert verify_refs(data, layout) == 2


def test_verify_refs_reports_missing_file(layout: ProjectLayout) -> None:
    data = {"input": {"source": {"path": "input/absent.jpg", "hash": hash_bytes(b"jpeg")}}}
    with pytest.raises(ManifestError, match="参照先の実体がない（I-02）"):
        verify_refs(data, layout)


def test_verify_refs_reports_hash_mismatch(layout: ProjectLayout) -> None:
    ref = _ref(layout, "input/portrait.jpg", b"jpeg")
    layout.resolve(ref["path"]).write_bytes(b"jpeh")
    del ref["bytes"]
    with pytest.raises(ArtifactCorruptedError, match="内容ハッシュが manifest と一致しない"):
        verify_refs({"input": {"source": ref}}, layout)


def test_verify_refs_checks_size_first(layout: ProjectLayout) -> None:
    """`bytes` があれば安いサイズ比較で先に不一致を出す。"""
    ref = _ref(layout, "input/portrait.jpg", b"jpeg")
    ref["bytes"] = 999
    with pytest.raises(ArtifactCorruptedError, match="サイズが manifest と一致しない"):
        verify_refs({"input": {"source": ref}}, layout)


def test_verify_refs_rejects_non_string_path(layout: ProjectLayout) -> None:
    data = {"input": {"source": {"path": 1, "hash": hash_bytes(b"jpeg")}}}
    with pytest.raises(ManifestError, match="path は文字列"):
        verify_refs(data, layout)


def test_verify_refs_rejects_bad_hash_format(layout: ProjectLayout) -> None:
    ref = _ref(layout, "input/portrait.jpg", b"jpeg")
    ref["hash"] = "deadbeef"
    with pytest.raises(StorageError, match="内容ハッシュ"):
        verify_refs({"input": {"source": ref}}, layout)


def test_sample_manifest_refs_are_all_missing(
    manifest_data: dict[str, Any], layout: ProjectLayout
) -> None:
    """サンプルは実体を伴わないため、I-02 は構造検証と別に走らせる必要がある。"""
    with pytest.raises(ManifestError, match="参照先の実体がない"):
        verify_refs(manifest_data, layout)
