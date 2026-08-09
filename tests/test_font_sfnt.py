"""sfnt 表と cmap の読取り（P1-020 / P1-024 の根拠）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from optpoet.errors import StageError
from optpoet.font import sfnt
from optpoet.font.cmap import read_codepoints


@pytest.fixture(scope="session")
def parsed(font_file: Path) -> sfnt.SfntFont:
    return sfnt.read_sfnt(font_file.read_bytes())


def test_table_directory_contains_required_tables(parsed: sfnt.SfntFont) -> None:
    assert {"cmap", "head", "name"} <= set(parsed.tables)
    assert parsed.table("cmap") is not None
    assert parsed.table("zzzz") is None


def test_names_include_family_and_version(parsed: sfnt.SfntFont) -> None:
    names = sfnt.read_names(parsed)
    assert names[sfnt.NAME_FAMILY]
    assert names[sfnt.NAME_VERSION].lower().startswith("version")


def test_codepoints_cover_kana_and_kanji(parsed: sfnt.SfntFont) -> None:
    codepoints = read_codepoints(parsed)
    assert {ord("あ"), ord("ア"), ord("永")} <= codepoints
    assert 0xE000 not in codepoints


def test_codepoints_are_deterministic(parsed: sfnt.SfntFont) -> None:
    assert read_codepoints(parsed) == read_codepoints(parsed)


def test_short_data_is_rejected() -> None:
    with pytest.raises(StageError) as info:
        sfnt.read_sfnt(b"\x00\x01\x00")
    assert info.value.code == "font_invalid"


def test_table_beyond_file_is_rejected() -> None:
    header = (0x00010000).to_bytes(4, "big") + (1).to_bytes(2, "big") + bytes(6)
    record = b"name" + bytes(4) + (1000).to_bytes(4, "big") + (10).to_bytes(4, "big")
    with pytest.raises(StageError) as info:
        sfnt.read_sfnt(header + record)
    assert info.value.code == "font_invalid"


def test_font_without_cmap_is_rejected() -> None:
    header = (0x00010000).to_bytes(4, "big") + (1).to_bytes(2, "big") + bytes(6)
    record = b"head" + bytes(4) + (28).to_bytes(4, "big") + (4).to_bytes(4, "big")
    font = sfnt.read_sfnt(header + record + bytes(4))
    with pytest.raises(StageError) as info:
        read_codepoints(font)
    assert info.value.code == "font_invalid"
