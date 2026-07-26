"""EXIF Orientation・ICC・透過の正規化の検証（P1-011 / FR-01）。"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image, ImageCms

from optpoet.image import Normalization, NormalizedImage, normalize_image

ORIENTATION_TAG = 0x0112


def _srgb_bytes() -> bytes:
    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def _jpeg_with_orientation(path: Path, orientation: int) -> Image.Image:
    image = Image.new("RGB", (40, 20), color=(200, 40, 40))
    exif = image.getexif()
    exif[ORIENTATION_TAG] = orientation
    image.save(path, format="JPEG", exif=exif)
    return Image.open(path)


def test_returns_srgb_rgb_image() -> None:
    result = normalize_image(Image.new("RGB", (8, 6), color=(10, 20, 30)))
    assert isinstance(result, NormalizedImage)
    assert isinstance(result.normalization, Normalization)
    assert result.image.mode == "RGB"
    assert result.image.size == (8, 6)


def test_applies_exif_orientation_rotation(tmp_path: Path) -> None:
    """Orientation 6（90 度回転）は実画素へ適用し、以降は向きを見なくて済む。"""
    source = _jpeg_with_orientation(tmp_path / "rotated.jpg", 6)
    result = normalize_image(source)
    assert result.normalization.orientation == 6
    assert source.size == (40, 20)
    assert result.image.size == (20, 40)


def test_orientation_one_keeps_size(tmp_path: Path) -> None:
    source = _jpeg_with_orientation(tmp_path / "upright.jpg", 1)
    result = normalize_image(source)
    assert result.normalization.orientation == 1
    assert result.image.size == (40, 20)


def test_missing_orientation_is_treated_as_one() -> None:
    result = normalize_image(Image.new("RGB", (4, 4)))
    assert result.normalization.orientation == 1


def test_out_of_range_orientation_is_treated_as_one(tmp_path: Path) -> None:
    source = _jpeg_with_orientation(tmp_path / "broken_tag.jpg", 99)
    result = normalize_image(source)
    assert result.normalization.orientation == 1
    assert result.image.size == (40, 20)


def test_exif_is_removed_from_result(tmp_path: Path) -> None:
    source = _jpeg_with_orientation(tmp_path / "tagged.jpg", 6)
    result = normalize_image(source)
    assert result.normalization.exif_removed is True
    assert "exif" not in result.image.info
    assert not result.image.getexif()


def test_exif_removed_is_false_without_exif() -> None:
    result = normalize_image(Image.new("RGB", (4, 4)))
    assert result.normalization.exif_removed is False


def test_converts_embedded_icc_to_srgb(tmp_path: Path) -> None:
    path = tmp_path / "icc.png"
    Image.new("RGB", (8, 8), color=(120, 60, 30)).save(
        path, format="PNG", icc_profile=_srgb_bytes()
    )
    result = normalize_image(Image.open(path))
    assert result.normalization.icc_applied is True
    assert result.normalization.icc_source is not None
    assert result.normalization.icc_error is None
    assert "icc_profile" not in result.image.info


def test_no_icc_profile_is_assumed_srgb() -> None:
    result = normalize_image(Image.new("RGB", (4, 4)))
    assert result.normalization.icc_applied is False
    assert result.normalization.icc_source is None
    assert result.normalization.icc_error is None


def test_broken_icc_profile_is_recorded_and_skipped(tmp_path: Path) -> None:
    """壊れた ICC で工程を止めず、sRGB とみなして続ける。理由は記録へ残す。"""
    path = tmp_path / "broken_icc.png"
    Image.new("RGB", (8, 8), color=(120, 60, 30)).save(
        path, format="PNG", icc_profile=b"not an icc profile"
    )
    result = normalize_image(Image.open(path))
    assert result.normalization.icc_applied is False
    assert result.normalization.icc_error is not None
    assert result.image.mode == "RGB"


def test_flattens_alpha_onto_white_by_default() -> None:
    image = Image.new("RGBA", (2, 1), color=(0, 0, 0, 0))
    image.putpixel((1, 0), (0, 0, 0, 255))
    result = normalize_image(image)
    assert result.normalization.alpha_flattened is True
    assert result.normalization.background == (255, 255, 255)
    assert result.image.getpixel((0, 0)) == (255, 255, 255)
    assert result.image.getpixel((1, 0)) == (0, 0, 0)


def test_flattens_alpha_onto_given_background() -> None:
    image = Image.new("RGBA", (1, 1), color=(255, 255, 255, 0))
    result = normalize_image(image, background=(0, 0, 0))
    assert result.image.getpixel((0, 0)) == (0, 0, 0)
    assert result.normalization.background == (0, 0, 0)


def test_flattens_palette_transparency(tmp_path: Path) -> None:
    """P モードの単色透過も透過として扱う。"""
    path = tmp_path / "palette.png"
    Image.new("RGBA", (2, 1), color=(0, 0, 0, 0)).convert("P", palette=Image.Palette.ADAPTIVE).save(
        path, format="PNG", transparency=0
    )
    result = normalize_image(Image.open(path))
    assert result.normalization.alpha_flattened is True
    assert result.image.mode == "RGB"


def test_flattens_la_mode() -> None:
    image = Image.new("LA", (1, 1), color=(0, 0))
    result = normalize_image(image)
    assert result.normalization.alpha_flattened is True
    assert result.image.getpixel((0, 0)) == (255, 255, 255)


def test_opaque_image_is_not_flagged_as_flattened() -> None:
    result = normalize_image(Image.new("RGB", (4, 4)))
    assert result.normalization.alpha_flattened is False


def test_converts_grayscale_to_rgb() -> None:
    result = normalize_image(Image.new("L", (4, 4), color=90))
    assert result.normalization.source_mode == "L"
    assert result.image.mode == "RGB"
    assert result.image.getpixel((0, 0)) == (90, 90, 90)


def test_converts_cmyk_to_rgb() -> None:
    result = normalize_image(Image.new("CMYK", (4, 4)))
    assert result.normalization.source_mode == "CMYK"
    assert result.image.mode == "RGB"


def test_source_image_is_not_mutated(tmp_path: Path) -> None:
    source = _jpeg_with_orientation(tmp_path / "keep.jpg", 6)
    normalize_image(source)
    assert source.size == (40, 20)
    assert source.getexif()[ORIENTATION_TAG] == 6


def test_normalization_payload_is_serializable(tmp_path: Path) -> None:
    path = tmp_path / "payload.png"
    Image.new("RGBA", (4, 4), color=(1, 2, 3, 0)).save(
        path, format="PNG", icc_profile=_srgb_bytes()
    )
    payload = normalize_image(Image.open(path)).normalization.to_dict()
    assert payload["source_mode"] == "RGBA"
    assert payload["orientation"] == 1
    assert payload["icc_applied"] is True
    assert payload["alpha_flattened"] is True
    assert payload["background"] == [255, 255, 255]


@pytest.mark.parametrize("image_format", ["JPEG", "PNG", "TIFF", "WEBP"])
def test_accepts_every_supported_format(tmp_path: Path, image_format: str) -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (16, 12), color=(70, 80, 90)).save(buffer, format=image_format)
    buffer.seek(0)
    result = normalize_image(Image.open(buffer))
    assert result.image.mode == "RGB"
    assert result.image.size == (16, 12)
