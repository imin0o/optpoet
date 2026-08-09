"""密度測定と最終描画で共有する 1 セル描画（P1-022 / NFR-02）。

docs/environment/rendering-engine.md の決定に従い、描画は Pillow の
`ImageDraw.text` + `ImageFont.truetype`（FreeType, `layout_engine=BASIC`）だけを使う。
測定専用・描画専用の別実装を持たず、密度辞書も最終 PNG も `render_cell()` を通す。
P0-014 のスパイクで、この経路が測定と最終描画でバイト一致し、プロセス内外で決定的で
あることを実測済み（docs/environment/pixel-identity-spike.md）。

`RenderSettings` は辞書キーへ入る描画設定そのもの（P1-023）。ここに含めない値が描画へ
影響すると、同じキーで別の画素が出る。設定を増やすときは辞書の `stage_version` を上げる
（docs/decisions/change-management.md）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import PIL
from numpy.typing import NDArray
from PIL import Image, ImageDraw, ImageFont
from PIL import features as pil_features

from optpoet.errors import StageError
from optpoet.font.profile import FontProfile
from optpoet.storage import Stage

ENGINE = "pillow"
LAYOUT_ENGINE = "BASIC"
"""決定性を優先し libraqm を使わない（rendering-engine.md）。"""

_STAGE = str(Stage.DICTIONARY)

Cell = NDArray[np.uint8]


@dataclass(frozen=True, slots=True)
class RenderSettings:
    """1 セルの描画設定。密度測定と最終描画で共有する。

    `variation_axes` は可変フォントの軸固定値で、順序はフォントの `fvar` 軸順に従う。
    空なら既定インスタンスで描く（pixel-identity-spike.md「可変フォントの軸固定」）。
    """

    pixel_size: int = 48
    cell_width: int = 64
    cell_height: int = 64
    mode: str = "L"
    background: int = 255
    foreground: int = 0
    anchor: str = "mm"
    variation_axes: tuple[float, ...] = ()

    @property
    def cell_size(self) -> tuple[int, int]:
        return (self.cell_width, self.cell_height)

    def validate(self) -> None:
        if self.pixel_size <= 0:
            raise _invalid_settings(f"pixel_size は 1 以上: {self.pixel_size}")
        if self.cell_width <= 0 or self.cell_height <= 0:
            raise _invalid_settings(f"セル寸法は 1 以上: {self.cell_width}x{self.cell_height}")
        if self.mode != "L":
            # 密度は輝度から算出する。他モードは黒画素率の定義が変わるため受けない。
            raise _invalid_settings(f"mode は L 固定: {self.mode!r}")
        for name, value in (("background", self.background), ("foreground", self.foreground)):
            if not 0 <= value <= 255:
                raise _invalid_settings(f"{name} は 0〜255: {value}")
        if self.background == self.foreground:
            raise _invalid_settings("background と foreground が同値では密度差が出ない")

    def to_dict(self) -> dict[str, Any]:
        """manifest の `fonts.render_settings`。エンジン版まで含めて同一性の根拠にする。"""
        return {
            "engine": ENGINE,
            "engine_version": PIL.__version__,
            "freetype_version": pil_features.version("freetype2") or "unknown",
            "layout_engine": LAYOUT_ENGINE,
            "mode": self.mode,
            "pixel_size": self.pixel_size,
            "cell": {"width": self.cell_width, "height": self.cell_height},
            "background": self.background,
            "foreground": self.foreground,
            "antialias": True,
            "anchor": self.anchor,
            "variation_axes": list(self.variation_axes),
        }


def load_font(profile: FontProfile, settings: RenderSettings) -> ImageFont.FreeTypeFont:
    """測定・描画で共有するフォントを読み込む唯一の入口。"""
    settings.validate()
    try:
        font = ImageFont.truetype(
            str(profile.path),
            settings.pixel_size,
            layout_engine=ImageFont.Layout.BASIC,
        )
    except OSError as exc:
        raise StageError(
            _STAGE,
            "font_unreadable",
            f"フォントを読み込めない: {profile.path}",
            hint="フォントファイルが壊れていないか確認する。",
        ) from exc
    if settings.variation_axes:
        _set_variation(font, settings)
    return font


def render_cell(char: str, font: ImageFont.FreeTypeFont, settings: RenderSettings) -> Cell:
    """1 セル（1 文字）を描画して配列で返す。測定も最終描画もこの関数だけを通す。"""
    image = Image.new(settings.mode, settings.cell_size, settings.background)
    draw = ImageDraw.Draw(image)
    draw.text(
        (settings.cell_width / 2, settings.cell_height / 2),
        char,
        font=font,
        fill=settings.foreground,
        anchor=settings.anchor,
    )
    return np.asarray(image, dtype=np.uint8)


def black_ratio(cell: Cell, settings: RenderSettings) -> float:
    """セルの黒画素率（0.0=背景色のまま, 1.0=全面が描画色）。

    背景色と描画色の差で正規化するため、反転設定（P1-041）でも同じ尺度になる。
    """
    span = settings.background - settings.foreground
    values = cell.astype(np.float64)
    return float(((settings.background - values) / span).mean())


def _set_variation(font: ImageFont.FreeTypeFont, settings: RenderSettings) -> None:
    """可変フォントの軸を固定する。

    Pillow は軸の数が合わなくても黙って受けるため、先に `fvar` の軸数と突き合わせる。
    値が無視されると記録した設定と実際の画素がずれ、NFR-02 が崩れる。
    """
    values = list(settings.variation_axes)
    try:
        axes = font.get_variation_axes()
    except OSError as exc:
        raise StageError(
            _STAGE,
            "invalid_render_settings",
            "可変フォントではないため variation_axes を適用できない",
            hint="variation_axes を空にするか、可変フォントを指定する。",
        ) from exc
    if len(values) != len(axes):
        raise StageError(
            _STAGE,
            "invalid_render_settings",
            f"可変フォントの軸数が合わない: 設定 {len(values)} / フォント {len(axes)}",
            hint="軸の数と順序をフォントの fvar に合わせる。",
        )
    font.set_variation_by_axes(values)


def _invalid_settings(message: str) -> StageError:
    return StageError(
        _STAGE,
        "invalid_render_settings",
        message,
        hint="描画設定を見直す。密度辞書と最終描画で同じ設定を使う。",
    )
