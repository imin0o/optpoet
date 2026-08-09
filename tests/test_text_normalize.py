"""入力文の正規化と許可文字検査（P1-030）。"""

from __future__ import annotations

import pytest

from optpoet.errors import StageError
from optpoet.font.charset import Charset, CharsetSpec, build_charset
from optpoet.text.normalize import (
    REASON_CONTROL,
    REASON_NOT_IN_CHARSET,
    inspect_text,
    normalize_text,
    require_supported,
)

SPEC = CharsetSpec(name="test", version="1.0", ranges=((0x3041, 0x3096),), extra="、。 　")


@pytest.fixture(scope="module")
def charset() -> Charset:
    return build_charset(SPEC)


def test_composes_to_nfc() -> None:
    assert normalize_text("が") == "が"
    assert normalize_text("パ") == "パ"


def test_unifies_newline_notations() -> None:
    assert normalize_text("あ\r\nい\rう\nえ") == "あ\nい\nう\nえ"


def test_supported_text_passes_through(charset: Charset) -> None:
    assert require_supported("あい、うえ。\nお", charset) == "あい、うえ。\nお"


def test_newline_is_not_checked_against_the_charset(charset: Charset) -> None:
    assert inspect_text("あ\nい", charset).ok


def test_chars_outside_the_charset_are_reported_with_positions(charset: Charset) -> None:
    result = inspect_text("あA\nい🙂", charset)
    assert not result.ok
    assert [item.char for item in result.unsupported] == ["A", "🙂"]
    assert [(item.line, item.column) for item in result.unsupported] == [(1, 2), (2, 2)]
    assert {item.reason for item in result.unsupported} == {REASON_NOT_IN_CHARSET}


def test_control_chars_are_reported_separately(charset: Charset) -> None:
    result = inspect_text("あ\tい", charset)
    assert [item.reason for item in result.unsupported] == [REASON_CONTROL]


def test_require_supported_lists_the_offending_chars(charset: Charset) -> None:
    with pytest.raises(StageError) as info:
        require_supported("あ漢", charset)
    assert info.value.code == "unsupported_chars"
    assert "U+6F22" in info.value.detail


def test_report_is_serializable(charset: Charset) -> None:
    body = inspect_text("あA", charset).to_dict()
    assert body["normalization_form"] == "NFC"
    assert body["unsupported"][0]["codepoint"] == "U+0041"
