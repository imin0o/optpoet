"""フォントファイルの取り込み、ハッシュ、メタデータ（P1-020 / P1-024）。

密度測定と最終描画は「同一ファイル・同一版・同一ハッシュ」を使う（NFR-02）。そのため
ファミリ名ではなく**ファイルの内容ハッシュ**を同一性の根拠にし、manifest の
`fonts.font_files` へそのまま書ける形で持つ（docs/decisions/project-manifest.md）。

暗黙代替フォントを作らないため、次の 2 点を入口で止める。

- `font.path` 未指定（ファミリ名だけ）は失敗にする。OS 側の解決に任せると版が環境で
  変わり、NFR-02 を満たせない。
- cmap に無い文字は欠落として報告する。Pillow は代替フォントを探さず `.notdef` を
  描くだけなので、描画前に検出しないと豆腐が黙って混ざる（FR-08 / AC-02）。
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from optpoet.config import FontConfig
from optpoet.errors import StageError
from optpoet.font import sfnt
from optpoet.font.cmap import read_codepoints
from optpoet.hashing import hash_bytes
from optpoet.storage import Stage

_STAGE = str(Stage.DICTIONARY)

_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")

# ライセンス表記の同定。出力前検査（P5-012）が「OFL 準拠か」を一点確認できるようにする。
# 判別できない場合は None のままにし、推測で埋めない。
_LICENSE_MARKERS = (
    ("sil open font license", "OFL-1.1"),
    ("openfontlicense", "OFL-1.1"),
    ("ipa font license", "IPA-1.0"),
)


@dataclass(frozen=True, slots=True, eq=False)
class FontProfile:
    """取り込んだフォント 1 つ。ハッシュ・メタデータ・収録符号位置を持つ。"""

    path: Path
    file_name: str
    hash: str
    bytes: int
    font_key: str
    family: str
    subfamily: str
    version: str
    postscript_name: str
    license: str | None
    codepoints: frozenset[int] = field(repr=False)

    @property
    def weight(self) -> str:
        """manifest の `weight`。可変フォントは既定インスタンスのスタイル名になる。"""
        return self.subfamily

    def supports(self, char: str) -> bool:
        return ord(char) in self.codepoints

    def missing(self, chars: Iterable[str]) -> tuple[str, ...]:
        """収録されていない文字を、出現順・重複なしで返す。"""
        found: dict[str, None] = {}
        for char in chars:
            if not self.supports(char):
                found.setdefault(char, None)
        return tuple(found)

    def require(self, chars: Iterable[str]) -> None:
        """欠落グリフがあれば止める。暗黙代替へ落とさない（AC-02）。"""
        missing = self.missing(chars)
        if not missing:
            return
        shown = "".join(missing[:20])
        raise StageError(
            _STAGE,
            "missing_glyph",
            f"フォントに無い文字が {len(missing)} 種ある: {shown}",
            hint="文字を許可文字集合から外すか、収録するフォントへ差し替える。",
        )

    def to_dict(self) -> dict[str, Any]:
        """manifest の `fonts.font_files` 要素。"""
        entry: dict[str, Any] = {
            "font_key": self.font_key,
            "file_name": self.file_name,
            "hash": self.hash,
            "weight": self.weight,
            "version": self.version,
        }
        if self.license is not None:
            entry["license"] = self.license
        return entry


def load_font_profile(path: Path, *, font_key: str | None = None) -> FontProfile:
    """フォントファイルを読み、ハッシュとメタデータを確定する。"""
    data = _read(path)
    font = sfnt.read_sfnt(data)
    names = sfnt.read_names(font)

    family = _pick(names, sfnt.NAME_TYPO_FAMILY, sfnt.NAME_FAMILY) or path.stem
    subfamily = _pick(names, sfnt.NAME_TYPO_SUBFAMILY, sfnt.NAME_SUBFAMILY) or "Regular"
    postscript = _pick(names, sfnt.NAME_POSTSCRIPT) or f"{family}-{subfamily}"
    version = _pick(names, sfnt.NAME_VERSION) or "unknown"

    return FontProfile(
        path=path,
        file_name=path.name,
        hash=hash_bytes(data),
        bytes=len(data),
        font_key=font_key or _slug(postscript),
        family=family,
        subfamily=subfamily,
        version=version,
        postscript_name=postscript,
        license=_license_id(names),
        codepoints=read_codepoints(font),
    )


def resolve_font_path(config: FontConfig) -> Path:
    """設定から使うフォントファイルを決める。ファミリ名だけの指定は拒否する。"""
    if config.path is None:
        raise StageError(
            _STAGE,
            "font_not_configured",
            f"font.path が未指定のため、{config.family} をファイル単位で特定できない",
            hint="同梱したフォントファイルの相対パスを font.path に指定する。",
        )
    return config.path


def _read(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise StageError(
            _STAGE,
            "font_unreadable",
            f"フォントファイルを読めない: {path}",
            hint="パスと読み取り権限を確認する。",
        ) from exc


def _pick(names: dict[int, str], *name_ids: int) -> str | None:
    for name_id in name_ids:
        value = names.get(name_id)
        if value:
            return value
    return None


def _license_id(names: dict[int, str]) -> str | None:
    source = " ".join(
        names.get(name_id, "") for name_id in (sfnt.NAME_LICENSE, sfnt.NAME_LICENSE_URL)
    ).lower()
    for marker, license_id in _LICENSE_MARKERS:
        if marker in source:
            return license_id
    return None


def _slug(value: str) -> str:
    return _SLUG_PATTERN.sub("-", value.lower()).strip("-") or "font"
