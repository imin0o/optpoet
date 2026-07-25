"""起動時のオープン判定と直前の有効版からの復旧提示。

docs/decisions/save-and-migration.md 3 節 R-01〜R-05 の実装。

`manifest.json` が存在し検証を通れば通常オープン（R-01 / R-02 / R-04 / R-05）。存在しない
か検証に失敗した場合のみ `manifest.bak.json` を評価し、健全ならば復旧提示とする（R-03）。
自動で書き戻さない。両方が失敗した場合はプロジェクトを開かず、実体が無傷であることを
伝える。空の manifest を新規作成して上書きしない。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from optpoet.errors import ManifestError, ManifestSchemaVersionError
from optpoet.manifest.store import LoadedManifest, load_manifest
from optpoet.storage.layout import ProjectLayout


class OpenMode(StrEnum):
    """オープンの種類。"""

    NORMAL = "normal"
    RECOVERY = "recovery"
    """`manifest.bak.json` からの復旧提示中。確定は作者の明示操作（O-02）。"""


@dataclass(frozen=True, slots=True)
class OpenedProject:
    """開いたプロジェクトと、作者へ提示すべき状態。"""

    mode: OpenMode
    manifest: LoadedManifest
    source_path: Path
    read_only: bool
    tmp_residue: tuple[str, ...]
    """`.tmp/` の残留物。破棄前に層 B の値パターン走査を要求するため破棄しない。"""
    reason: str | None
    """復旧提示の理由（`manifest.json` を使えなかった理由）。通常オープンでは None。"""


def open_project(layout: ProjectLayout) -> OpenedProject:
    """R-01〜R-05 の判定順序でプロジェクトを開く。

    異なる MAJOR は復旧提示の対象ではなく明示エラーとして送出する（4 節）。
    """
    residue = _tmp_residue(layout)
    primary = _try_load(layout.manifest_path)
    if isinstance(primary, LoadedManifest):
        return OpenedProject(
            mode=OpenMode.NORMAL,
            manifest=primary,
            source_path=layout.manifest_path,
            read_only=primary.read_only,
            tmp_residue=residue,
            reason=None,
        )
    backup = _try_load(layout.manifest_backup_path)
    if isinstance(backup, LoadedManifest):
        # 復旧を確定するまで書込みを禁じる（O-02）。自動で書き戻さない。
        return OpenedProject(
            mode=OpenMode.RECOVERY,
            manifest=backup,
            source_path=layout.manifest_backup_path,
            read_only=True,
            tmp_residue=residue,
            reason=primary,
        )
    raise ManifestError(
        "manifest が両方とも使えないためプロジェクトを開けない。実体は無傷であり、"
        "孤児からの手動復旧ができる"
        f"（{layout.manifest_path.name}: {primary} / {layout.manifest_backup_path.name}: {backup}）"
    )


def _try_load(path: Path) -> LoadedManifest | str:
    """読めた manifest、または読めなかった理由を返す。"""
    if not path.is_file():
        return "ファイルがない"
    try:
        return load_manifest(path)
    except ManifestSchemaVersionError:
        # 未知 MAJOR は構造の意味が変わっており、閲覧すら誤読になりうる。
        raise
    except ManifestError as exc:
        return str(exc)


def _tmp_residue(layout: ProjectLayout) -> tuple[str, ...]:
    if not layout.tmp_dir.is_dir():
        return ()
    return tuple(sorted(entry.name for entry in layout.tmp_dir.iterdir()))
