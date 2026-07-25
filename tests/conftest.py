"""テスト共通のフィクスチャ。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from optpoet.hashing import hash_bytes
from optpoet.storage import ProjectLayout, iter_refs

SAMPLE_MANIFEST = Path(__file__).resolve().parents[1] / "docs" / "samples" / "manifest.sample.json"


@pytest.fixture(scope="session")
def sample_manifest_text() -> str:
    return SAMPLE_MANIFEST.read_text(encoding="utf-8")


@pytest.fixture
def manifest_data(sample_manifest_text: str) -> dict[str, Any]:
    """レビュー済みサンプル manifest の独立コピー。テストごとに壊してよい。"""
    data: dict[str, Any] = json.loads(sample_manifest_text)
    return data


@pytest.fixture
def project_layout(tmp_path: Path) -> ProjectLayout:
    layout = ProjectLayout(tmp_path)
    layout.create()
    return layout


@pytest.fixture
def materialized_manifest(
    manifest_data: dict[str, Any],
    project_layout: ProjectLayout,
) -> dict[str, Any]:
    """全 ref の実体を作り、`hash` と `bytes` を実測値へ合わせたサンプル manifest。

    保存手順 A-04 の照合（I-02）を通すため。`text.final_ref` と `outputs.txt_ref` は同一
    内容を要求されるので、全 ref を同一内容で置く（照合するのは hash の一致だけ）。
    """
    payload = b"optpoet"
    digest = hash_bytes(payload)
    for _label, ref in iter_refs(manifest_data):
        mutable = cast(dict[str, Any], ref)
        target = project_layout.resolve(mutable["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        mutable["hash"] = digest
        if "bytes" in mutable:
            mutable["bytes"] = len(payload)
    return manifest_data
