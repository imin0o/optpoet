"""内容ハッシュと構造化データの正規形直列化。

docs/decisions/artifact-storage.md「内容ハッシュ」に従う。

- アルゴリズムは SHA-256、表記は `sha256:<64 桁小文字 16 進>`（識別子を必ず前置）。
- 対象はファイルのバイト列そのもの。タイムスタンプ等のメタデータを含めない。
- JSON など構造化実体は `canonical_json` の正規形へ直列化してからハッシュする。

浮動小数の丸め桁は docs が「工程ごとに確定」としているため、本モジュールは既定値
`FLOAT_DIGITS` を持ちつつ呼び出し側の指定を優先する。工程が既定以外を使う場合は、
その桁数を値と同じ場所へ記録する責務は呼び出し側にある。
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from optpoet.errors import StorageError

HASH_ALGORITHM = "sha256"
HASH_PREFIX = f"{HASH_ALGORITHM}:"
HASH_HEX_LENGTH = 64
_HASH_PATTERN = re.compile(rf"^{HASH_PREFIX}[0-9a-f]{{{HASH_HEX_LENGTH}}}$")

SHORT_ID_LENGTH = 16
"""ファイル名へ使う先頭桁数。64 bit あればプロジェクト内の衝突回避に足りる。"""

FLOAT_DIGITS = 6
"""浮動小数の既定丸め桁。工程側で確定した桁があればそれを渡す。"""

_READ_CHUNK = 1 << 20


def hash_bytes(data: bytes) -> str:
    """バイト列の内容ハッシュを返す。"""
    return HASH_PREFIX + hashlib.sha256(data).hexdigest()


def hash_file(path: Path) -> str:
    """ファイルのバイト列の内容ハッシュを返す。大きい実体も一定メモリで読む。"""
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(_READ_CHUNK):
                digest.update(chunk)
    except OSError as exc:
        raise StorageError(f"実体を読めない: {path}") from exc
    return HASH_PREFIX + digest.hexdigest()


def hash_json(value: object, *, float_digits: int = FLOAT_DIGITS) -> str:
    """構造化データを正規形へ直列化してから内容ハッシュを返す。"""
    return hash_bytes(canonical_json(value, float_digits=float_digits))


def canonical_json(value: object, *, float_digits: int = FLOAT_DIGITS) -> bytes:
    """同一内容が同一バイト列になる JSON 直列化。

    キーは Unicode コードポイント昇順、UTF-8（BOM なし）、インデントなし、区切りに
    余分な空白を置かない。配列の順序は意味を持つものとして保持する。
    """
    normalized = _normalize(value, float_digits, "")
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def parse_hash(value: object) -> str:
    """内容ハッシュの表記を検証して返す。"""
    if not isinstance(value, str):
        raise StorageError(f"内容ハッシュは文字列: {value!r}")
    if not _HASH_PATTERN.match(value):
        raise StorageError(f"内容ハッシュは {HASH_PREFIX}<64 桁小文字 16 進> 形式: {value!r}")
    return value


def short_id(hash_value: str, *, length: int = SHORT_ID_LENGTH) -> str:
    """ファイル名へ使う先頭桁を返す。完全なハッシュは manifest 側に保持する。"""
    return parse_hash(hash_value).removeprefix(HASH_PREFIX)[:length]


def _normalize(value: object, float_digits: int, path: str) -> Any:
    """JSON 直列化前に、環境差を生む値を正規形へ落とす。"""
    if isinstance(value, bool) or value is None or isinstance(value, int):
        return value
    if isinstance(value, float):
        return _normalize_float(value, float_digits, path)
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise StorageError(f"{_label(path)} のキーは文字列: {key!r}")
            result[key] = _normalize(item, float_digits, _join(path, key))
        return result
    if isinstance(value, Sequence):
        return [
            _normalize(item, float_digits, f"{path}[{index}]") for index, item in enumerate(value)
        ]
    raise StorageError(f"{_label(path)} は JSON へ直列化できない: {value!r}")


def _normalize_float(value: float, float_digits: int, path: str) -> float:
    if not math.isfinite(value):
        raise StorageError(f"{_label(path)} は有限の数値である必要がある: {value!r}")
    rounded = round(value, float_digits)
    # `-0.0` と `0.0` を同一バイト列にする。
    return 0.0 if rounded == 0.0 else rounded


def _join(path: str, name: str) -> str:
    return f"{path}.{name}" if path else name


def _label(path: str) -> str:
    return path or "値"
