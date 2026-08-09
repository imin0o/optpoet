"""最適化トレース（P1-037 / FR-09 第 5 段階）。

「初期草稿、候補、採否、評価値を追跡可能にする」ため、局所探索が評価した候補を 1 件ずつ
記録する。記録は探索の再現ではなく **説明** が目的で、どの位置でどの候補をなぜ採った／
採らなかったかを後から読めるようにする。

件数は本文長 × 候補数に比例して増えるため、`max_entries` で上限を設ける。打ち切った場合も
`evaluated`（評価した総数）は数え続け、`truncated` で打ち切りを明示する。黙って減らさない。

実体は `Stage.OPTIMIZE` のキャッシュ配置（`trace/`）へ置き、manifest の
`optimization.trace_ref` から参照する（artifact-storage.md）。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from optpoet.hashing import FLOAT_DIGITS, canonical_json
from optpoet.storage import Stage, cache_key

TRACE_SCHEMA_VERSION = "1.0"
TRACE_STAGE_VERSION = 1
"""トレースの記録規則を変えたら上げる（docs/decisions/change-management.md）。"""

DEFAULT_MAX_ENTRIES = 10_000


@dataclass(frozen=True, slots=True)
class TraceEntry:
    """1 候補分の評価。`error_before` / `error_after` は当該セルの絶対誤差。"""

    iteration: int
    index: int
    char: str
    candidate: str
    error_before: float
    error_after: float
    accepted: bool

    @property
    def gain(self) -> float:
        """採用した場合に減る誤差。負なら悪化する候補。"""
        return self.error_before - self.error_after

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration,
            "index": self.index,
            "char": self.char,
            "candidate": self.candidate,
            "error_before": round(self.error_before, FLOAT_DIGITS),
            "error_after": round(self.error_after, FLOAT_DIGITS),
            "accepted": self.accepted,
        }


class OptimizationTrace:
    """探索中に候補と採否を集める。工程はこれだけを触る。"""

    __slots__ = ("_entries", "_evaluated", "max_entries", "params")

    def __init__(
        self,
        *,
        params: Mapping[str, Any] | None = None,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ) -> None:
        self.params: dict[str, Any] = dict(params or {})
        self.max_entries = max_entries
        self._entries: list[TraceEntry] = []
        self._evaluated = 0

    @property
    def entries(self) -> tuple[TraceEntry, ...]:
        return tuple(self._entries)

    @property
    def evaluated(self) -> int:
        """評価した候補の総数。上限で打ち切った分も含む。"""
        return self._evaluated

    @property
    def accepted(self) -> int:
        return sum(1 for entry in self._entries if entry.accepted)

    @property
    def truncated(self) -> bool:
        return self._evaluated > len(self._entries)

    def record(self, entry: TraceEntry) -> None:
        """候補 1 件を記録する。上限を超えた分は保持しないが数える。"""
        self._evaluated += 1
        if len(self._entries) < self.max_entries:
            self._entries.append(entry)

    def to_dict(self) -> dict[str, Any]:
        """トレース実体の内容。"""
        return {
            "schema_version": TRACE_SCHEMA_VERSION,
            "params": self.params,
            "evaluated": self._evaluated,
            "accepted": self.accepted,
            "truncated": self.truncated,
            "max_entries": self.max_entries,
            "entries": [entry.to_dict() for entry in self._entries],
        }

    def to_bytes(self) -> bytes:
        """トレース実体のバイト列。キャッシュ配置と内容ハッシュはこれを対象にする。"""
        return canonical_json(self.to_dict())

    def cache_key(self, *, inputs: Sequence[str] = ()) -> str:
        """トレースの配置キー。`inputs` は密度マップと辞書の内容ハッシュを渡す。"""
        return cache_key(
            Stage.OPTIMIZE,
            stage_version=TRACE_STAGE_VERSION,
            inputs=inputs,
            params=self.params,
        )
