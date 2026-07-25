"""原子的書込みと置換のプリミティブの検証。"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from optpoet.errors import StorageError
from optpoet.storage.atomic import (
    REPLACE_ATTEMPTS,
    atomic_write,
    replace,
    staged_name,
    sync_dir,
    write_and_sync,
)


def test_write_and_sync_creates_parent(tmp_path: Path) -> None:
    target = tmp_path / "derived" / "density" / "ab12.npy"
    write_and_sync(target, b"density")
    assert target.read_bytes() == b"density"


def test_write_and_sync_reports_failure(tmp_path: Path) -> None:
    """書込み失敗（容量不足・権限・ロック）は保存前に検出する。"""
    target = tmp_path / "occupied"
    target.mkdir()
    with pytest.raises(StorageError, match="実体を書けない"):
        write_and_sync(target, b"x")


def test_replace_overwrites_target(tmp_path: Path) -> None:
    source = tmp_path / "staged.json"
    source.write_bytes(b"new")
    target = tmp_path / "manifest.json"
    target.write_bytes(b"old")
    replace(source, target)
    assert target.read_bytes() == b"new"
    assert not source.exists()


def test_replace_retries_before_failing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """一時的なファイルロックを跨ぐため再試行してから諦める。"""
    source = tmp_path / "staged.json"
    source.write_bytes(b"new")
    calls = 0

    def locked(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        raise PermissionError("locked")

    monkeypatch.setattr(os, "replace", locked)
    monkeypatch.setattr(time, "sleep", lambda _: None)
    with pytest.raises(StorageError, match="置換移動に失敗した"):
        replace(source, tmp_path / "manifest.json")
    assert calls == REPLACE_ATTEMPTS


def test_replace_succeeds_after_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "staged.json"
    source.write_bytes(b"new")
    target = tmp_path / "manifest.json"
    real = os.replace
    calls = 0

    def flaky(src: object, dst: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise PermissionError("locked")
        real(src, dst)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "replace", flaky)
    monkeypatch.setattr(time, "sleep", lambda _: None)
    replace(source, target)
    assert target.read_bytes() == b"new"


def test_atomic_write_leaves_no_residue(tmp_path: Path) -> None:
    tmp_dir = tmp_path / ".tmp"
    target = tmp_path / "derived" / "density" / "ab12.npy"
    atomic_write(target, b"density", tmp_dir=tmp_dir)
    assert target.read_bytes() == b"density"
    assert list(tmp_dir.iterdir()) == []


def test_staged_name_includes_parent_dir() -> None:
    """`.tmp/` は工程横断で共用するため、実体名だけでは衝突しうる。"""
    assert staged_name(Path("derived/density/ab12.npy")) == "density.ab12.npy.part"


def test_sync_dir_never_raises(tmp_path: Path) -> None:
    """A-09 は OS が対応しない場合に何もしない。保存の失敗にしない。"""
    sync_dir(tmp_path)
    sync_dir(tmp_path / "absent")
