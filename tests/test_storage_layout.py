"""プロジェクトディレクトリ構成と相対 POSIX パスの検証。"""

from __future__ import annotations

from pathlib import Path

import pytest

from optpoet.errors import StorageError
from optpoet.storage import ProjectLayout, relative_path_error


def test_create_makes_all_dirs(tmp_path: Path) -> None:
    layout = ProjectLayout(tmp_path)
    layout.create()
    assert all(directory.is_dir() for directory in layout.all_dirs())


def test_create_is_idempotent(tmp_path: Path) -> None:
    layout = ProjectLayout(tmp_path)
    layout.create()
    layout.create()
    assert layout.dictionary_dir.is_dir()


def test_fixed_names(tmp_path: Path) -> None:
    layout = ProjectLayout(tmp_path)
    assert layout.manifest_path == tmp_path / "manifest.json"
    assert layout.index_path == tmp_path / "index.sqlite"
    assert layout.output_png_path == tmp_path / "outputs" / "artwork.png"
    assert layout.output_txt_path == tmp_path / "outputs" / "artwork.txt"


def test_relative_uses_posix_separator(tmp_path: Path) -> None:
    layout = ProjectLayout(tmp_path)
    assert layout.relative(layout.density_dir / "9f2c.npy") == "derived/density/9f2c.npy"


def test_relative_accepts_relative_input(tmp_path: Path) -> None:
    layout = ProjectLayout(tmp_path)
    assert layout.relative(Path("input/portrait.jpg")) == "input/portrait.jpg"


def test_relative_rejects_outside_root(tmp_path: Path) -> None:
    layout = ProjectLayout(tmp_path / "project")
    with pytest.raises(StorageError, match="プロジェクトルート外"):
        layout.relative(tmp_path / "other" / "portrait.jpg")


def test_relative_rejects_root_itself(tmp_path: Path) -> None:
    layout = ProjectLayout(tmp_path)
    with pytest.raises(StorageError, match="プロジェクトルート自体"):
        layout.relative(tmp_path)


def test_resolve_round_trip(tmp_path: Path) -> None:
    layout = ProjectLayout(tmp_path)
    assert layout.resolve("derived/density/9f2c.npy") == layout.density_dir / "9f2c.npy"


@pytest.mark.parametrize(
    "value",
    [
        "/var/data/portrait.jpg",
        "C:/data/portrait.jpg",
        "~/portrait.jpg",
        "input\\portrait.jpg",
        "../portrait.jpg",
        "input//portrait.jpg",
        "",
    ],
)
def test_resolve_rejects_non_relative(tmp_path: Path, value: str) -> None:
    layout = ProjectLayout(tmp_path)
    with pytest.raises(StorageError, match="manifest の path"):
        layout.resolve(value)


def test_relative_path_error_accepts_valid() -> None:
    assert relative_path_error("input/portrait.jpg") is None


def test_clear_tmp_removes_leftovers(tmp_path: Path) -> None:
    layout = ProjectLayout(tmp_path)
    layout.create()
    (layout.tmp_dir / "partial.png").write_bytes(b"x")
    (layout.tmp_dir / "sub").mkdir()
    (layout.tmp_dir / "sub" / "partial.txt").write_text("x", encoding="utf-8")
    layout.clear_tmp()
    assert list(layout.tmp_dir.iterdir()) == []


def test_clear_tmp_without_dir(tmp_path: Path) -> None:
    ProjectLayout(tmp_path).clear_tmp()
