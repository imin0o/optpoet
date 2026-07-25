"""内容ハッシュと正規形直列化の検証。"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from optpoet.errors import StorageError
from optpoet.hashing import (
    HASH_PREFIX,
    canonical_json,
    hash_bytes,
    hash_file,
    hash_json,
    parse_hash,
    short_id,
)


def test_hash_bytes_matches_sha256() -> None:
    assert hash_bytes(b"optpoet") == HASH_PREFIX + hashlib.sha256(b"optpoet").hexdigest()


def test_hash_file_matches_bytes(tmp_path: Path) -> None:
    target = tmp_path / "artifact.bin"
    data = b"\x00\x01" * 1000
    target.write_bytes(data)
    assert hash_file(target) == hash_bytes(data)


def test_hash_file_missing(tmp_path: Path) -> None:
    with pytest.raises(StorageError, match="実体を読めない"):
        hash_file(tmp_path / "absent.bin")


def test_canonical_json_sorts_keys_and_omits_space() -> None:
    assert canonical_json({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


def test_canonical_json_key_order_does_not_change_hash() -> None:
    assert hash_json({"a": 1, "b": [1, 2]}) == hash_json({"b": [1, 2], "a": 1})


def test_canonical_json_keeps_array_order() -> None:
    assert hash_json([2, 1]) != hash_json([1, 2])


def test_canonical_json_keeps_non_ascii_raw() -> None:
    assert canonical_json({"mode": "記述"}) == '{"mode":"記述"}'.encode()


def test_canonical_json_rounds_float() -> None:
    """丸め桁を超える差は同一バイト列になる（不当なキャッシュ無効化を避ける）。"""
    assert canonical_json(0.1 + 0.2) == canonical_json(0.3)


def test_canonical_json_normalizes_negative_zero() -> None:
    assert canonical_json(-0.0) == canonical_json(0.0)


def test_canonical_json_float_digits_is_configurable() -> None:
    assert canonical_json(1.234_5, float_digits=2) == b"1.23"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_canonical_json_rejects_non_finite(value: float) -> None:
    with pytest.raises(StorageError, match="有限の数値"):
        canonical_json({"gamma": value})


def test_canonical_json_rejects_non_string_key() -> None:
    with pytest.raises(StorageError, match="キーは文字列"):
        canonical_json({1: "x"})


def test_canonical_json_rejects_unsupported_type() -> None:
    with pytest.raises(StorageError, match="直列化できない"):
        canonical_json({"path": Path("input/a.jpg")})


@pytest.mark.parametrize(
    "value",
    [
        "sha256:" + "0" * 63,
        "sha256:" + "0" * 65,
        "sha256:" + "A" * 64,
        "sha1:" + "0" * 64,
        "0" * 64,
        "",
    ],
)
def test_parse_hash_rejects_bad_format(value: str) -> None:
    with pytest.raises(StorageError, match="内容ハッシュ"):
        parse_hash(value)


def test_parse_hash_rejects_non_string() -> None:
    with pytest.raises(StorageError, match="内容ハッシュは文字列"):
        parse_hash(None)


def test_short_id_is_16_hex_digits() -> None:
    digest = hash_bytes(b"optpoet")
    assert short_id(digest) == digest.removeprefix(HASH_PREFIX)[:16]
    assert len(short_id(digest)) == 16
