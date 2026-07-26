"""工程実行枠の検証（開始・完了・失敗・中断の通知と例外の透過）。"""

from __future__ import annotations

import pytest

from optpoet.errors import ErrorKind, FailureClass, StageCancelledError, StageError, StorageError
from optpoet.pipeline import CancelToken, CollectingSink, StageStatus, run_stage
from optpoet.storage import Stage


def _statuses(sink: CollectingSink) -> list[StageStatus]:
    return [event.status for event in sink.events]


def test_success_emits_started_and_completed() -> None:
    sink = CollectingSink()
    with run_stage(Stage.DENSITY_MAP, total=2, sink=sink) as progress:
        progress.advance()
        progress.advance()
    assert _statuses(sink) == [
        StageStatus.STARTED,
        StageStatus.ADVANCED,
        StageStatus.ADVANCED,
        StageStatus.COMPLETED,
    ]
    assert sink.events[-1].completed == 2
    assert sink.events[0].stage == "density_map"


def test_started_event_reports_total_and_ai_use() -> None:
    sink = CollectingSink()
    with run_stage("ai_call", total=3, uses_ai=True, sink=sink):
        pass
    started = sink.events[0]
    assert started.total == 3
    assert started.uses_ai is True


def test_failure_emits_failed_and_reraises() -> None:
    sink = CollectingSink()
    with pytest.raises(StageError) as info, run_stage("preprocess", sink=sink) as progress:
        progress.advance()
        raise StageError("preprocess", "unreadable", "画像を読めない")
    assert _statuses(sink) == [StageStatus.STARTED, StageStatus.ADVANCED, StageStatus.FAILED]
    assert sink.events[-1].message == "unreadable: 画像を読めない"
    assert sink.events[-1].completed == 1
    assert info.value.kind is ErrorKind.NEEDS_CONFIG


def test_failure_keeps_exception_type_and_kind() -> None:
    """例外を包み直さないので FR-18 の 2 区分が呼出側で読める。"""
    sink = CollectingSink()
    with pytest.raises(StageError) as info, run_stage("ai_call", uses_ai=True, sink=sink):
        raise StageError("ai_call", "timeout", "応答が返らない", failure=FailureClass.TIMEOUT)
    assert info.value.retriable is True
    assert _statuses(sink)[-1] is StageStatus.FAILED


def test_other_optpoet_errors_are_reported_as_failed() -> None:
    sink = CollectingSink()
    with pytest.raises(StorageError), run_stage("render", sink=sink):
        raise StorageError("実体を置けない")
    assert _statuses(sink)[-1] is StageStatus.FAILED
    assert sink.events[-1].message == "実体を置けない"


def test_unexpected_exception_is_reported_and_reraised() -> None:
    sink = CollectingSink()
    with pytest.raises(ZeroDivisionError), run_stage("optimize", sink=sink):
        raise ZeroDivisionError
    assert _statuses(sink)[-1] is StageStatus.FAILED
    assert sink.events[-1].message == "ZeroDivisionError"


def test_cancel_emits_cancelled_not_failed() -> None:
    sink = CollectingSink()
    token = CancelToken()
    with (
        pytest.raises(StageCancelledError) as info,
        run_stage("optimize", total=4, sink=sink, cancel=token) as progress,
    ):
        progress.advance()
        token.cancel()
        progress.advance()
    assert _statuses(sink) == [StageStatus.STARTED, StageStatus.ADVANCED, StageStatus.CANCELLED]
    assert sink.events[-1].completed == 1
    assert info.value.completed == 1


def test_cancel_before_body_skips_work() -> None:
    sink = CollectingSink()
    token = CancelToken()
    token.cancel()
    entered = False
    with pytest.raises(StageCancelledError), run_stage("optimize", sink=sink, cancel=token):
        entered = True
    assert entered is False
    assert _statuses(sink) == [StageStatus.STARTED, StageStatus.CANCELLED]


def test_cancelled_note_is_carried_to_event() -> None:
    sink = CollectingSink()
    with pytest.raises(StageCancelledError), run_stage("optimize", sink=sink):
        raise StageCancelledError("optimize", completed=2, note="作者操作")
    assert sink.events[-1].message == "作者操作"


def test_runs_without_sink_or_token() -> None:
    with run_stage(Stage.NORMALIZE) as progress:
        progress.advance()
    assert progress.completed == 1
