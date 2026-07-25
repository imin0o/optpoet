"""manifest の構造検証（層 A）と不変条件の呼び出し。

層 A は docs/decisions/secret-exclusion-test.md の D-01（未知キー禁止）と D-02（禁止キー名）、
および docs/decisions/project-manifest.md の I-07（相対パス）を検査する。値パターン検査
（層 B、D-03〜D-07）は保存時には実行しない（同 docs「実行タイミング」）。
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from optpoet.errors import ManifestError
from optpoet.manifest.invariants import check_invariants
from optpoet.manifest.schema import (
    FORBIDDEN_KEY_NAMES,
    MANIFEST_SPEC,
    Arr,
    Free,
    Node,
    normalize_key,
)

_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")


def validate_manifest(data: Mapping[str, Any], *, allow_unknown: bool = False) -> None:
    """manifest の構造と、内部だけで判定できる不変条件を検証する。

    `allow_unknown` は読取専用オープン（MINOR がアプリより新しい）で使う。未知項目を
    破棄せず保持するため、未知キーを拒否しない（project-manifest.md「未知項目の保持」）。
    禁止キー名と I-07 は読取モードに関わらず常に検査する。

    I-02 参照健全性（`path` の存在と `hash` 一致）は内容ハッシュ（P1-003）が必要なため
    本関数では扱わない。
    """
    _walk(MANIFEST_SPEC, data, "", allow_unknown=allow_unknown)
    _check_keys(data, "")
    check_invariants(data)


def _walk(node: Node, value: object, path: str, *, allow_unknown: bool) -> None:
    if isinstance(node, Free):
        return
    if isinstance(node, Arr):
        if not isinstance(value, list):
            raise ManifestError(f"{_label(path)} は配列である必要がある")
        for index, item in enumerate(value):
            _walk(node.item, item, f"{path}[{index}]", allow_unknown=allow_unknown)
        return
    if not isinstance(value, dict):
        raise ManifestError(f"{_label(path)} はオブジェクトである必要がある")
    for name, child in node.required.items():
        if name not in value:
            raise ManifestError(f"必須項目がない: {_join(path, name)}")
        _walk(child, value[name], _join(path, name), allow_unknown=allow_unknown)
    for name, item in value.items():
        if name in node.required:
            continue
        optional = node.optional.get(name)
        if optional is None:
            if allow_unknown:
                continue
            raise ManifestError(f"未知の項目: {_join(path, name)}")
        _walk(optional, item, _join(path, name), allow_unknown=allow_unknown)


def _check_keys(value: object, path: str) -> None:
    """全深度でキー名（D-02）と `path` の相対性（I-07）を検査する。"""
    if isinstance(value, dict):
        for name, item in value.items():
            child = _join(path, str(name))
            if normalize_key(str(name)) in FORBIDDEN_KEY_NAMES:
                raise ManifestError(f"秘密情報を示すキー名は保存できない: {child}")
            if name == "path" and isinstance(item, str):
                _check_relative_path(item, child)
            _check_keys(item, child)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _check_keys(item, f"{path}[{index}]")


def _check_relative_path(value: str, path: str) -> None:
    """I-07: 絶対パス・端末固有パス・親ディレクトリ脱出を拒否する。"""
    if not value:
        raise ManifestError(f"{path} が空")
    if value.startswith(("/", "\\", "~")) or _DRIVE_PREFIX.match(value):
        raise ManifestError(f"{path} は相対パスである必要がある（I-07）: {value!r}")
    if "\\" in value:
        # 区切りは POSIX の `/` 固定（artifact-storage.md）。
        raise ManifestError(f"{path} の区切りは / である必要がある（I-07）: {value!r}")
    parts = value.split("/")
    if ".." in parts or "" in parts:
        raise ManifestError(f"{path} が不正な要素を含む（I-07）: {value!r}")


def _join(path: str, name: str) -> str:
    return f"{path}.{name}" if path else name


def _label(path: str) -> str:
    return path or "manifest 全体"
