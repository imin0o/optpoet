"""入力文の正規化と許可文字検査（P1-030 / FR-10）。

正規化形式は NFC 固定（requirements.md FR-10）。許可文字集合（`optpoet.font.charset`）は
NFC 済みの 1 文字だけを持つため、入力側もここで同じ形へ揃えてから突合する。

改行は **セルに数えない**（FR-10）。段落の区切りとして本文に残すが、許可文字集合には
含まれないので検査対象から外す。改行表記は `\\r\\n` / `\\r` / `\\n` を `\\n` へ統一する。

集合外の文字（結合文字、絵文字、半角英数など）は暗黙に落とさず、**文字・符号位置・行・列**
を添えて示す。どれを許可文字へ足すか、どう書き換えるかは作者の判断に委ねる。
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any, Final, Literal

from optpoet.errors import StageError
from optpoet.font.charset import Charset
from optpoet.storage import Stage

NEWLINE = "\n"
NORMALIZATION_FORM: Final[Literal["NFC"]] = "NFC"
"""manifest の `grid.normalization_form` へ記録する値。"""

REASON_CONTROL = "control"
REASON_NOT_IN_CHARSET = "not_in_charset"

_STAGE = str(Stage.TEXT)
_MAX_REPORTED = 20
# Cc 制御 / Cf 書式 / Cs サロゲート / Cn 未割当。改行は呼出前に除外する。
_CONTROL_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Cn"})


@dataclass(frozen=True, slots=True)
class UnsupportedChar:
    """許可文字集合に無い文字と、その出現位置。位置は正規化後の本文で数える。"""

    char: str
    index: int
    line: int
    column: int
    reason: str

    @property
    def codepoint(self) -> str:
        return f"U+{ord(self.char):04X}"

    @property
    def label(self) -> str:
        """UI と例外メッセージへ出す 1 件分の表記。"""
        return f"{self.char!r} ({self.codepoint}) {self.line}行{self.column}列"

    def to_dict(self) -> dict[str, Any]:
        return {
            "char": self.char,
            "codepoint": self.codepoint,
            "index": self.index,
            "line": self.line,
            "column": self.column,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class NormalizedText:
    """正規化した本文と、集合外文字の一覧。"""

    text: str
    form: str
    unsupported: tuple[UnsupportedChar, ...]

    @property
    def ok(self) -> bool:
        return not self.unsupported

    def to_dict(self) -> dict[str, Any]:
        return {
            "normalization_form": self.form,
            "unsupported": [item.to_dict() for item in self.unsupported],
        }


def normalize_text(text: str) -> str:
    """改行表記を `\\n` へ統一し、NFC 正規化した本文を返す。"""
    unified = text.replace("\r\n", NEWLINE).replace("\r", NEWLINE)
    return unicodedata.normalize(NORMALIZATION_FORM, unified)


def inspect_text(text: str, charset: Charset) -> NormalizedText:
    """正規化した本文と、許可文字集合に無い文字を返す。ここでは失敗にしない。"""
    normalized = normalize_text(text)
    found: list[UnsupportedChar] = []
    line = 1
    column = 1
    for index, char in enumerate(normalized):
        if char == NEWLINE:
            line += 1
            column = 1
            continue
        reason = _reason(char, charset)
        if reason is not None:
            found.append(
                UnsupportedChar(char=char, index=index, line=line, column=column, reason=reason)
            )
        column += 1
    return NormalizedText(text=normalized, form=NORMALIZATION_FORM, unsupported=tuple(found))


def require_supported(text: str, charset: Charset) -> str:
    """正規化した本文を返す。集合外の文字が 1 つでもあれば失敗にする。"""
    result = inspect_text(text, charset)
    if result.unsupported:
        raise _unsupported(result.unsupported)
    return result.text


def _reason(char: str, charset: Charset) -> str | None:
    if unicodedata.category(char) in _CONTROL_CATEGORIES:
        return REASON_CONTROL
    if char not in charset:
        return REASON_NOT_IN_CHARSET
    return None


def _unsupported(items: tuple[UnsupportedChar, ...]) -> StageError:
    shown = ", ".join(item.label for item in items[:_MAX_REPORTED])
    if len(items) > _MAX_REPORTED:
        shown = f"{shown}, ほか {len(items) - _MAX_REPORTED} 件"
    return StageError(
        _STAGE,
        "unsupported_chars",
        f"許可文字集合に無い文字がある（{len(items)} 件）: {shown}",
        hint="該当文字を書き換えるか、許可文字集合へ追加して辞書を作り直す。",
    )
