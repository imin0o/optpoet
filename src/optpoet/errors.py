"""例外の基底と、工程別の構造化エラー。

構造化エラーは requirements.md FR-18（進捗・中断・失敗）を満たすために、
**工程 ID**、**FR-18 の 2 区分**（再試行可能 / 設定修正が必要）、**作者向け対処**を
例外自身に持たせる。UI と来歴は文字列を解析せず、これらのフィールドを読む。

失敗クラスの語彙（F-TIMEOUT / F-RATELIMIT / F-AUTH / F-SERVICE）は
docs/decisions/ai-failure-responses.md に従う。中断（作者操作）は失敗ではなく、
別経路の `StageCancelledError` で表す。
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class OptpoetError(Exception):
    """optpoet が発生させる例外の基底。"""


class ConfigError(OptpoetError):
    """設定値が不正、または設定ファイルを読めない。"""


class ManifestError(OptpoetError):
    """project manifest の構造、または不変条件が不正。"""


class ManifestSchemaVersionError(ManifestError):
    """project manifest のスキーマ版を扱えない（未知 MAJOR）。"""


class StorageError(OptpoetError):
    """成果物の配置、内容ハッシュ、キャッシュキーが不正。"""


class ArtifactCorruptedError(StorageError):
    """実体があるが内容ハッシュが一致しない。暗黙に再生成しない（I-02）。"""


class SaveAbortedError(StorageError):
    """保存を中止した。書きかけの新版ではなく直前の有効版が残る。"""


class ErrorKind(StrEnum):
    """FR-18 の失敗 2 区分。UI の提示（再試行を促す / 設定修正を促す）を決める。"""

    RETRIABLE = "retriable"
    NEEDS_CONFIG = "needs_config"


class FailureClass(StrEnum):
    """外部 AI 呼出の正規化失敗クラス（ai-failure-responses.md）。"""

    TIMEOUT = "F-TIMEOUT"
    RATELIMIT = "F-RATELIMIT"
    AUTH = "F-AUTH"
    SERVICE = "F-SERVICE"

    @property
    def kind(self) -> ErrorKind:
        """F-AUTH のみ設定修正が必要。他は一過性で自動再試行の対象。"""
        if self is FailureClass.AUTH:
            return ErrorKind.NEEDS_CONFIG
        return ErrorKind.RETRIABLE


class StageError(OptpoetError):
    """工程が失敗した。工程 ID・区分・対処・失敗クラスを構造化して持つ。

    `stage` は工程 ID（`optpoet.storage.Stage` をそのまま渡せる）。`code` は工程内で
    失敗種別を識別する短い識別子で、UI のメッセージ選択と来歴の突合に使う。
    `kind` を省略した場合、`failure` があればその区分を、無ければ設定修正が必要側を
    採る（分類不明を暗黙に再試行しない）。
    """

    def __init__(
        self,
        stage: str,
        code: str,
        message: str,
        *,
        kind: ErrorKind | None = None,
        hint: str | None = None,
        failure: FailureClass | None = None,
        retry_after_ms: int | None = None,
    ) -> None:
        super().__init__(f"[{stage}/{code}] {message}")
        self.stage = str(stage)
        self.code = code
        self.detail = message
        self.failure = failure
        self.hint = hint
        self.retry_after_ms = retry_after_ms
        if kind is not None:
            self.kind = kind
        elif failure is not None:
            self.kind = failure.kind
        else:
            self.kind = ErrorKind.NEEDS_CONFIG

    @property
    def retriable(self) -> bool:
        return self.kind is ErrorKind.RETRIABLE

    def to_dict(self) -> dict[str, Any]:
        """UI 提示と来歴記録に渡す構造。値が無いフィールドは含めない。

        プロバイダーの生シグナルは秘密情報を含みうるため、ここへ入れる前に
        呼出側でマスクする（quality-and-operations.md 秘密情報要件）。
        """
        payload: dict[str, Any] = {
            "stage": self.stage,
            "code": self.code,
            "message": self.detail,
            "kind": str(self.kind),
        }
        if self.failure is not None:
            payload["failure"] = str(self.failure)
        if self.hint is not None:
            payload["hint"] = self.hint
        if self.retry_after_ms is not None:
            payload["retry_after_ms"] = self.retry_after_ms
        return payload


class StageCancelledError(OptpoetError):
    """作者操作で工程を中断した。

    失敗ではないため再試行・degrade の対象にしない。完了済みの中間生成物と設定は
    保持する（FR-18 / FR-17）。
    """

    def __init__(self, stage: str, *, completed: int = 0, note: str | None = None) -> None:
        detail = f"[{stage}] 中断した（完了 {completed}）"
        if note is not None:
            detail = f"{detail}: {note}"
        super().__init__(detail)
        self.stage = str(stage)
        self.completed = completed
        self.note = note


def error_kind(exc: BaseException) -> ErrorKind:
    """例外を FR-18 の 2 区分へ写す。

    `StageError` は自身の区分を持つ。それ以外（設定不正、manifest 不正、実体破損、
    保存中止、未分類の例外）は設定修正・作者判断が必要側に寄せ、暗黙に再試行しない。
    """
    if isinstance(exc, StageError):
        return exc.kind
    return ErrorKind.NEEDS_CONFIG
