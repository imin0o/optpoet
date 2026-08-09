"""sfnt（TrueType / OpenType）の表ディレクトリと `name` 表の読取り（P1-020）。

フォントの版・ファミリ・ライセンス表記はフォントファイル自身が持つ。Pillow は
`getname()` でファミリとスタイルしか返さず、版（nameID 5）やライセンス（nameID 13/14）を
取れないため、必要な表だけを直接読む。追加依存は入れない。

対象は**単一フォントの sfnt**（`0x00010000` / `OTTO` / `true`）に限る。TrueType
Collection（`ttcf`）はどの face を指すかが一意でなく、版固定（NFR-02）と内容ハッシュの
対応が崩れるため受け付けない。
"""

from __future__ import annotations

import struct
from collections.abc import Mapping
from dataclasses import dataclass

from optpoet.errors import StageError
from optpoet.storage import Stage

NAME_FAMILY = 1
NAME_SUBFAMILY = 2
NAME_UNIQUE_ID = 3
NAME_FULL = 4
NAME_VERSION = 5
NAME_POSTSCRIPT = 6
NAME_LICENSE = 13
NAME_LICENSE_URL = 14
NAME_TYPO_FAMILY = 16
NAME_TYPO_SUBFAMILY = 17

# sfnt 版: TrueType アウトライン / CFF アウトライン / 旧 Apple TrueType。
_SFNT_VERSIONS = frozenset({0x00010000, 0x4F54544F, 0x74727565})

_STAGE = str(Stage.DICTIONARY)

# name 文字列の採用優先度。英語（Windows 0x0409 / Mac 0）を優先し、Unicode 系の符号化を
# 上に置く。同一 nameID が複数あっても採用結果が環境に依らないようにする。
_PLATFORM_SCORE = {3: 30, 0: 20, 1: 10}
_UNICODE_ENCODINGS = frozenset({1, 10})


@dataclass(frozen=True, slots=True)
class SfntFont:
    """読み込んだフォントのバイト列と表の位置。"""

    data: bytes
    tables: Mapping[str, tuple[int, int]]

    def table(self, tag: str) -> bytes | None:
        """表のバイト列を返す。無ければ None。"""
        located = self.tables.get(tag)
        if located is None:
            return None
        offset, length = located
        return self.data[offset : offset + length]


def read_sfnt(data: bytes) -> SfntFont:
    """フォントファイルのバイト列から表ディレクトリを読む。"""
    if len(data) < 12:
        raise _invalid("フォントファイルが短すぎる")
    if data[:4] == b"ttcf":
        raise StageError(
            _STAGE,
            "font_unsupported",
            "TrueType Collection (.ttc) はどの face を使うか一意でない",
            hint="単一フォントの .ttf / .otf を指定する。",
        )
    version = int.from_bytes(data[:4], "big")
    if version not in _SFNT_VERSIONS:
        raise _invalid(f"sfnt 版が不明: 0x{version:08x}")

    count = int.from_bytes(data[4:6], "big")
    tables: dict[str, tuple[int, int]] = {}
    for index in range(count):
        base = 12 + index * 16
        if base + 16 > len(data):
            raise _invalid("表ディレクトリが途中で切れている")
        tag = data[base : base + 4].decode("latin-1")
        offset = int.from_bytes(data[base + 8 : base + 12], "big")
        length = int.from_bytes(data[base + 12 : base + 16], "big")
        if offset + length > len(data):
            raise _invalid(f"表 {tag!r} がファイル範囲外を指している")
        tables[tag] = (offset, length)
    return SfntFont(data=data, tables=tables)


def read_names(font: SfntFont) -> dict[int, str]:
    """`name` 表を nameID → 文字列で返す。読めない記録は落とす。"""
    table = font.table("name")
    if table is None or len(table) < 6:
        return {}
    count, storage = struct.unpack_from(">HH", table, 2)

    names: dict[int, str] = {}
    scores: dict[int, int] = {}
    for index in range(count):
        record = 6 + index * 12
        if record + 12 > len(table):
            break
        platform, encoding, language, name_id, length, offset = struct.unpack_from(
            ">6H", table, record
        )
        start = storage + offset
        raw = table[start : start + length]
        if len(raw) != length:
            continue
        text = _decode(platform, encoding, raw)
        if text is None:
            continue
        score = _name_score(platform, encoding, language)
        if score > scores.get(name_id, -1):
            names[name_id] = text
            scores[name_id] = score
    return names


def _decode(platform: int, encoding: int, raw: bytes) -> str | None:
    if platform in (0, 3):
        codec = "utf-16-be"
    elif platform == 1:
        codec = "mac_roman"
    else:
        return None
    try:
        text = raw.decode(codec)
    except (UnicodeDecodeError, LookupError):
        return None
    text = text.replace("\x00", "").strip()
    return text or None


def _name_score(platform: int, encoding: int, language: int) -> int:
    score = _PLATFORM_SCORE.get(platform, 0)
    # 英語（Windows は 0x0409、Mac は 0）を優先する。Unicode プラットフォームは
    # 言語 ID を持たないため加点しない。
    if (platform == 3 and language == 0x0409) or (platform == 1 and language == 0):
        score += 5
    if platform == 3 and encoding in _UNICODE_ENCODINGS:
        score += 1
    return score


def _invalid(message: str) -> StageError:
    return StageError(
        _STAGE,
        "font_invalid",
        message,
        hint="TrueType / OpenType のフォントファイルを指定する。",
    )
