"""工程の実行枠。進捗通知・取消確認・失敗通知を 1 か所に集める。

各工程は次の形で書く。工程本体は進捗と取消だけを扱い、開始・完了・失敗・中断の
通知は本モジュールが行う（FR-18）。

    with run_stage(Stage.DENSITY_MAP, total=grid.cells, sink=sink, cancel=token) as p:
        for cell in cells:
            p.advance()

失敗と中断は区別して通知し、例外はそのまま呼出側へ伝える。ここで例外型を書き換えると
FR-18 の 2 区分（再試行可能 / 設定修正が必要）が失われるため、包み直さない。
中断時は完了済みの中間生成物を保持したまま抜ける。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from optpoet.errors import StageCancelledError, StageError
from optpoet.pipeline.cancel import CancelToken
from optpoet.pipeline.progress import ProgressSink, StageProgress, StageStatus, null_sink


@contextmanager
def run_stage(
    stage: str,
    *,
    total: int | None = None,
    uses_ai: bool = False,
    sink: ProgressSink = null_sink,
    cancel: CancelToken | None = None,
) -> Iterator[StageProgress]:
    """1 工程を実行し、開始・完了・失敗・中断を通知する。

    `stage` は工程 ID（`optpoet.storage.Stage` をそのまま渡せる）。`uses_ai` は外部 AI を
    呼ぶ工程で True にし、UI が送信の有無を提示できるようにする（X-05 / FR-18）。
    開始時点で取消済みなら本体を実行しない。
    """
    progress = StageProgress(stage, total=total, uses_ai=uses_ai, sink=sink, cancel=cancel)
    progress.emit(StageStatus.STARTED)
    try:
        progress.check_cancelled()
        yield progress
    except StageCancelledError as exc:
        progress.emit(StageStatus.CANCELLED, message=exc.note)
        raise
    except Exception as exc:
        progress.emit(StageStatus.FAILED, message=_failure_message(exc))
        raise
    progress.finish()


def _failure_message(exc: Exception) -> str:
    """進捗イベントへ載せる短い失敗文。構造化情報は例外側が持つ。"""
    if isinstance(exc, StageError):
        return f"{exc.code}: {exc.detail}"
    return str(exc) or type(exc).__name__
