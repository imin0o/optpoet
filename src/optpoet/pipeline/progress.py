"""工程別の進捗イベントと通知先。

FR-18: 各工程の進捗、外部 AI 利用の有無、概算処理量を表示する。工程は
`StageProgress` だけを触り、表示手段（UI / ログ / テスト）は `ProgressSink` で差し替える。

`total` は概算処理量（セル数、文字数、呼出回数など工程が数える単位）。事前に数えられない
工程は None のままにし、UI は割合ではなく完了数だけを出す。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from optpoet.pipeline.cancel import CancelToken


class StageStatus(StrEnum):
    """進捗イベントの種別。`FAILED` と `CANCELLED` は終端で、区別して提示する。"""

    STARTED = "started"
    ADVANCED = "advanced"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    """1 回の進捗通知。`stage` は工程 ID（`optpoet.storage.Stage` をそのまま渡せる）。"""

    stage: str
    status: StageStatus
    completed: int = 0
    total: int | None = None
    message: str | None = None
    uses_ai: bool = False

    @property
    def ratio(self) -> float | None:
        """完了割合。`total` 不明なら None。1.0 を超えない。"""
        if self.total is None or self.total <= 0:
            return None
        return min(self.completed / self.total, 1.0)


ProgressSink = Callable[[ProgressEvent], None]


def null_sink(event: ProgressEvent) -> None:
    """通知しない既定の sink。"""


class CollectingSink:
    """受け取ったイベントを順に保持する sink。テストと来歴記録に使う。"""

    __slots__ = ("events",)

    def __init__(self) -> None:
        self.events: list[ProgressEvent] = []

    def __call__(self, event: ProgressEvent) -> None:
        self.events.append(event)


class StageProgress:
    """1 工程分の進捗ハンドル。取消確認も兼ねる。

    `advance` / `report` は進捗を進める前に取消を確認する。これにより取消後に余分な
    処理を進めず、そこまでの完了数を `StageCancelledError` へ載せられる。
    """

    __slots__ = ("_cancel", "_completed", "_sink", "stage", "total", "uses_ai")

    def __init__(
        self,
        stage: str,
        *,
        total: int | None = None,
        uses_ai: bool = False,
        sink: ProgressSink = null_sink,
        cancel: CancelToken | None = None,
    ) -> None:
        self.stage = str(stage)
        self.total = total
        self.uses_ai = uses_ai
        self._sink = sink
        self._cancel = cancel
        self._completed = 0

    @property
    def completed(self) -> int:
        return self._completed

    def check_cancelled(self) -> None:
        """取消要求があれば、そこまでの完了数を添えて中断する。"""
        if self._cancel is not None:
            self._cancel.raise_if_cancelled(self.stage, completed=self._completed)

    def advance(self, step: int = 1, *, message: str | None = None) -> None:
        """完了数を `step` 進めて通知する。"""
        self.check_cancelled()
        self._completed += step
        self.emit(StageStatus.ADVANCED, message=message)

    def report(self, completed: int, *, message: str | None = None) -> None:
        """完了数を絶対値で置き換えて通知する。"""
        self.check_cancelled()
        self._completed = completed
        self.emit(StageStatus.ADVANCED, message=message)

    def emit(self, status: StageStatus, *, message: str | None = None) -> None:
        """現在の完了数で任意の種別のイベントを通知する。"""
        self._sink(
            ProgressEvent(
                stage=self.stage,
                status=status,
                completed=self._completed,
                total=self.total,
                message=message,
                uses_ai=self.uses_ai,
            )
        )

    def finish(self, *, message: str | None = None) -> None:
        """完了として通知する。`total` が既知なら完了数をそこへ揃える。"""
        if self.total is not None:
            self._completed = self.total
        self.emit(StageStatus.COMPLETED, message=message)
