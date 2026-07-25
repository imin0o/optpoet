"""起動時のオープン判定 R-01〜R-05 と復旧提示の検証。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from optpoet.errors import ManifestError, ManifestSchemaVersionError
from optpoet.project import OpenMode, open_project, save_project
from optpoet.storage import ProjectLayout


def _write(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def saved(materialized_manifest: dict[str, Any], project_layout: ProjectLayout) -> dict[str, Any]:
    save_project(project_layout, materialized_manifest)
    return materialized_manifest


def test_normal_open(saved: dict[str, Any], project_layout: ProjectLayout) -> None:
    opened = open_project(project_layout)
    assert opened.mode is OpenMode.NORMAL
    assert opened.source_path == project_layout.manifest_path
    assert not opened.read_only
    assert opened.reason is None


def test_open_marks_newer_minor_read_only(
    saved: dict[str, Any], project_layout: ProjectLayout
) -> None:
    """O-01: 新しい MINOR は通常オープンではなく読取専用オープン。"""
    saved["manifest"]["schema_version"] = "1.1"
    _write(project_layout.manifest_path, saved)
    opened = open_project(project_layout)
    assert opened.mode is OpenMode.NORMAL
    assert opened.read_only


def test_open_offers_recovery_when_manifest_missing(
    saved: dict[str, Any], project_layout: ProjectLayout
) -> None:
    """R-03: A-07 直後に落ちた状態。`manifest.bak.json` から復旧を提示する。"""
    save_project(project_layout, saved, updated_at="2026-07-26T00:00:00.000Z")
    project_layout.manifest_path.unlink()
    opened = open_project(project_layout)
    assert opened.mode is OpenMode.RECOVERY
    assert opened.source_path == project_layout.manifest_backup_path
    assert opened.read_only
    assert opened.reason == "ファイルがない"


def test_open_does_not_write_back(saved: dict[str, Any], project_layout: ProjectLayout) -> None:
    """復旧は作者の明示操作で確定する。自動で書き戻さない。"""
    save_project(project_layout, saved, updated_at="2026-07-26T00:00:00.000Z")
    project_layout.manifest_path.unlink()
    open_project(project_layout)
    assert not project_layout.manifest_path.exists()
    assert project_layout.manifest_backup_path.is_file()


def test_open_offers_recovery_when_manifest_broken(
    saved: dict[str, Any], project_layout: ProjectLayout
) -> None:
    save_project(project_layout, saved, updated_at="2026-07-26T00:00:00.000Z")
    project_layout.manifest_path.write_text("{ broken", encoding="utf-8")
    opened = open_project(project_layout)
    assert opened.mode is OpenMode.RECOVERY
    assert opened.reason is not None
    assert "JSON" in opened.reason


def test_open_reports_tmp_residue_without_discarding(
    saved: dict[str, Any], project_layout: ProjectLayout
) -> None:
    """R-01 / R-04: 残留物は報告する。破棄前に層 B の走査を要求するため消さない。"""
    (project_layout.tmp_dir / "density.ab12.npy.part").write_bytes(b"partial")
    opened = open_project(project_layout)
    assert opened.tmp_residue == ("density.ab12.npy.part",)
    assert (project_layout.tmp_dir / "density.ab12.npy.part").is_file()


def test_open_reports_no_residue_after_clean_save(
    saved: dict[str, Any], project_layout: ProjectLayout
) -> None:
    assert open_project(project_layout).tmp_residue == ()


def test_open_fails_when_both_manifests_unusable(
    saved: dict[str, Any], project_layout: ProjectLayout
) -> None:
    """空の manifest を新規作成して上書きしない。"""
    save_project(project_layout, saved, updated_at="2026-07-26T00:00:00.000Z")
    project_layout.manifest_path.write_text("{ broken", encoding="utf-8")
    project_layout.manifest_backup_path.write_text("{ broken", encoding="utf-8")
    with pytest.raises(ManifestError, match="実体は無傷"):
        open_project(project_layout)


def test_open_fails_when_manifest_absent(project_layout: ProjectLayout) -> None:
    with pytest.raises(ManifestError, match="プロジェクトを開けない"):
        open_project(project_layout)


def test_open_rejects_unknown_major(saved: dict[str, Any], project_layout: ProjectLayout) -> None:
    """異なる MAJOR は復旧提示に落とさず明示エラーにする。"""
    save_project(project_layout, saved, updated_at="2026-07-26T00:00:00.000Z")
    saved["manifest"]["schema_version"] = "2.0"
    _write(project_layout.manifest_path, saved)
    with pytest.raises(ManifestSchemaVersionError, match="未知のスキーマ MAJOR 版"):
        open_project(project_layout)
