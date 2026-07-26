"""取消要求の伝達の検証（FR-18: 中断で完了済み中間生成物を失わない）。"""

from __future__ import annotations

import threading

import pytest

from optpoet.errors import StageCancelledError
from optpoet.pipeline import CancelToken


def test_token_starts_not_cancelled() -> None:
    assert CancelToken().cancelled is False


def test_cancel_sets_flag() -> None:
    token = CancelToken()
    token.cancel()
    assert token.cancelled is True


def test_raise_if_cancelled_is_noop_before_cancel() -> None:
    CancelToken().raise_if_cancelled("optimize")


def test_raise_if_cancelled_reports_stage_and_progress() -> None:
    token = CancelToken()
    token.cancel()
    with pytest.raises(StageCancelledError) as info:
        token.raise_if_cancelled("optimize", completed=8, note="作者操作")
    assert info.value.stage == "optimize"
    assert info.value.completed == 8
    assert info.value.note == "作者操作"


def test_cancel_is_idempotent() -> None:
    token = CancelToken()
    token.cancel()
    token.cancel()
    assert token.cancelled is True


def test_wait_returns_false_on_timeout() -> None:
    assert CancelToken().wait(0.01) is False


def test_wait_returns_when_cancelled_from_other_thread() -> None:
    """UI スレッドからの取消を、実行中の待機が受け取れる。"""
    token = CancelToken()
    threading.Timer(0.01, token.cancel).start()
    assert token.wait(5.0) is True
