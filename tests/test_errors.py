"""工程別の構造化エラーの検証（FR-18 の 2 区分・失敗クラス・提示用構造）。"""

from __future__ import annotations

import pytest

from optpoet.errors import (
    ArtifactCorruptedError,
    ConfigError,
    ErrorKind,
    FailureClass,
    OptpoetError,
    StageCancelledError,
    StageError,
    error_kind,
)
from optpoet.storage import Stage


def test_stage_error_carries_structured_fields() -> None:
    exc = StageError(
        Stage.DENSITY_MAP,
        "grid_too_small",
        "グリッドが密度マップより小さい",
        hint="grid.columns を増やす",
    )
    assert exc.stage == "density_map"
    assert exc.code == "grid_too_small"
    assert exc.detail == "グリッドが密度マップより小さい"
    assert exc.hint == "grid.columns を増やす"


def test_stage_error_message_includes_stage_and_code() -> None:
    exc = StageError("preprocess", "unreadable", "画像を読めない")
    assert str(exc) == "[preprocess/unreadable] 画像を読めない"


def test_stage_error_is_optpoet_error() -> None:
    with pytest.raises(OptpoetError):
        raise StageError("render", "no_font", "フォントがない")


def test_stage_error_defaults_to_needs_config() -> None:
    """区分不明を暗黙に再試行可能としない。"""
    exc = StageError("render", "no_font", "フォントがない")
    assert exc.kind is ErrorKind.NEEDS_CONFIG
    assert exc.retriable is False


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (FailureClass.TIMEOUT, ErrorKind.RETRIABLE),
        (FailureClass.RATELIMIT, ErrorKind.RETRIABLE),
        (FailureClass.SERVICE, ErrorKind.RETRIABLE),
        (FailureClass.AUTH, ErrorKind.NEEDS_CONFIG),
    ],
)
def test_failure_class_kind(failure: FailureClass, expected: ErrorKind) -> None:
    """F-AUTH のみ設定修正が必要（ai-failure-responses.md）。"""
    assert failure.kind is expected


def test_stage_error_derives_kind_from_failure() -> None:
    exc = StageError("ai_call", "timeout", "応答が返らない", failure=FailureClass.TIMEOUT)
    assert exc.kind is ErrorKind.RETRIABLE
    assert exc.retriable is True


def test_stage_error_explicit_kind_wins() -> None:
    exc = StageError(
        "ai_call",
        "service",
        "上限到達で打ち切った",
        failure=FailureClass.SERVICE,
        kind=ErrorKind.NEEDS_CONFIG,
    )
    assert exc.kind is ErrorKind.NEEDS_CONFIG


def test_to_dict_omits_absent_fields() -> None:
    exc = StageError("optimize", "no_candidate", "候補がない")
    assert exc.to_dict() == {
        "stage": "optimize",
        "code": "no_candidate",
        "message": "候補がない",
        "kind": "needs_config",
    }


def test_to_dict_includes_failure_and_retry_after() -> None:
    exc = StageError(
        "ai_call",
        "ratelimit",
        "割当を超えた",
        failure=FailureClass.RATELIMIT,
        hint="時間をおいて再試行する",
        retry_after_ms=2_000,
    )
    assert exc.to_dict() == {
        "stage": "ai_call",
        "code": "ratelimit",
        "message": "割当を超えた",
        "kind": "retriable",
        "failure": "F-RATELIMIT",
        "hint": "時間をおいて再試行する",
        "retry_after_ms": 2_000,
    }


def test_stage_cancelled_keeps_completed_count() -> None:
    exc = StageCancelledError(Stage.OPTIMIZE, completed=12, note="作者操作")
    assert exc.stage == "optimize"
    assert exc.completed == 12
    assert exc.note == "作者操作"
    assert "12" in str(exc)


def test_stage_cancelled_is_not_a_stage_error() -> None:
    """中断は失敗ではないため、失敗として扱う経路に入らない。"""
    assert not isinstance(StageCancelledError("optimize"), StageError)


@pytest.mark.parametrize(
    "exc",
    [
        ConfigError("設定不正"),
        ArtifactCorruptedError("破損"),
        ValueError("未分類"),
    ],
)
def test_error_kind_defaults_to_needs_config(exc: Exception) -> None:
    assert error_kind(exc) is ErrorKind.NEEDS_CONFIG


def test_error_kind_uses_stage_error_kind() -> None:
    exc = StageError("ai_call", "timeout", "応答が返らない", failure=FailureClass.TIMEOUT)
    assert error_kind(exc) is ErrorKind.RETRIABLE
