"""工程共通の進捗・取消・実行枠。

requirements.md FR-18（進捗・中断・失敗）の実装。構造化エラーは
`optpoet.errors`（`StageError` / `ErrorKind` / `FailureClass`）に置く。
"""

from optpoet.pipeline.cancel import CancelToken
from optpoet.pipeline.progress import (
    CollectingSink,
    ProgressEvent,
    ProgressSink,
    StageProgress,
    StageStatus,
    null_sink,
)
from optpoet.pipeline.runner import run_stage

__all__ = [
    "CancelToken",
    "CollectingSink",
    "ProgressEvent",
    "ProgressSink",
    "StageProgress",
    "StageStatus",
    "null_sink",
    "run_stage",
]
