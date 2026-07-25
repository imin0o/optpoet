"""原子的保存 A-01〜A-11 と直前の有効版の保持の検証。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from optpoet.errors import ManifestError, SaveAbortedError, StorageError
from optpoet.project import save
from optpoet.project.save import save_project
from optpoet.storage.atomic import replace as atomic_replace
from optpoet.storage.layout import ProjectLayout

_LATER = "2026-07-26T00:00:00.000Z"


def _read(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def test_first_save_commits(
    materialized_manifest: dict[str, Any], project_layout: ProjectLayout
) -> None:
    result = save_project(project_layout, materialized_manifest)
    assert result.manifest_path == project_layout.manifest_path
    assert result.backup_path is None
    assert result.verified_refs > 0
    assert _read(project_layout.manifest_path)["manifest"]["project_id"]


def test_save_clears_tmp(
    materialized_manifest: dict[str, Any], project_layout: ProjectLayout
) -> None:
    """A-11: 保存完了時に `.tmp/` を空にする。"""
    save_project(project_layout, materialized_manifest)
    assert list(project_layout.tmp_dir.iterdir()) == []


def test_save_keeps_one_backup_generation(
    materialized_manifest: dict[str, Any], project_layout: ProjectLayout
) -> None:
    """A-07: 直前の有効版を 1 世代だけ退避する。"""
    save_project(project_layout, materialized_manifest)
    first = project_layout.manifest_path.read_bytes()
    result = save_project(project_layout, materialized_manifest, updated_at=_LATER)
    assert result.backup_path == project_layout.manifest_backup_path
    assert project_layout.manifest_backup_path.read_bytes() == first
    assert _read(project_layout.manifest_path)["manifest"]["updated_at"] == _LATER


def test_save_does_not_mutate_input(
    materialized_manifest: dict[str, Any], project_layout: ProjectLayout
) -> None:
    before = materialized_manifest["manifest"]["updated_at"]
    save_project(project_layout, materialized_manifest, updated_at=_LATER)
    assert materialized_manifest["manifest"]["updated_at"] == before


def test_save_rejects_read_only_version(
    materialized_manifest: dict[str, Any], project_layout: ProjectLayout
) -> None:
    """O-01 の版は保存しない。旧版はそのまま残る。"""
    save_project(project_layout, materialized_manifest)
    committed = project_layout.manifest_path.read_bytes()
    materialized_manifest["manifest"]["schema_version"] = "1.1"
    with pytest.raises(ManifestError, match="読取専用オープンの版は保存できない"):
        save_project(project_layout, materialized_manifest)
    assert project_layout.manifest_path.read_bytes() == committed
    assert not project_layout.manifest_backup_path.exists()


def test_save_aborts_on_missing_artifact(
    materialized_manifest: dict[str, Any], project_layout: ProjectLayout
) -> None:
    """A-04: 参照実体が欠けていればコミット前に中止する。"""
    project_layout.resolve(materialized_manifest["input"]["source"]["path"]).unlink()
    with pytest.raises(ManifestError, match="参照先の実体がない"):
        save_project(project_layout, materialized_manifest)
    assert not project_layout.manifest_path.exists()
    assert list(project_layout.tmp_dir.iterdir()) == []


def test_save_aborts_on_invalid_structure(
    materialized_manifest: dict[str, Any], project_layout: ProjectLayout
) -> None:
    del materialized_manifest["grid"]
    with pytest.raises(ManifestError):
        save_project(project_layout, materialized_manifest)
    assert not project_layout.manifest_path.exists()


def test_save_aborts_when_staged_manifest_fails_validation(
    materialized_manifest: dict[str, Any],
    project_layout: ProjectLayout,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A-06: 検証を通らない manifest を正の位置へ一度も置かない。"""
    monkeypatch.setattr(save, "serialize_manifest", lambda payload: b"[]")
    with pytest.raises(SaveAbortedError, match="オブジェクトでない"):
        save_project(project_layout, materialized_manifest)
    assert not project_layout.manifest_path.exists()
    assert list(project_layout.tmp_dir.iterdir()) == []


def test_save_reports_index_update(
    materialized_manifest: dict[str, Any], project_layout: ProjectLayout
) -> None:
    calls = 0

    def update() -> None:
        nonlocal calls
        calls += 1

    result = save_project(project_layout, materialized_manifest, update_index=update)
    assert calls == 1
    assert result.index_updated
    assert result.index_error is None


def test_save_survives_index_failure(
    materialized_manifest: dict[str, Any], project_layout: ProjectLayout
) -> None:
    """A-10: 索引は manifest から再構築できる派生。失敗は保存の失敗ではない。"""

    def update() -> None:
        raise RuntimeError("index locked")

    result = save_project(project_layout, materialized_manifest, update_index=update)
    assert project_layout.manifest_path.is_file()
    assert not result.index_updated
    assert result.index_error == "index locked"


def test_commit_failure_restores_previous_version(
    materialized_manifest: dict[str, Any],
    project_layout: ProjectLayout,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A-08 が失敗しても、残るのは直前の有効版であって書きかけの新版ではない。"""
    save_project(project_layout, materialized_manifest)
    committed = project_layout.manifest_path.read_bytes()
    calls = 0

    def flaky(source: Path, target: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:  # A-07 の退避は通し、A-08 のコミットだけ失敗させる。
            raise StorageError("locked")
        atomic_replace(source, target)

    monkeypatch.setattr(save, "replace", flaky)
    with pytest.raises(SaveAbortedError, match="直前の有効版へ戻した"):
        save_project(project_layout, materialized_manifest, updated_at=_LATER)
    assert project_layout.manifest_path.read_bytes() == committed


def test_first_commit_failure_reports_abort(
    materialized_manifest: dict[str, Any],
    project_layout: ProjectLayout,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """初回保存では退避元がないため、戻す対象もない。"""

    def locked(source: Path, target: Path) -> None:
        raise StorageError("locked")

    monkeypatch.setattr(save, "replace", locked)
    with pytest.raises(SaveAbortedError, match="manifest を置換できない"):
        save_project(project_layout, materialized_manifest)
    assert not project_layout.manifest_path.exists()
