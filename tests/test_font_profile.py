"""フォントの取り込み・ハッシュ・メタデータ・欠落グリフ（P1-020 / P1-024）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from optpoet.config import FontConfig
from optpoet.errors import StageError
from optpoet.font.profile import load_font_profile, resolve_font_path
from optpoet.hashing import hash_file, parse_hash

PUA = "\ue000"
"""私用領域。基準フォント相当のどの CJK フォントにも収録されない。"""


def test_profile_records_file_hash_and_metadata(font_file: Path) -> None:
    profile = load_font_profile(font_file)
    assert profile.hash == hash_file(font_file)
    assert parse_hash(profile.hash) == profile.hash
    assert profile.bytes == font_file.stat().st_size
    assert profile.file_name == font_file.name
    assert profile.family
    assert profile.weight
    assert profile.version != ""


def test_profile_is_deterministic(font_file: Path) -> None:
    first, second = load_font_profile(font_file), load_font_profile(font_file)
    assert first.to_dict() == second.to_dict()
    assert first.codepoints == second.codepoints


def test_font_key_can_be_fixed(font_file: Path) -> None:
    profile = load_font_profile(font_file, font_key="base-gothic")
    assert profile.to_dict()["font_key"] == "base-gothic"


def test_to_dict_matches_manifest_font_files_entry(font_file: Path) -> None:
    entry = load_font_profile(font_file).to_dict()
    assert set(entry) <= {"font_key", "file_name", "hash", "weight", "version", "license"}
    assert {"font_key", "file_name", "hash", "weight", "version"} <= set(entry)


def test_missing_glyph_is_detected(font_file: Path) -> None:
    profile = load_font_profile(font_file)
    assert profile.missing(f"あ{PUA}{PUA}") == (PUA,)
    assert profile.supports(PUA) is False


def test_require_stops_on_missing_glyph(font_file: Path) -> None:
    profile = load_font_profile(font_file)
    with pytest.raises(StageError) as info:
        profile.require(f"あ{PUA}")
    assert info.value.code == "missing_glyph"
    assert info.value.hint is not None


def test_require_passes_for_covered_chars(font_file: Path) -> None:
    profile = load_font_profile(font_file)
    profile.require("あア永")


def test_broken_font_is_rejected(tmp_path: Path) -> None:
    broken = tmp_path / "broken.ttf"
    broken.write_bytes(b"not a font at all" * 4)
    with pytest.raises(StageError) as info:
        load_font_profile(broken)
    assert info.value.code == "font_invalid"


def test_collection_is_rejected(tmp_path: Path) -> None:
    collection = tmp_path / "fonts.ttc"
    collection.write_bytes(b"ttcf" + bytes(64))
    with pytest.raises(StageError) as info:
        load_font_profile(collection)
    assert info.value.code == "font_unsupported"


def test_missing_file_is_reported(tmp_path: Path) -> None:
    with pytest.raises(StageError) as info:
        load_font_profile(tmp_path / "absent.ttf")
    assert info.value.code == "font_unreadable"


def test_resolve_font_path_requires_explicit_file() -> None:
    with pytest.raises(StageError) as info:
        resolve_font_path(FontConfig())
    assert info.value.code == "font_not_configured"


def test_resolve_font_path_returns_configured_path(font_file: Path) -> None:
    assert resolve_font_path(FontConfig(path=font_file)) == font_file
