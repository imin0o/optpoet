"""原子的保存と直前の有効版の保持。

docs/decisions/save-and-migration.md 2 節 A-01〜A-11 の実装。

コミット点は `manifest.json` の置換 1 点のみ。実体は内容アドレスで不変なので、保存は
「実体の追記」と「manifest の 1 回の置換」に分解できる。実体の追記（A-01〜A-03）は
`optpoet.storage.cache` の `store` が担い、本モジュールは A-04 以降を担う。

保存は「成功」か「何も変わっていない」かのどちらかになる。途中で失敗した場合は以降を
実行せず `.tmp/` を破棄して中止し、残るのは直前の有効版であって書きかけの新版ではない。
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from optpoet.errors import SaveAbortedError, StorageError
from optpoet.manifest.store import prepare_manifest, serialize_manifest
from optpoet.manifest.validate import validate_manifest
from optpoet.storage.atomic import replace, sync_dir, write_and_sync
from optpoet.storage.layout import MANIFEST_NAME, ProjectLayout
from optpoet.storage.refs import verify_refs


@dataclass(frozen=True, slots=True)
class SaveResult:
    """コミット済みの保存結果。"""

    manifest_path: Path
    backup_path: Path | None
    """退避した直前の有効版。初回保存では退避元がないため None。"""
    verified_refs: int
    """A-04 で実体とハッシュを照合した ref 数。"""
    index_updated: bool
    index_error: str | None
    """索引更新の失敗理由。索引は派生なので、失敗しても保存は成功（A-10）。"""


def save_project(
    layout: ProjectLayout,
    data: Mapping[str, Any],
    *,
    updated_at: str | None = None,
    update_index: Callable[[], None] | None = None,
) -> SaveResult:
    """A-04〜A-11 を順に実行し、`manifest.json` の置換 1 点でコミットする。

    `updated_at` の生成は呼び出し側の責務とし、保存を決定的に保つ。`update_index` は
    `index.sqlite` の更新フック（A-10）で、失敗しても保存は成功として扱う。
    """
    staged = layout.tmp_dir / MANIFEST_NAME
    try:
        payload = prepare_manifest(data, updated_at=updated_at)
        verified = verify_refs(payload, layout)
        write_and_sync(staged, serialize_manifest(payload))
        _validate_staged(staged)
        backup = _backup_current(layout)
    except Exception:
        # A-04〜A-07 の失敗。中間状態を残さず、旧版をそのまま有効版として残す。
        layout.clear_tmp()
        raise
    _commit(layout, staged, backup)
    sync_dir(layout.root)
    index_updated, index_error = _update_index(update_index)
    layout.clear_tmp()
    return SaveResult(
        manifest_path=layout.manifest_path,
        backup_path=backup,
        verified_refs=verified,
        index_updated=index_updated,
        index_error=index_error,
    )


def _validate_staged(staged: Path) -> None:
    """A-06: 正の位置へ置く前に、書き出したバイト列を読み直して検証する。

    メモリ上の値ではなく実ファイルを検証するのは、直列化で失われた項目もここで捕まえる
    ため。検証を通らない manifest を正の位置へ一度も置かない。
    """
    try:
        reloaded = json.loads(staged.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise SaveAbortedError(f"書き出した manifest を読み直せない: {staged}") from exc
    if not isinstance(reloaded, dict):
        raise SaveAbortedError(f"書き出した manifest がオブジェクトでない: {staged}")
    validate_manifest(reloaded)


def _backup_current(layout: ProjectLayout) -> Path | None:
    """A-07: 現行 manifest を 1 世代だけ退避する。実体は不変なので 1 世代で足りる。"""
    if not layout.manifest_path.is_file():
        return None
    replace(layout.manifest_path, layout.manifest_backup_path)
    return layout.manifest_backup_path


def _commit(layout: ProjectLayout, staged: Path, backup: Path | None) -> None:
    """A-08: コミット点。失敗した場合は退避した直前の有効版を正の位置へ戻す。"""
    try:
        replace(staged, layout.manifest_path)
    except StorageError as exc:
        raise _abort_commit(layout, backup, exc) from exc


def _abort_commit(
    layout: ProjectLayout, backup: Path | None, exc: StorageError
) -> SaveAbortedError:
    """R-03（`manifest.json` 不在）を残さないための巻き戻し。

    プロセスが生きている間は退避元を戻せる。戻せた場合は保存前と同じ状態になる。
    """
    if backup is None:
        return SaveAbortedError(f"manifest を置換できない: {exc}")
    try:
        replace(backup, layout.manifest_path)
    except StorageError:
        return SaveAbortedError(
            f"manifest を置換できず、直前の有効版も戻せない: {exc}"
            f"（{layout.manifest_backup_path.name} から復旧できる）"
        )
    return SaveAbortedError(f"manifest を置換できない。直前の有効版へ戻した: {exc}")


def _update_index(update_index: Callable[[], None] | None) -> tuple[bool, str | None]:
    """A-10: 索引は manifest から再構築できる派生。失敗を保存の失敗にしない。"""
    if update_index is None:
        return False, None
    try:
        update_index()
    except Exception as exc:
        # 索引の失敗理由は保存結果へ載せるだけ。呼び出し側が再構築を判断する。
        return False, str(exc)
    return True, None
