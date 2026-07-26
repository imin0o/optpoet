"""非破壊の前処理設定と適用（P1-012 / FR-01）。

作者の調整は **設定値** として持ち、原画像も正規化後画像も書き換えない。`Preprocess`
だけを保存しておけば、いつでも同じ結果を作り直せる。やり直しは設定を戻すだけで済む。

適用順は crop → rotate → brightness → contrast → gamma → invert で固定する。
crop は正規化後画像の座標系で指定する（EXIF Orientation は適用済み）。rotate は
時計回りの度数で、余白は背景色で埋める。

未適用の項目も無変換値として明示的に持つ（project manifest の `preprocess` は
「省略で暗黙既定を意味させない」: docs/decisions/project-manifest.md）。crop の
無変換値は原寸と同値の矩形で、`apply_preprocess` の返す設定では必ず確定している。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any

from PIL import Image, ImageEnhance, ImageOps

from optpoet.errors import StageError
from optpoet.image.normalize import WHITE
from optpoet.storage import Stage

# 明るさ・コントラストの許容幅。倍率 1.0 + 値 として掛ける。-1.0 で完全に潰れる。
ADJUST_LIMIT = 1.0
# ガンマの許容幅。これを超える値は階調がほぼ 2 値へ潰れ、密度の手掛かりが消える。
MIN_GAMMA = 0.1
MAX_GAMMA = 10.0

_STAGE = str(Stage.PREPROCESS)


@dataclass(frozen=True, slots=True)
class Crop:
    """トリミング矩形。正規化後画像の左上を原点とする画素座標。"""

    x: int
    y: int
    width: int
    height: int

    @property
    def box(self) -> tuple[int, int, int, int]:
        """Pillow の `crop` へ渡す (left, upper, right, lower)。"""
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    def to_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


@dataclass(frozen=True, slots=True)
class Preprocess:
    """作者が指定する前処理設定。既定値はすべて無変換。

    `crop` の None は「原寸のまま」を意味する。画像サイズが決まる時点で
    `resolved` が実矩形へ確定する。
    """

    crop: Crop | None = None
    rotate: float = 0.0
    brightness: float = 0.0
    contrast: float = 0.0
    gamma: float = 1.0
    invert: bool = False

    def validate(self) -> None:
        """画像サイズに依らない範囲を検査する。"""
        if not math.isfinite(self.rotate):
            raise _invalid("rotate", self.rotate, "有限の角度を指定する。")
        _require_range("brightness", self.brightness, -ADJUST_LIMIT, ADJUST_LIMIT)
        _require_range("contrast", self.contrast, -ADJUST_LIMIT, ADJUST_LIMIT)
        _require_range("gamma", self.gamma, MIN_GAMMA, MAX_GAMMA)

    def resolved(self, size: tuple[int, int]) -> Preprocess:
        """`size` に対して検証し、`crop` を実矩形へ確定した設定を返す。"""
        self.validate()
        width, height = size
        crop = self.crop or Crop(0, 0, width, height)
        if crop.x < 0 or crop.y < 0 or crop.width <= 0 or crop.height <= 0:
            raise StageError(
                _STAGE,
                "invalid_crop",
                f"トリミング矩形が不正: {crop.to_dict()}",
                hint="幅と高さを 1 以上、原点を 0 以上にする。",
            )
        if crop.x + crop.width > width or crop.y + crop.height > height:
            raise StageError(
                _STAGE,
                "crop_out_of_bounds",
                f"トリミング矩形が画像 {width}x{height} をはみ出す: {crop.to_dict()}",
                hint=f"矩形を {width}x{height} の内側へ収める。",
            )
        return replace(self, crop=crop)

    def to_dict(self) -> dict[str, Any]:
        """manifest の `preprocess` へ入れる形。`crop` は未確定なら null。"""
        return {
            "crop": self.crop.to_dict() if self.crop is not None else None,
            "rotate": self.rotate,
            "brightness": self.brightness,
            "contrast": self.contrast,
            "gamma": self.gamma,
            "invert": self.invert,
        }


@dataclass(frozen=True, slots=True)
class PreprocessedImage:
    """前処理後の画像と、実際に適用した設定（`crop` 確定済み）。"""

    image: Image.Image
    settings: Preprocess


def apply_preprocess(
    image: Image.Image,
    settings: Preprocess | None = None,
    *,
    background: tuple[int, int, int] = WHITE,
) -> PreprocessedImage:
    """`settings` を `image` へ適用した新しい画像を返す。元の `image` は変更しない。

    `settings` が None なら無変換の既定値を使う。`background` は回転で生じる余白の色。
    """
    resolved = (settings or Preprocess()).resolved(image.size)
    working = image.crop(resolved.crop.box) if resolved.crop is not None else image.copy()
    working = _rotate(working, resolved.rotate, background)
    working = _adjust(working, resolved)
    return PreprocessedImage(image=working, settings=resolved)


def _rotate(image: Image.Image, angle: float, background: tuple[int, int, int]) -> Image.Image:
    """時計回りに `angle` 度回す。Pillow は反時計回りなので符号を反転する。"""
    if angle % 360 == 0:
        return image
    return image.rotate(
        -angle,
        resample=Image.Resampling.BICUBIC,
        expand=True,
        fillcolor=background,
    )


def _adjust(image: Image.Image, settings: Preprocess) -> Image.Image:
    """階調を調整する。無変換値の項目は処理自体を飛ばし、再標本化の劣化を足さない。"""
    working = image
    if settings.brightness != 0.0:
        working = ImageEnhance.Brightness(working).enhance(1.0 + settings.brightness)
    if settings.contrast != 0.0:
        working = ImageEnhance.Contrast(working).enhance(1.0 + settings.contrast)
    if settings.gamma != 1.0:
        working = _gamma(working, settings.gamma)
    if settings.invert:
        working = ImageOps.invert(working)
    return working


def _gamma(image: Image.Image, gamma: float) -> Image.Image:
    """out = 255 * (in/255)^(1/gamma)。gamma > 1 で中間調が明るくなる。"""
    exponent = 1.0 / gamma
    table = [round(255.0 * (level / 255.0) ** exponent) for level in range(256)]
    return image.point(table * len(image.getbands()))


def _require_range(name: str, value: float, low: float, high: float) -> None:
    # NaN は比較がすべて False になるため、この判定で範囲外側へ落ちる。
    if not low <= value <= high:
        raise _invalid(name, value, f"{low}〜{high} の範囲にする。")


def _invalid(name: str, value: float, hint: str) -> StageError:
    return StageError(
        _STAGE,
        "invalid_adjustment",
        f"preprocess.{name} の値が不正: {value!r}",
        hint=hint,
    )
