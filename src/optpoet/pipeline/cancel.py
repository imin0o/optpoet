"""作者操作による中断（取消）の伝達。

FR-18: 作者は生成を中断でき、完了済み中間生成物を失わない。中断は
docs/decisions/ai-failure-responses.md の失敗クラスとは別経路で、再試行・degrade の
対象にしない。

取消は協調的に働く。工程は安全な区切りで `raise_if_cancelled` を呼び、そこまでの
成果物を残したまま `StageCancelledError` で抜ける。UI 側の取消操作
（docs/environment/local-ui.md の `cancels=`）は `cancel()` を呼ぶ。
"""

from __future__ import annotations

import threading

from optpoet.errors import StageCancelledError


class CancelToken:
    """取消要求のフラグ。工程を実行するスレッドと UI スレッドで共有できる。"""

    __slots__ = ("_event",)

    def __init__(self) -> None:
        self._event = threading.Event()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        """取消を要求する。実際の停止は工程が次の区切りで行う。"""
        self._event.set()

    def wait(self, timeout: float | None = None) -> bool:
        """取消されるまで待つ。外部呼出の待機を取消可能にする用途で使う。"""
        return self._event.wait(timeout)

    def raise_if_cancelled(
        self,
        stage: str,
        *,
        completed: int = 0,
        note: str | None = None,
    ) -> None:
        """取消要求があれば `StageCancelledError` を投げる。無ければ何もしない。"""
        if self._event.is_set():
            raise StageCancelledError(stage, completed=completed, note=note)
