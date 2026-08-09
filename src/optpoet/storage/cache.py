"""キャッシュキーの算出と、キー由来の配置・再利用。

docs/decisions/artifact-storage.md「キャッシュキー」「ファイル命名」「再利用と無効化」に従う。

    cache_key = sha256(canonical_json({stage, stage_version, inputs, params}))

`inputs` は直前段の実体ハッシュのみを入れる。前段が変われば前段の実体ハッシュが変わり、
後段キーへ自動的に伝播する。`params` は当該工程が実際に読む値だけを含める。

`ai_call` はキャッシュキーを持たず、ai-adapter-contract.md の `request_hash` を配置キー
兼照合キーにする（`request_path` / `response_path`）。

`store` は `.tmp/` へ書いて fsync してから最終パスへ置換する（save-and-migration.md
A-01〜A-03）。既存実体は内容アドレスのため不変で、上書きしない。
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from optpoet.errors import ArtifactCorruptedError, StorageError
from optpoet.hashing import FLOAT_DIGITS, hash_bytes, hash_file, hash_json, parse_hash, short_id
from optpoet.storage.atomic import atomic_write
from optpoet.storage.layout import ProjectLayout

_EXTENSION_PATTERN = re.compile(r"^[a-z0-9]+(\.[a-z0-9]+)*$")


class Stage(StrEnum):
    """キャッシュキーを持つ工程 ID。`ai_call` は `request_hash` を使うため含めない。"""

    NORMALIZE = "normalize"
    PREPROCESS = "preprocess"
    DENSITY_MAP = "density_map"
    EDGE_MAP = "edge_map"
    DICTIONARY = "dictionary"
    TEXT = "text"
    OPTIMIZE = "optimize"
    RENDER = "render"


@dataclass(frozen=True, slots=True)
class CacheEntry:
    """配置済みの実体。`relative_path` と `hash` をそのまま manifest の ref へ書ける。"""

    path: Path
    relative_path: str
    hash: str


def cache_key(
    stage: Stage,
    *,
    stage_version: int,
    inputs: Sequence[str] = (),
    params: Mapping[str, Any] | None = None,
    float_digits: int = FLOAT_DIGITS,
) -> str:
    """工程の入力集合からキャッシュキーを導出する。

    `stage_version` は工程実装が変わって出力が変わりうるとき上げる。上げ忘れると古い
    実体が誤って再利用されるため、変更管理は docs/decisions/change-management.md に従う。
    """
    if stage_version < 1:
        raise StorageError(f"stage_version は 1 以上: {stage_version}")
    # 順序は意味を持つため整列しない（前段の並びが変われば別実体）。
    resolved = [parse_hash(value) for value in inputs]
    return hash_json(
        {
            "stage": str(stage),
            "stage_version": stage_version,
            "inputs": resolved,
            "params": dict(params or {}),
        },
        float_digits=float_digits,
    )


@dataclass(frozen=True, slots=True)
class ArtifactCache:
    """キャッシュキーで中間生成物を配置し、キー一致で再利用する。"""

    layout: ProjectLayout

    def stage_dir(self, stage: Stage) -> Path:
        match stage:
            case Stage.NORMALIZE:
                return self.layout.normalized_dir
            case Stage.PREPROCESS:
                return self.layout.preprocessed_dir
            case Stage.DENSITY_MAP | Stage.EDGE_MAP:
                return self.layout.density_dir
            case Stage.DICTIONARY:
                return self.layout.dictionary_dir
            case Stage.TEXT:
                return self.layout.text_dir
            case Stage.OPTIMIZE:
                return self.layout.trace_dir
            case Stage.RENDER:
                # 出力は固定名。追跡は manifest の `outputs.*.hash` で行う。
                raise StorageError("render の出力は固定名で、キャッシュ配置の対象ではない")

    def path_for(self, stage: Stage, key: str, extension: str) -> Path:
        """キー由来のファイルパスを返す。入力または設定が変われば別ファイルになる。"""
        return self.stage_dir(stage) / f"{short_id(key)}.{_extension(extension)}"

    def lookup(
        self,
        stage: Stage,
        key: str,
        extension: str,
        *,
        expected_hash: str | None = None,
    ) -> CacheEntry | None:
        """実体があれば内容ハッシュ付きで返す。無ければ None を返す。

        `expected_hash`（manifest の ref に記録済みの値）と一致しない場合は破損として
        報告し、暗黙に再生成しない（I-02）。
        """
        path = self.path_for(stage, key, extension)
        if not path.is_file():
            return None
        actual = hash_file(path)
        if expected_hash is not None and actual != parse_hash(expected_hash):
            raise ArtifactCorruptedError(
                f"実体の内容ハッシュが記録と一致しない: {self.layout.relative(path)}"
            )
        return self._entry(path, actual)

    def store(self, stage: Stage, key: str, extension: str, data: bytes) -> CacheEntry:
        """実体を `.tmp/` 経由で配置する。同一キーの既存実体は上書きしない。

        既存実体の内容が異なる場合は、キー衝突か `stage_version` の上げ忘れであり、
        破損として報告する。
        """
        path = self.path_for(stage, key, extension)
        digest = hash_bytes(data)
        if path.is_file():
            existing = hash_file(path)
            if existing != digest:
                raise ArtifactCorruptedError(
                    f"同一キーで内容が異なる実体がある: {self.layout.relative(path)}"
                )
            return self._entry(path, existing)
        atomic_write(path, data, tmp_dir=self.layout.tmp_dir)
        return self._entry(path, digest)

    def request_path(self, request_hash: str) -> Path:
        return self.layout.requests_dir / f"{short_id(request_hash)}.req.json"

    def response_path(self, request_hash: str, attempt: int) -> Path:
        """試行連番付きの応答パス。失敗応答を上書きしないため連番を必須にする。"""
        if attempt < 1:
            raise StorageError(f"試行連番は 1 以上: {attempt}")
        return self.layout.responses_dir / f"{short_id(request_hash)}.a{attempt}.res.json"

    def _entry(self, path: Path, digest: str) -> CacheEntry:
        return CacheEntry(path=path, relative_path=self.layout.relative(path), hash=digest)


def _extension(extension: str) -> str:
    normalized = extension.removeprefix(".")
    if not _EXTENSION_PATTERN.match(normalized):
        raise StorageError(f"拡張子は小文字英数と . のみ: {extension!r}")
    return normalized
