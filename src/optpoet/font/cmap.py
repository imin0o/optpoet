"""`cmap` 表からフォントが実際に持つ符号位置を読む（P1-024）。

欠落グリフの判定を描画結果の見た目に頼らない。FreeType は cmap に無い文字を
`.notdef`（グリフ ID 0）へ写して描くだけで例外を出さないため、**cmap に載っているか**を
唯一の根拠にする。Pillow は文字単位の代替フォント探索をしないので、cmap に無い文字は
そのまま暗黙代替（豆腐・空白）になる。これを描画前に検出して止める（FR-08 / AC-02）。

対応する部分表は format 0 / 4 / 6 / 12。CJK フォントが実際に載せる形式を網羅する。
"""

from __future__ import annotations

import struct

from optpoet.errors import StageError
from optpoet.font.sfnt import SfntFont
from optpoet.storage import Stage

MAX_CODEPOINT = 0x10FFFF

_STAGE = str(Stage.DICTIONARY)

# 部分表の採用優先度。Unicode 全域（format 12 を伴う (3,10) / (0,4〜6)）を最優先にする。
_SUBTABLE_SCORE = {
    (3, 10): 50,
    (0, 6): 45,
    (0, 4): 40,
    (3, 1): 30,
    (0, 3): 25,
    (0, 2): 15,
    (0, 1): 15,
    (0, 0): 15,
}


def read_codepoints(font: SfntFont) -> frozenset[int]:
    """フォントが glyph を持つ符号位置の集合を返す。

    優先度の高い部分表から順に試し、最初に読めたものを採る。読めた部分表が 1 つも
    無ければ、網羅を確認できないため失敗にする（暗黙に「全部ある」と見なさない）。
    """
    table = font.table("cmap")
    if table is None or len(table) < 4:
        raise _invalid("cmap 表がない")

    count = struct.unpack_from(">H", table, 2)[0]
    candidates: list[tuple[int, int]] = []
    for index in range(count):
        record = 4 + index * 8
        if record + 8 > len(table):
            break
        platform, encoding, offset = struct.unpack_from(">HHI", table, record)
        if offset + 4 > len(table):
            continue
        candidates.append((_SUBTABLE_SCORE.get((platform, encoding), 0), offset))

    for _score, offset in sorted(candidates, key=lambda item: -item[0]):
        codepoints = _read_subtable(table, offset)
        if codepoints is not None:
            return codepoints
    raise _invalid("読み取れる cmap 部分表がない")


def _read_subtable(table: bytes, offset: int) -> frozenset[int] | None:
    """部分表 1 つを読む。未対応の形式なら None を返す。"""
    fmt = struct.unpack_from(">H", table, offset)[0]
    match fmt:
        case 0:
            return _read_format0(table, offset)
        case 4:
            return _read_format4(table, offset)
        case 6:
            return _read_format6(table, offset)
        case 12:
            return _read_format12(table, offset)
        case _:
            return None


def _read_format0(table: bytes, offset: int) -> frozenset[int] | None:
    start = offset + 6
    if start + 256 > len(table):
        return None
    return frozenset(code for code in range(256) if table[start + code] != 0)


def _read_format4(table: bytes, offset: int) -> frozenset[int] | None:
    """区間ごとに delta か glyphIdArray でグリフ ID を引く形式（BMP 用）。"""
    if offset + 14 > len(table):
        return None
    segments = struct.unpack_from(">H", table, offset + 6)[0] // 2
    ends_at = offset + 14
    starts_at = ends_at + segments * 2 + 2  # reservedPad を挟む
    deltas_at = starts_at + segments * 2
    ranges_at = deltas_at + segments * 2
    if ranges_at + segments * 2 > len(table):
        return None

    ends = struct.unpack_from(f">{segments}H", table, ends_at)
    starts = struct.unpack_from(f">{segments}H", table, starts_at)
    deltas = struct.unpack_from(f">{segments}h", table, deltas_at)
    ranges = struct.unpack_from(f">{segments}H", table, ranges_at)

    codepoints: set[int] = set()
    for index in range(segments):
        start, end = starts[index], ends[index]
        if start > end or start == 0xFFFF:
            continue
        for code in range(start, min(end, 0xFFFF) + 1):
            if ranges[index] == 0:
                glyph = (code + deltas[index]) & 0xFFFF
            else:
                position = ranges_at + index * 2 + ranges[index] + (code - start) * 2
                if position + 2 > len(table):
                    continue
                glyph = struct.unpack_from(">H", table, position)[0]
                if glyph != 0:
                    glyph = (glyph + deltas[index]) & 0xFFFF
            if glyph != 0:
                codepoints.add(code)
    return frozenset(codepoints)


def _read_format6(table: bytes, offset: int) -> frozenset[int] | None:
    if offset + 10 > len(table):
        return None
    first, count = struct.unpack_from(">HH", table, offset + 6)
    if offset + 10 + count * 2 > len(table):
        return None
    glyphs = struct.unpack_from(f">{count}H", table, offset + 10)
    return frozenset(first + index for index, glyph in enumerate(glyphs) if glyph != 0)


def _read_format12(table: bytes, offset: int) -> frozenset[int] | None:
    """符号位置の連続区間で持つ形式（BMP 外を含む）。"""
    if offset + 16 > len(table):
        return None
    groups = struct.unpack_from(">I", table, offset + 12)[0]
    if offset + 16 + groups * 12 > len(table):
        return None

    codepoints: set[int] = set()
    for index in range(groups):
        start, end, glyph = struct.unpack_from(">III", table, offset + 16 + index * 12)
        if start > end or start > MAX_CODEPOINT:
            continue
        for code in range(start, min(end, MAX_CODEPOINT) + 1):
            # 区間内は glyph が 1 ずつ増える。先頭が .notdef の区間だけ 1 文字ずれる。
            if glyph + (code - start) != 0:
                codepoints.add(code)
    return frozenset(codepoints)


def _invalid(message: str) -> StageError:
    return StageError(
        _STAGE,
        "font_invalid",
        message,
        hint="Unicode の cmap を持つ TrueType / OpenType フォントを指定する。",
    )
