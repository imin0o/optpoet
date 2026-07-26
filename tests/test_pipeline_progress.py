"""工程別進捗の通知と取消確認の検証（FR-18）。"""

from __future__ import annotations

import pytest

from optpoet.errors import StageCancelledError
from optpoet.pipeline import (
    CancelToken,
    CollectingSink,
    ProgressEvent,
    StageProgress,
    StageStatus,
)
from optpoet.storage import Stage


def test_progress_event_ratio() -> None:
    event = ProgressEvent(stage="density_map", status=StageStatus.ADVANCED, completed=1, total=4)
    assert event.ratio == 0.25


def test_progress_event_ratio_is_none_without_total() -> None:
    """事前に処理量を数えられない工程は割合を出さない。"""
    event = ProgressEvent(stage="optimize", status=StageStatus.ADVANCED, completed=7)
    assert event.ratio is None


def test_progress_event_ratio_is_capped() -> None:
    event = ProgressEvent(stage="optimize", status=StageStatus.ADVANCED, completed=9, total=4)
    assert event.ratio == 1.0


def test_advance_emits_events() -> None:
    sink = CollectingSink()
    progress = StageProgress(Stage.DENSITY_MAP, total=2, sink=sink)
    progress.advance()
    progress.advance(message="残り 1")
    assert [(e.completed, e.message) for e in sink.events] == [(1, None), (2, "残り 1")]
    assert {e.status for e in sink.events} == {StageStatus.ADVANCED}
    assert sink.events[0].stage == "density_map"
    assert sink.events[0].total == 2


def test_advance_accepts_step() -> None:
    sink = CollectingSink()
    progress = StageProgress("optimize", sink=sink)
    progress.advance(5)
    assert progress.completed == 5


def test_report_sets_absolute_count() -> None:
    sink = CollectingSink()
    progress = StageProgress("optimize", total=100, sink=sink)
    progress.report(40)
    assert progress.completed == 40
    assert sink.events[-1].ratio == 0.4


def test_uses_ai_is_carried_on_events() -> None:
    """外部 AI 利用の有無を UI が提示できる（X-05 / FR-18）。"""
    sink = CollectingSink()
    progress = StageProgress("ai_call", uses_ai=True, sink=sink)
    progress.advance()
    assert sink.events[-1].uses_ai is True


def test_finish_fills_total() -> None:
    sink = CollectingSink()
    progress = StageProgress("render", total=10, sink=sink)
    progress.advance()
    progress.finish()
    assert sink.events[-1].status is StageStatus.COMPLETED
    assert sink.events[-1].completed == 10


def test_finish_keeps_count_without_total() -> None:
    sink = CollectingSink()
    progress = StageProgress("optimize", sink=sink)
    progress.advance(3)
    progress.finish()
    assert sink.events[-1].completed == 3


def test_advance_stops_on_cancel_with_completed_count() -> None:
    """取消後は進めず、そこまでの完了数を中断へ載せる。"""
    sink = CollectingSink()
    token = CancelToken()
    progress = StageProgress("optimize", total=3, sink=sink, cancel=token)
    progress.advance()
    token.cancel()
    with pytest.raises(StageCancelledError) as info:
        progress.advance()
    assert info.value.completed == 1
    assert progress.completed == 1
    assert len(sink.events) == 1


def test_check_cancelled_passes_without_request() -> None:
    progress = StageProgress("optimize", cancel=CancelToken())
    progress.check_cancelled()


def test_progress_without_sink_does_not_fail() -> None:
    progress = StageProgress("optimize")
    progress.advance()
    progress.finish()
    assert progress.completed == 1
