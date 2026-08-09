"""許可文字集合（P1-021）。"""

from __future__ import annotations

import unicodedata

import pytest

from optpoet.errors import StageError
from optpoet.font.charset import (
    CHARSET_VERSION,
    DEFAULT_EXTRA,
    CharsetSpec,
    build_charset,
)


def test_default_charset_is_nfc_and_sorted() -> None:
    charset = build_charset()
    assert charset.version == CHARSET_VERSION
    assert all(unicodedata.normalize("NFC", char) == char for char in charset)
    codepoints = [ord(char) for char in charset]
    assert codepoints == sorted(set(codepoints))


def test_default_charset_covers_kana_kanji_and_punctuation() -> None:
    charset = build_charset()
    for char in "あアの永鬱、。「」 　":
        assert char in charset
    # MVP は半角英数と絵文字を含めない（入力時に不足として示す）。
    for char in "aA1🙂":
        assert char not in charset


def test_kanji_are_limited_to_jis_x_0208() -> None:
    """日本語フォントが持たない CJK 統合漢字を既定集合へ入れない（AC-02）。"""
    charset = build_charset()
    assert "漢" in charset
    assert "丆" not in charset
    for char in charset:
        if char not in DEFAULT_EXTRA:
            char.encode("shift_jis")


def test_encoding_filter_can_be_disabled() -> None:
    ranges = ((0x3042, 0x3042), (0x4E06, 0x4E06))
    filtered = build_charset(CharsetSpec(name="test", version="1.0", ranges=ranges, extra=""))
    kept = build_charset(
        CharsetSpec(name="test", version="1.0", ranges=ranges, extra="", encoding=None)
    )
    assert filtered.chars == ("あ",)
    assert kept.chars == ("あ", "丆")


def test_extra_chars_bypass_the_encoding_filter() -> None:
    spec = CharsetSpec(name="test", version="1.0", ranges=((0x3042, 0x3044),), extra="丆")
    assert "丆" in build_charset(spec)


def test_unknown_encoding_is_rejected() -> None:
    with pytest.raises(StageError):
        build_charset(CharsetSpec(name="test", version="1.0", encoding="no-such-encoding"))


def test_build_charset_is_deterministic() -> None:
    first, second = build_charset(), build_charset()
    assert first.chars == second.chars
    assert first.hash == second.hash


def test_charset_hash_changes_with_content() -> None:
    spec = CharsetSpec(name="test", version="1.0", ranges=((0x3042, 0x3044),), extra="")
    base = build_charset(spec)
    wider = build_charset(CharsetSpec(name="test", version="1.0", ranges=((0x3042, 0x3046),)))
    assert base.hash != wider.hash
    assert len(base) == 3


def test_excluded_chars_are_dropped() -> None:
    spec = CharsetSpec(name="test", version="1.0", ranges=((0x3042, 0x3046),), excluded="い")
    charset = build_charset(spec)
    assert "い" not in charset
    assert "あ" in charset


def test_unsupported_reports_missing_chars_in_order() -> None:
    charset = build_charset(CharsetSpec(name="test", version="1.0", ranges=((0x3042, 0x3044),)))
    assert charset.unsupported("あzあy") == ("z", "y")


def test_control_chars_are_not_included() -> None:
    spec = CharsetSpec(name="test", version="1.0", ranges=((0x0009, 0x0020),), extra="")
    assert build_charset(spec).chars == (" ",)


def test_invalid_spec_is_rejected() -> None:
    with pytest.raises(StageError) as info:
        build_charset(CharsetSpec(name="test", version="1.0", ranges=((0x3046, 0x3042),)))
    assert info.value.code == "invalid_charset"


def test_empty_charset_is_rejected() -> None:
    with pytest.raises(StageError):
        build_charset(CharsetSpec(name="test", version="1.0", ranges=(), extra=""))


def test_to_dict_has_identity_fields() -> None:
    spec = CharsetSpec(name="test", version="1.0", ranges=((0x3042, 0x3044),), extra="")
    charset = build_charset(spec)
    assert charset.to_dict() == {
        "name": "test",
        "version": "1.0",
        "count": 3,
        "hash": charset.hash,
    }
