"""文字密度辞書の生成とキー（P1-022 / P1-023 / P1-025 / P1-026 / FR-04）。

各文字を基準セルへ 1 文字ずつ描き、黒画素率を測る。描画は `render_cell()` 一本で、
最終描画と同じ画素になる（NFR-02）。

**辞書キー**（`dictionary_id`）は「フォントファイルのハッシュ + 文字集合 + 描画設定 +
密度クラス設定」から導く（docs/decisions/artifact-storage.md）。キャッシュキーと同じ
入力集合から導出し、表記を `dict:sha256:<64 桁>` に固定する（manifest-sample-review R-03）。
フォントを差し替えればファイルハッシュが変わり、辞書も別実体になる。

**密度クラス**（P1-025）は 5〜10 段階を設定できる。文字の黒画素率は 0.0〜1.0 の全域には
広がらず、実測では概ね 0.04〜0.13 に集まる（pixel-identity-spike.md）。そのままでは段階が
片寄るため、辞書内の最小〜最大で正規化してから分割する。

- `LINEAR`: 正規化後の等幅分割。密度マップ側（0.0〜1.0 を等幅で段階化）と対応が素直。
- `QUANTILE`: 出現頻度が等しくなる分割。どの段階にも候補文字が残ることを優先する。

`min_ratio` / `max_ratio` を辞書に持たせるので、密度マップ側の 0.0〜1.0 と相互変換できる。
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import numpy as np

from optpoet.config import MAX_DENSITY_LEVELS, MIN_DENSITY_LEVELS
from optpoet.errors import StageError
from optpoet.font.charset import Charset, build_charset
from optpoet.font.profile import FontProfile
from optpoet.font.render import RenderSettings, black_ratio, load_font, render_cell
from optpoet.hashing import FLOAT_DIGITS, canonical_json
from optpoet.pipeline.progress import StageProgress
from optpoet.storage import Stage, cache_key

DICTIONARY_STAGE_VERSION = 1
"""辞書の生成規則を変えたら上げる（docs/decisions/change-management.md）。"""

DICTIONARY_SCHEMA_VERSION = "1.0"
DICTIONARY_ID_PREFIX = "dict:"

_STAGE = str(Stage.DICTIONARY)


class LevelScale(StrEnum):
    """黒画素率を密度クラスへ割る方法。"""

    LINEAR = "linear"
    QUANTILE = "quantile"


@dataclass(frozen=True, slots=True, eq=False)
class DensityDictionary:
    """文字 → 黒画素率と密度クラスの対応。`chars` と `ratios` は同じ並び。"""

    font: FontProfile
    charset: Charset
    settings: RenderSettings
    levels: int
    scale: LevelScale
    ratios: tuple[float, ...]
    thresholds: tuple[float, ...]
    _by_char: dict[str, float] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_by_char", dict(zip(self.chars, self.ratios, strict=True)))

    @property
    def chars(self) -> tuple[str, ...]:
        return self.charset.chars

    @property
    def min_ratio(self) -> float:
        return min(self.ratios)

    @property
    def max_ratio(self) -> float:
        return max(self.ratios)

    def ratio_of(self, char: str) -> float:
        """文字の黒画素率。辞書に無い文字は暗黙に 0 とせず失敗にする。"""
        try:
            return self._by_char[char]
        except KeyError:
            raise _unknown_char(char) from None

    def level_of(self, char: str) -> int:
        """文字の密度クラス（0 が最も薄い）。"""
        return bisect_right(self.thresholds, self.ratio_of(char))

    def chars_at(self, level: int) -> tuple[str, ...]:
        """指定した密度クラスに属する文字。候補提示（P1-035）で使う。"""
        if not 0 <= level < self.levels:
            raise _invalid_levels(f"密度クラスは 0〜{self.levels - 1}: {level}")
        return tuple(char for char in self.chars if self.level_of(char) == level)

    def level_for_density(self, density: float) -> int:
        """密度マップの値（0.0〜1.0）を同じ段階数の密度クラスへ写す。"""
        index = int(np.clip(density, 0.0, 1.0) * self.levels)
        return min(index, self.levels - 1)

    @property
    def cache_key(self) -> str:
        """キャッシュ配置と `dictionary_id` の元になるキー。"""
        return dictionary_cache_key(
            self.font,
            self.charset,
            self.settings,
            levels=self.levels,
            scale=self.scale,
        )

    @property
    def dictionary_id(self) -> str:
        """manifest の `fonts.dictionary_id`。表記は `dict:sha256:<64 桁>`。"""
        return DICTIONARY_ID_PREFIX + self.cache_key

    def to_dict(self) -> dict[str, Any]:
        """辞書実体の内容。同じ条件なら同じ内容になる（P1-026）。"""
        return {
            "schema_version": DICTIONARY_SCHEMA_VERSION,
            "dictionary_id": self.dictionary_id,
            "font": self.font.to_dict(),
            "charset": self.charset.to_dict(),
            "render_settings": self.settings.to_dict(),
            "levels": self.levels,
            "scale": str(self.scale),
            "thresholds": list(self.thresholds),
            "entries": {char: ratio for char, ratio in zip(self.chars, self.ratios, strict=True)},
        }

    def to_bytes(self) -> bytes:
        """辞書実体のバイト列。キャッシュ配置と内容ハッシュはこれを対象にする。"""
        return canonical_json(self.to_dict())


def dictionary_cache_key(
    font: FontProfile,
    charset: Charset,
    settings: RenderSettings,
    *,
    levels: int,
    scale: LevelScale,
) -> str:
    """辞書のキャッシュキー。フォント実体のハッシュを入力に取る。"""
    return cache_key(
        Stage.DICTIONARY,
        stage_version=DICTIONARY_STAGE_VERSION,
        inputs=(font.hash,),
        params={
            "charset": charset.to_dict(),
            "render_settings": settings.to_dict(),
            "levels": levels,
            "scale": str(scale),
        },
    )


def build_dictionary(
    font: FontProfile,
    charset: Charset | None = None,
    settings: RenderSettings | None = None,
    *,
    levels: int = 8,
    scale: LevelScale = LevelScale.LINEAR,
    progress: StageProgress | None = None,
) -> DensityDictionary:
    """許可文字集合の各文字を基準セルへ描き、黒画素率と密度クラスを確定する。

    欠落グリフがある場合は描画前に止める（AC-02）。`progress` を渡すと文字単位で
    進捗を通知し、取消要求を確認する（FR-18）。
    """
    charset = charset or build_charset()
    settings = settings or RenderSettings()
    _validate_levels(levels)
    settings.validate()
    font.require(charset.chars)

    loaded = load_font(font, settings)
    ratios: list[float] = []
    for index, char in enumerate(charset.chars, start=1):
        ratio = black_ratio(render_cell(char, loaded, settings), settings)
        ratios.append(round(ratio, FLOAT_DIGITS))
        if progress is not None:
            progress.report(index)

    return DensityDictionary(
        font=font,
        charset=charset,
        settings=settings,
        levels=levels,
        scale=scale,
        ratios=tuple(ratios),
        thresholds=_thresholds(ratios, levels, scale),
    )


def _thresholds(ratios: list[float], levels: int, scale: LevelScale) -> tuple[float, ...]:
    """密度クラスの境界（`levels - 1` 個、昇順）を求める。"""
    values = np.asarray(ratios, dtype=np.float64)
    fractions = np.arange(1, levels) / levels
    if scale is LevelScale.QUANTILE:
        bounds = np.quantile(values, fractions)
    else:
        low, high = float(values.min()), float(values.max())
        bounds = low + (high - low) * fractions
    # 丸め後も昇順を保つ。同値が並んでも境界の順序は崩さない。
    return tuple(round(float(bound), FLOAT_DIGITS) for bound in np.maximum.accumulate(bounds))


def _validate_levels(levels: int) -> None:
    if not MIN_DENSITY_LEVELS <= levels <= MAX_DENSITY_LEVELS:
        raise _invalid_levels(
            f"密度クラスは {MIN_DENSITY_LEVELS}〜{MAX_DENSITY_LEVELS} 段階: {levels}"
        )


def _invalid_levels(message: str) -> StageError:
    return StageError(
        _STAGE,
        "invalid_levels",
        message,
        hint="density.levels を 5〜10 の範囲で設定する。",
    )


def _unknown_char(char: str) -> StageError:
    return StageError(
        _STAGE,
        "unknown_char",
        f"密度辞書に無い文字: {char!r} (U+{ord(char):04X})",
        hint="許可文字集合に含めて辞書を作り直す。",
    )
