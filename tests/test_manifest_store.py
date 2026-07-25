"""manifest の読込・保存とスキーマ版規則（I-01）の検証。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from optpoet.errors import ManifestError, ManifestSchemaVersionError
from optpoet.manifest import APP_SCHEMA_VERSION, load_manifest, save_manifest


def _write(path: Path, data: Any) -> Path:
    target = path / "manifest.json"
    target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return target


def test_load_sample(tmp_path: Path, manifest_data: dict[str, Any]) -> None:
    loaded = load_manifest(_write(tmp_path, manifest_data))
    assert loaded.schema_version == APP_SCHEMA_VERSION
    assert loaded.read_only is False
    assert loaded.data["grid"]["cols"] == 60


def test_save_and_reload(tmp_path: Path, manifest_data: dict[str, Any]) -> None:
    target = tmp_path / "manifest.json"
    save_manifest(manifest_data, target)
    assert load_manifest(target).data == manifest_data


def test_save_keeps_non_ascii(tmp_path: Path, manifest_data: dict[str, Any]) -> None:
    target = tmp_path / "manifest.json"
    save_manifest(manifest_data, target)
    assert "記述モード試作" in target.read_text(encoding="utf-8")


def test_save_updates_timestamp(tmp_path: Path, manifest_data: dict[str, Any]) -> None:
    target = tmp_path / "manifest.json"
    save_manifest(manifest_data, target, updated_at="2026-07-26T00:00:00.000Z")
    loaded = load_manifest(target)
    assert loaded.data["manifest"]["updated_at"] == "2026-07-26T00:00:00.000Z"
    # 元データは書き換えない。
    assert manifest_data["manifest"]["updated_at"] == "2026-07-25T10:38:57.902Z"


def test_save_rejects_invalid(tmp_path: Path, manifest_data: dict[str, Any]) -> None:
    """検証に失敗した manifest はファイルを作らない（部分書込みを残さない）。"""
    manifest_data["manifest"]["api_key"] = "dummy"
    target = tmp_path / "manifest.json"
    with pytest.raises(ManifestError):
        save_manifest(manifest_data, target)
    assert not target.exists()


def test_newer_minor_is_read_only(tmp_path: Path, manifest_data: dict[str, Any]) -> None:
    """MINOR がアプリより新しい版は読取専用オープンとし、未知項目を保持する。"""
    manifest_data["manifest"]["schema_version"] = "1.9"
    manifest_data["grid"]["future_key"] = "kept"
    loaded = load_manifest(_write(tmp_path, manifest_data))
    assert loaded.read_only is True
    assert loaded.data["grid"]["future_key"] == "kept"


def test_read_only_version_cannot_be_saved(tmp_path: Path, manifest_data: dict[str, Any]) -> None:
    manifest_data["manifest"]["schema_version"] = "1.9"
    with pytest.raises(ManifestError, match="読取専用オープン"):
        save_manifest(manifest_data, tmp_path / "manifest.json")


def test_unknown_major_is_error(tmp_path: Path, manifest_data: dict[str, Any]) -> None:
    manifest_data["manifest"]["schema_version"] = "2.0"
    with pytest.raises(ManifestSchemaVersionError, match="未知のスキーマ MAJOR 版"):
        load_manifest(_write(tmp_path, manifest_data))


@pytest.mark.parametrize("value", ["1", "1.0.0", "x.y", 1.0, None, "１.０"])
def test_malformed_schema_version(
    tmp_path: Path, manifest_data: dict[str, Any], value: Any
) -> None:
    manifest_data["manifest"]["schema_version"] = value
    with pytest.raises(ManifestError, match="schema_version"):
        load_manifest(_write(tmp_path, manifest_data))


def test_missing_schema_version(tmp_path: Path, manifest_data: dict[str, Any]) -> None:
    del manifest_data["manifest"]["schema_version"]
    with pytest.raises(ManifestError, match="I-01"):
        load_manifest(_write(tmp_path, manifest_data))


def test_missing_manifest_block(tmp_path: Path, manifest_data: dict[str, Any]) -> None:
    del manifest_data["manifest"]
    with pytest.raises(ManifestError, match="I-01"):
        load_manifest(_write(tmp_path, manifest_data))


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ManifestError, match="manifest を読めない"):
        load_manifest(tmp_path / "absent.json")


def test_broken_json(tmp_path: Path) -> None:
    target = tmp_path / "manifest.json"
    target.write_text("{ broken", encoding="utf-8")
    with pytest.raises(ManifestError, match="JSON が不正"):
        load_manifest(target)


def test_root_must_be_object(tmp_path: Path) -> None:
    with pytest.raises(ManifestError, match="オブジェクトである必要がある"):
        load_manifest(_write(tmp_path, []))
