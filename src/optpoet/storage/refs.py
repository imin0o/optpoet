"""manifest の ref 健全性検証（I-02）。

docs/decisions/project-manifest.md I-02: すべての ref の `path` が存在し `hash` が一致する
こと。不一致は破損として報告し、暗黙に再生成しない。

構造検証（層 A）と I-07 は P1-002 の `optpoet.manifest.validate` が担う。本モジュールは
ファイルシステムを読む検証だけを扱うため、読込時に常に走らせるかは呼び出し側が決める
（全 ref の SHA-256 照合は NFR-04 の読込時間へ影響しうる）。
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from optpoet.errors import ArtifactCorruptedError, ManifestError
from optpoet.hashing import hash_file, parse_hash
from optpoet.storage.layout import ProjectLayout


def iter_refs(data: Mapping[str, Any]) -> Iterator[tuple[str, Mapping[str, Any]]]:
    """manifest 内の ref を（位置ラベル, ref）で走査する。

    ref は `path` と `hash` を併せ持つオブジェクトとして識別する。
    """
    yield from _walk(data, "")


def verify_refs(data: Mapping[str, Any], layout: ProjectLayout) -> int:
    """全 ref の実体存在と内容ハッシュ一致を検証し、検証した ref 数を返す。"""
    count = 0
    for label, ref in iter_refs(data):
        verify_ref(label, ref, layout)
        count += 1
    return count


def verify_ref(label: str, ref: Mapping[str, Any], layout: ProjectLayout) -> None:
    """単一 ref の実体を検証する。"""
    relative = ref["path"]
    if not isinstance(relative, str):
        raise ManifestError(f"{label}.path は文字列: {relative!r}")
    expected = parse_hash(ref["hash"])
    path = layout.resolve(relative)
    if not path.is_file():
        raise ManifestError(f"参照先の実体がない（I-02）: {label}.path = {relative}")
    _check_size(label, ref, path)
    actual = hash_file(path)
    if actual != expected:
        raise ArtifactCorruptedError(
            f"実体の内容ハッシュが manifest と一致しない（I-02）: {label}.path = {relative}"
        )


def _check_size(label: str, ref: Mapping[str, Any], path: Path) -> None:
    """`bytes` があればサイズを先に見る。大きい実体の不一致を安く検出する。"""
    declared = ref.get("bytes")
    if not isinstance(declared, int) or isinstance(declared, bool):
        return
    actual = path.stat().st_size
    if actual != declared:
        raise ArtifactCorruptedError(
            f"実体のサイズが manifest と一致しない（I-02）: {label}.bytes = {declared}"
            f"（実測 {actual}）"
        )


def _walk(value: object, path: str) -> Iterator[tuple[str, Mapping[str, Any]]]:
    if isinstance(value, Mapping):
        if "path" in value and "hash" in value:
            yield path or "manifest 全体", value
        for key, item in value.items():
            yield from _walk(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}[{index}]")
