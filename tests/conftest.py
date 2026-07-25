"""テスト共通のフィクスチャ。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

SAMPLE_MANIFEST = Path(__file__).resolve().parents[1] / "docs" / "samples" / "manifest.sample.json"


@pytest.fixture(scope="session")
def sample_manifest_text() -> str:
    return SAMPLE_MANIFEST.read_text(encoding="utf-8")


@pytest.fixture
def manifest_data(sample_manifest_text: str) -> dict[str, Any]:
    """レビュー済みサンプル manifest の独立コピー。テストごとに壊してよい。"""
    data: dict[str, Any] = json.loads(sample_manifest_text)
    return data
