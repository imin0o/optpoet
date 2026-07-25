"""原子的な書込みと置換のプリミティブ。

docs/decisions/save-and-migration.md 2 節の A-01〜A-03 / A-05 / A-08 / A-09 が要求する
操作だけを提供する。手順の順序と中止規則は `optpoet.project.save` が担う。

置換移動は同一ボリューム上でのみ原子的なため、一時ファイルはプロジェクトルート直下の
`.tmp/` に置く（OS の一時ディレクトリを使わない）。
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from optpoet.errors import StorageError

REPLACE_ATTEMPTS = 3
"""置換移動の試行回数。一時的なファイルロックを跨ぐための最小限。"""

REPLACE_DELAY_SECONDS = 0.05
"""再試行の間隔。実測に基づく調整は save-and-migration.md の再確認事項。"""


def write_and_sync(path: Path, data: bytes) -> None:
    """バイト列を書込み、flush してから fsync する（A-02 / A-05）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise StorageError(f"実体を書けない: {path}") from exc


def replace(source: Path, target: Path) -> None:
    """同一ボリューム上で原子的に置換移動する（A-03 / A-07 / A-08）。

    ウイルス対策ソフト等による一時的なロックで失敗しうるため短く再試行する。
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    last: OSError | None = None
    for attempt in range(REPLACE_ATTEMPTS):
        try:
            os.replace(source, target)
            return
        except OSError as exc:
            last = exc
            if attempt + 1 < REPLACE_ATTEMPTS:
                time.sleep(REPLACE_DELAY_SECONDS)
    raise StorageError(f"置換移動に失敗した: {source} -> {target}") from last


def atomic_write(path: Path, data: bytes, *, tmp_dir: Path) -> None:
    """`.tmp/` へ書いて fsync してから最終パスへ置換する（A-01〜A-03）。"""
    staged = tmp_dir / staged_name(path)
    write_and_sync(staged, data)
    replace(staged, path)


def staged_name(path: Path) -> str:
    """`.tmp/` 内で衝突しない一時名。親ディレクトリ名を前置する。"""
    return f"{path.parent.name}.{path.name}.part"


def sync_dir(path: Path) -> None:
    """ディレクトリエントリを同期する（A-09）。対応しない OS では何もしない。"""
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        # Windows はディレクトリを読取用に開けない。保存の失敗ではない。
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)
