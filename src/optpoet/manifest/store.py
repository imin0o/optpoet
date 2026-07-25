"""project manifest の読込と保存。

保存は `manifest.json` を直接書く。原子的保存（`.tmp/` への書込みと置換、直前の有効版の
保持）は P1-004 で本モジュールの上に載せる（docs/decisions/save-and-migration.md）。
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from optpoet.errors import ManifestError
from optpoet.manifest.validate import validate_manifest
from optpoet.manifest.version import APP_SCHEMA_VERSION, SchemaVersion, is_read_only


@dataclass(frozen=True, slots=True)
class LoadedManifest:
    """読込済みの manifest。`read_only` なら上書き保存しない。"""

    data: Mapping[str, Any]
    schema_version: SchemaVersion
    read_only: bool


def load_manifest(path: Path) -> LoadedManifest:
    """manifest を読み、スキーマ版を判定して検証する。

    MINOR がアプリより新しい場合は読取専用オープンとし、未知項目を保持したまま返す。
    """
    data = _read_json(path)
    version = SchemaVersion.parse(_schema_version_of(data))
    read_only = is_read_only(version)
    validate_manifest(data, allow_unknown=read_only)
    return LoadedManifest(data=data, schema_version=version, read_only=read_only)


def save_manifest(
    data: Mapping[str, Any],
    path: Path,
    *,
    updated_at: str | None = None,
) -> None:
    """manifest を検証してから書き出す。

    `updated_at` を渡すと `manifest.updated_at` を差し替える。時刻の生成は呼び出し側の
    責務とし、保存を決定的に保つ。読取専用オープンに相当する版は保存を拒否する。
    """
    version = SchemaVersion.parse(_schema_version_of(data))
    if is_read_only(version):
        raise ManifestError(
            f"読取専用オープンの版は保存できない: {version}（対応: {APP_SCHEMA_VERSION}）"
        )
    payload: dict[str, Any] = dict(data)
    if updated_at is not None:
        payload["manifest"] = {**payload["manifest"], "updated_at": updated_at}
    validate_manifest(payload)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(f"manifest を読めない: {path}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifest の JSON が不正: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError(f"manifest はオブジェクトである必要がある: {path}")
    return data


def _schema_version_of(data: Mapping[str, Any]) -> object:
    block = data.get("manifest")
    if not isinstance(block, dict) or "schema_version" not in block:
        raise ManifestError("manifest.schema_version がない（I-01）")
    return block["schema_version"]
