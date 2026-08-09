"""表記候補と許可置換の表（P1-035）。

Phase 1 は AI を使わない（Phase 1 の目標）。形態素解析による言い換え（FR-09 第 3 段階）も
Phase 2 以降なので、ここで扱えるのは **読みを変えずに表記だけを差し替える** 置換に限る。

既定の表:

- かな: ひらがな ⇔ カタカナ（U+3041〜U+3096 と U+30A1〜U+30F6 は符号位置が 0x60 差）。
  読みは変わらず、黒画素率は目に見えて変わる。
- 約物: 、⇔， 。⇔． ー⇔― の相互置換。組版上の同義表記として扱う。
- 空白: 半角 ⇔ 全角。どちらも 1 セルを占める（FR-10）。

意味が変わる置換（同義語、漢字⇔かな）は入れない。それらは語の単位で扱う必要があり、
Phase 2 の言い換え候補生成が担う。表は `name` / `version` を持ち、最適化トレース
（P1-037）へ記録して再現できるようにする。
"""

from __future__ import annotations

from collections.abc import Container, Mapping
from dataclasses import dataclass
from typing import Any

VARIANTS_VERSION = "1.0"
"""表の版。組を増減したら上げる（トレースの再現性のため）。"""

HIRAGANA_START = 0x3041
HIRAGANA_END = 0x3096
KANA_OFFSET = 0x60
"""ひらがな → カタカナの符号位置差。"""

PUNCTUATION_PAIRS: tuple[tuple[str, str], ...] = (
    ("、", "，"),
    ("。", "．"),
    ("ー", "―"),
    (" ", "　"),
)


@dataclass(frozen=True, slots=True)
class VariantTable:
    """文字 → 置換候補。候補は重複なし・決定的な並びで持つ。"""

    mapping: Mapping[str, tuple[str, ...]]
    name: str = "kana_punctuation"
    version: str = VARIANTS_VERSION

    def candidates(self, char: str) -> tuple[str, ...]:
        """`char` の置換候補。無ければ空。"""
        return self.mapping.get(char, ())

    def restricted(self, allowed: Container[str]) -> VariantTable:
        """`allowed` に含まれる文字だけへ絞った表を返す。

        密度辞書に無い文字へ置換すると測定値が無く、暗黙代替も禁止されている（FR-04）。
        最適化の前に必ず辞書の文字集合で絞る。
        """
        limited = {
            char: tuple(item for item in items if item in allowed)
            for char, items in self.mapping.items()
            if char in allowed
        }
        return VariantTable(
            mapping={char: items for char, items in limited.items() if items},
            name=self.name,
            version=self.version,
        )

    def to_dict(self) -> dict[str, Any]:
        """トレースへ記録する識別情報。組そのものは表の版で再現する。"""
        return {"name": self.name, "version": self.version, "count": len(self.mapping)}


def default_variants() -> VariantTable:
    """既定の表記候補表を作る。同じ版からは常に同じ表になる。"""
    mapping: dict[str, tuple[str, ...]] = {}
    for code in range(HIRAGANA_START, HIRAGANA_END + 1):
        hiragana = chr(code)
        katakana = chr(code + KANA_OFFSET)
        mapping[hiragana] = (katakana,)
        mapping[katakana] = (hiragana,)
    for left, right in PUNCTUATION_PAIRS:
        mapping[left] = (right,)
        mapping[right] = (left,)
    return VariantTable(mapping=mapping)
