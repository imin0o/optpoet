"""入力画像の EXIF Orientation・ICC・透過を正規化する（P1-011 / FR-01）。

以降の工程（密度マップ、エッジ、描画）は「向きが正しい sRGB の RGB 画像」だけを前提に
できるよう、ここで表現の揺れを吸収する。

1. **EXIF Orientation**: 回転・反転を実画素へ適用する。以降は Orientation を見ない。
2. **ICC プロファイル**: 埋め込みがあれば sRGB へ変換する。無い場合は sRGB とみなす。
3. **透過**: アルファを背景色（既定は白）で合成し、RGB へ落とす。密度は不透明前提で測る。

適用した変換は `Normalization` へ残す。project manifest の `input.normalization`
（docs/decisions/project-manifest.md）へそのまま入れられる形にする。

EXIF は正規化後の画像から落とす。位置情報や撮影機器情報を後段（外部 AI 送信を含む）へ
運ばないため（FR-01 / docs/quality-and-operations.md 秘密情報要件）。
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageCms, ImageOps

# 透過の合成先。評価側もアルファを白で合成する（docs/environment/evaluation-metrics.md）。
WHITE: tuple[int, int, int] = (255, 255, 255)

_ORIENTATION_TAG = 0x0112
_ALPHA_MODES = frozenset({"RGBA", "LA", "PA", "La"})


@dataclass(frozen=True, slots=True)
class Normalization:
    """正規化で実際に適用した変換の記録。"""

    source_mode: str
    orientation: int
    icc_source: str | None
    icc_applied: bool
    icc_error: str | None
    alpha_flattened: bool
    background: tuple[int, int, int]
    exif_removed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_mode": self.source_mode,
            "orientation": self.orientation,
            "icc_source": self.icc_source,
            "icc_applied": self.icc_applied,
            "icc_error": self.icc_error,
            "alpha_flattened": self.alpha_flattened,
            "background": list(self.background),
            "exif_removed": self.exif_removed,
        }


@dataclass(frozen=True, slots=True)
class NormalizedImage:
    """正規化後の RGB 画像と、その来歴。"""

    image: Image.Image
    normalization: Normalization


def normalize_image(
    image: Image.Image,
    *,
    background: tuple[int, int, int] = WHITE,
) -> NormalizedImage:
    """`image` を向き・色空間・透過について正規化し、sRGB の RGB 画像を返す。

    元の `image` は変更しない。ICC 変換に失敗した場合は変換せずに続行し、理由を
    `Normalization.icc_error` へ残す（黙って捨てない）。
    """
    source_mode = image.mode
    had_exif = bool(image.getexif())
    orientation = _orientation(image)

    working = ImageOps.exif_transpose(image) or image
    icc_source, icc_applied, icc_error, working = _to_srgb(working)
    flattened = _has_alpha(working)
    working = _flatten(working, background) if flattened else working.convert("RGB")

    working.info.pop("exif", None)
    working.info.pop("icc_profile", None)
    return NormalizedImage(
        image=working,
        normalization=Normalization(
            source_mode=source_mode,
            orientation=orientation,
            icc_source=icc_source,
            icc_applied=icc_applied,
            icc_error=icc_error,
            alpha_flattened=flattened,
            background=background,
            exif_removed=had_exif,
        ),
    )


def _orientation(image: Image.Image) -> int:
    """EXIF Orientation を返す。未設定・範囲外は無変換の 1 とみなす。"""
    value = image.getexif().get(_ORIENTATION_TAG)
    if isinstance(value, int) and 1 <= value <= 8:
        return value
    return 1


def _has_alpha(image: Image.Image) -> bool:
    # P モードは transparency キーで単色透過を持つことがある。
    return image.mode in _ALPHA_MODES or "transparency" in image.info


def _to_srgb(image: Image.Image) -> tuple[str | None, bool, str | None, Image.Image]:
    """埋め込み ICC があれば sRGB へ変換し、(元プロファイル名, 適用可否, 失敗理由, 画像)。"""
    profile_bytes = image.info.get("icc_profile")
    if not profile_bytes:
        return None, False, None, image
    try:
        source = ImageCms.ImageCmsProfile(io.BytesIO(profile_bytes))
        name = ImageCms.getProfileDescription(source).strip() or None
        target = ImageCms.createProfile("sRGB")
        converted = ImageCms.profileToProfile(
            _cms_input(image),
            source,
            target,
            outputMode="RGBA" if _has_alpha(image) else "RGB",
        )
    except (ImageCms.PyCMSError, OSError, ValueError) as exc:
        # 壊れた ICC で工程全体を止めない。sRGB とみなして続け、記録に残す。
        return None, False, f"{type(exc).__name__}: {exc}", image
    if converted is None:
        return name, False, "profileToProfile が変換結果を返さない", image
    return name, True, None, converted


def _cms_input(image: Image.Image) -> Image.Image:
    """littleCMS が直接扱えないモード（P など）を RGB / RGBA へ寄せる。"""
    if image.mode in {"RGB", "RGBA", "L", "LA", "CMYK"}:
        return image
    return image.convert("RGBA" if _has_alpha(image) else "RGB")


def _flatten(image: Image.Image, background: tuple[int, int, int]) -> Image.Image:
    """アルファを背景色で合成して RGB にする。"""
    rgba = image.convert("RGBA")
    canvas = Image.new("RGB", rgba.size, background)
    canvas.paste(rgba, mask=rgba.getchannel("A"))
    return canvas
