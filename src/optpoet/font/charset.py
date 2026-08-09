"""許可文字集合を NFC で確定し、版で固定する（P1-021 / FR-10）。

密度辞書・文字数調整・欠落グリフ検出は同じ文字一覧を前提にする。一覧が版ごとに揺れると
辞書 ID と最適化結果の再現が崩れるため、集合は **符号位置の範囲 + 追加/除外文字 + 版**で
宣言し、その組から決定的に構築する。

構築規則:

- 各文字を NFC 正規化し、正規化で形が変わる文字（結合文字列など）は集合へ入れない。
  入力側の正規化は P1-030 で行い、辞書側は「NFC 済み 1 文字」だけを扱う。
- 制御文字は入れない。空白（U+0020 / U+3000）は 1 セルを占める文字として入れる。
- 重複は落とし、符号位置の昇順に並べる。順序は辞書ハッシュに効くため固定する。

MVP の既定集合はかな・漢字・約物に限る。半角英数と絵文字は対象外で、入力時に不足文字
として示す（requirements.md「正規化形式は NFC とし、MVP の許可文字集合外にある結合文字・
絵文字は入力時に示す」）。

漢字は符号位置の範囲だけでは絞れない。CJK 統合漢字（U+4E00〜U+9FFF）には日本語フォントが
持たない字が多数あり、そのまま採ると欠落グリフだらけになる（Noto Sans JP で 8,245 種）。
そこで範囲に**符号化での絞り込み**を掛ける。既定は `shift_jis`（JIS X 0208）で、基準
フォントの網羅範囲（docs/environment/font-and-license.md）に収まる。`extra` で明示した
文字は作者の意図として絞り込みの対象外にし、収録の有無は欠落グリフ検出で示す。
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

from optpoet.errors import StageError
from optpoet.hashing import hash_bytes
from optpoet.storage import Stage

CHARSET_VERSION = "1.0"
"""既定集合の版。範囲・追加文字・除外文字のいずれかを変えたら上げる。"""

DEFAULT_RANGES: tuple[tuple[int, int], ...] = (
    (0x0020, 0x0020),  # 半角空白
    (0x3000, 0x3000),  # 全角空白
    (0x3005, 0x3005),  # 々
    (0x3041, 0x3096),  # ひらがな
    (0x309D, 0x309E),  # ゝゞ
    (0x30A1, 0x30FA),  # カタカナ
    (0x30FB, 0x30FE),  # ・ー ヽヾ
    (0x4E00, 0x9FFF),  # CJK 統合漢字
)

DEFAULT_EXTRA = "、。「」『』（）〈〉《》〔〕【】！？…‥―－ー：；，．"

DEFAULT_ENCODING = "shift_jis"
"""範囲の絞り込みに使う符号化。JIS X 0208 に載る字だけを採る。"""

_STAGE = str(Stage.DICTIONARY)


@dataclass(frozen=True, slots=True)
class CharsetSpec:
    """許可文字集合の宣言。ここから `Charset` を決定的に構築する。"""

    name: str = "mvp"
    version: str = CHARSET_VERSION
    ranges: tuple[tuple[int, int], ...] = DEFAULT_RANGES
    extra: str = DEFAULT_EXTRA
    excluded: str = ""
    encoding: str | None = DEFAULT_ENCODING

    def validate(self) -> None:
        if not self.name or not self.version:
            raise _invalid_charset("charset の name / version が空")
        for start, end in self.ranges:
            if not 0 <= start <= end <= 0x10FFFF:
                raise _invalid_charset(f"符号位置の範囲が不正: U+{start:04X}〜U+{end:04X}")
        if self.encoding is not None:
            try:
                "".encode(self.encoding)
            except LookupError as exc:
                raise _invalid_charset(f"未知の符号化: {self.encoding!r}") from exc


@dataclass(frozen=True, slots=True, eq=False)
class Charset:
    """確定した許可文字集合。符号位置の昇順で、NFC 済みの 1 文字だけを持つ。"""

    name: str
    version: str
    chars: tuple[str, ...]
    _members: frozenset[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_members", frozenset(self.chars))

    @property
    def text(self) -> str:
        """集合を並び順どおりに連結した文字列。ハッシュの対象。"""
        return "".join(self.chars)

    @property
    def hash(self) -> str:
        """文字一覧そのものの内容ハッシュ。辞書キーの構成要素にする。"""
        return hash_bytes(self.text.encode("utf-8"))

    def __len__(self) -> int:
        return len(self.chars)

    def __iter__(self) -> Iterator[str]:
        return iter(self.chars)

    def __contains__(self, char: object) -> bool:
        return char in self._members

    def unsupported(self, text: Iterable[str]) -> tuple[str, ...]:
        """`text` のうち集合外の文字を、出現順・重複なしで返す。"""
        found: dict[str, None] = {}
        for char in text:
            if char not in self._members:
                found.setdefault(char, None)
        return tuple(found)

    def to_dict(self) -> dict[str, Any]:
        """辞書と manifest へ書く識別情報。文字一覧そのものは辞書実体側に持つ。"""
        return {
            "name": self.name,
            "version": self.version,
            "count": len(self.chars),
            "hash": self.hash,
        }


def build_charset(spec: CharsetSpec | None = None) -> Charset:
    """宣言から許可文字集合を構築する。同じ宣言からは常に同じ集合になる。"""
    spec = spec or CharsetSpec()
    spec.validate()

    excluded = set(spec.excluded)
    extra = {ord(char) for char in spec.extra}
    codepoints: set[int] = set(extra)
    for start, end in spec.ranges:
        codepoints.update(range(start, end + 1))

    chars: list[str] = []
    for code in sorted(codepoints):
        char = chr(code)
        if char in excluded or not _acceptable(char):
            continue
        # 範囲由来の文字だけ符号化で絞る。`extra` は作者が明示した文字なので残す。
        if code not in extra and not _encodable(char, spec.encoding):
            continue
        chars.append(char)
    if not chars:
        raise _invalid_charset("許可文字集合が空")
    return Charset(name=spec.name, version=spec.version, chars=tuple(chars))


def _encodable(char: str, encoding: str | None) -> bool:
    """`encoding` で表せる文字か。`None` なら絞り込まない。"""
    if encoding is None:
        return True
    try:
        char.encode(encoding)
    except UnicodeEncodeError:
        return False
    return True


def _acceptable(char: str) -> bool:
    """NFC 済みの 1 文字で、かつ制御文字でないか。"""
    if unicodedata.normalize("NFC", char) != char:
        return False
    category = unicodedata.category(char)
    # Cc 制御 / Cs サロゲート / Cn 未割当。空白（Zs）は 1 セルを占めるため残す。
    return category not in ("Cc", "Cs", "Cn")


def _invalid_charset(message: str) -> StageError:
    return StageError(
        _STAGE,
        "invalid_charset",
        message,
        hint="許可文字集合の範囲・追加文字・除外文字を見直す。",
    )
