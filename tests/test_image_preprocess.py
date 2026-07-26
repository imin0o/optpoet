"""非破壊前処理の設定と適用の検証（P1-012 / FR-01）。"""

from __future__ import annotations

import math

import pytest
from PIL import Image

from optpoet.errors import ErrorKind, StageError
from optpoet.image import Crop, Preprocess, PreprocessedImage, apply_preprocess


def _gradient(width: int = 8, height: int = 4) -> Image.Image:
    """左右で明るさが変わる画像。コントラスト調整の効果が見える。"""
    image = Image.new("RGB", (width, height), color=(40, 40, 40))
    for x in range(width // 2, width):
        for y in range(height):
            image.putpixel((x, y), (200, 200, 200))
    return image


def _level(image: Image.Image, xy: tuple[int, int]) -> int:
    """画素の R 成分。ここで使う画像は無彩色なので明度として読める。"""
    pixel = image.getpixel(xy)
    assert isinstance(pixel, tuple)
    return int(pixel[0])


def test_default_settings_change_nothing() -> None:
    source = _gradient()
    result = apply_preprocess(source)
    assert isinstance(result, PreprocessedImage)
    assert result.image.size == source.size
    assert result.image.tobytes() == source.tobytes()


def test_source_image_is_not_mutated() -> None:
    """非破壊。設定を適用しても元画像は元のまま残る。"""
    source = _gradient()
    before = source.tobytes()
    apply_preprocess(source, Preprocess(crop=Crop(0, 0, 2, 2), invert=True))
    assert source.size == (8, 4)
    assert source.tobytes() == before


def test_crop_extracts_rectangle() -> None:
    source = _gradient()
    result = apply_preprocess(source, Preprocess(crop=Crop(4, 1, 3, 2)))
    assert result.image.size == (3, 2)
    assert result.image.getpixel((0, 0)) == (200, 200, 200)


def test_unset_crop_is_resolved_to_full_size() -> None:
    """未適用の crop も原寸矩形として確定する（manifest で省略を許さないため）。"""
    result = apply_preprocess(_gradient(), Preprocess())
    assert result.settings.crop == Crop(0, 0, 8, 4)


def test_crop_outside_image_is_rejected() -> None:
    with pytest.raises(StageError) as excinfo:
        apply_preprocess(_gradient(), Preprocess(crop=Crop(6, 0, 4, 2)))
    error = excinfo.value
    assert error.stage == "preprocess"
    assert error.code == "crop_out_of_bounds"
    assert error.kind is ErrorKind.NEEDS_CONFIG
    assert error.hint is not None


def test_empty_crop_is_rejected() -> None:
    with pytest.raises(StageError) as excinfo:
        apply_preprocess(_gradient(), Preprocess(crop=Crop(0, 0, 0, 2)))
    assert excinfo.value.code == "invalid_crop"


def test_negative_crop_origin_is_rejected() -> None:
    with pytest.raises(StageError) as excinfo:
        apply_preprocess(_gradient(), Preprocess(crop=Crop(-1, 0, 2, 2)))
    assert excinfo.value.code == "invalid_crop"


def test_rotate_is_clockwise() -> None:
    """左上の印が右上へ回る（時計回り 90 度）。"""
    source = Image.new("RGB", (8, 4), color=(0, 0, 0))
    source.putpixel((0, 0), (255, 0, 0))
    result = apply_preprocess(source, Preprocess(rotate=90))
    assert result.image.size == (4, 8)
    assert result.image.getpixel((3, 0)) == (255, 0, 0)


def test_rotate_360_keeps_pixels() -> None:
    source = _gradient()
    result = apply_preprocess(source, Preprocess(rotate=360))
    assert result.image.tobytes() == source.tobytes()


def test_rotate_fills_corners_with_background() -> None:
    source = Image.new("RGB", (8, 8), color=(10, 10, 10))
    result = apply_preprocess(source, Preprocess(rotate=45), background=(0, 255, 0))
    assert result.image.size[0] > 8
    assert result.image.getpixel((0, 0)) == (0, 255, 0)


def test_crop_is_applied_before_rotate() -> None:
    """crop は正規化後画像の座標系。回転前に切るのでサイズが入れ替わる。"""
    result = apply_preprocess(_gradient(), Preprocess(crop=Crop(0, 0, 6, 2), rotate=90))
    assert result.image.size == (2, 6)


def test_brightness_raises_levels() -> None:
    source = Image.new("RGB", (2, 2), color=(100, 100, 100))
    result = apply_preprocess(source, Preprocess(brightness=0.5))
    assert result.image.getpixel((0, 0)) == (150, 150, 150)


def test_negative_brightness_lowers_levels() -> None:
    source = Image.new("RGB", (2, 2), color=(100, 100, 100))
    result = apply_preprocess(source, Preprocess(brightness=-0.5))
    assert result.image.getpixel((0, 0)) == (50, 50, 50)


def test_contrast_widens_the_gap() -> None:
    source = _gradient()
    plain = apply_preprocess(source).image
    result = apply_preprocess(source, Preprocess(contrast=0.5)).image
    assert _level(result, (0, 0)) < _level(plain, (0, 0))
    assert _level(result, (7, 0)) > _level(plain, (7, 0))


def test_gamma_above_one_brightens_midtones() -> None:
    source = Image.new("RGB", (2, 2), color=(128, 128, 128))
    result = apply_preprocess(source, Preprocess(gamma=2.0))
    # 255 * (128/255)^(1/2) = 180.7
    assert result.image.getpixel((0, 0)) == (181, 181, 181)


def test_gamma_below_one_darkens_midtones() -> None:
    source = Image.new("RGB", (2, 2), color=(128, 128, 128))
    result = apply_preprocess(source, Preprocess(gamma=0.5))
    assert _level(result.image, (0, 0)) < 128


def test_gamma_one_keeps_pixels() -> None:
    source = _gradient()
    result = apply_preprocess(source, Preprocess(gamma=1.0))
    assert result.image.tobytes() == source.tobytes()


def test_invert_flips_levels() -> None:
    source = Image.new("RGB", (2, 2), color=(30, 60, 90))
    result = apply_preprocess(source, Preprocess(invert=True))
    assert result.image.getpixel((0, 0)) == (225, 195, 165)


def test_adjustments_combine_in_fixed_order() -> None:
    """gamma の後に invert。逆順なら結果が変わる組み合わせで確かめる。"""
    source = Image.new("RGB", (2, 2), color=(128, 128, 128))
    result = apply_preprocess(source, Preprocess(gamma=2.0, invert=True))
    assert result.image.getpixel((0, 0)) == (74, 74, 74)


@pytest.mark.parametrize(
    "settings",
    [
        Preprocess(brightness=1.5),
        Preprocess(brightness=-1.5),
        Preprocess(contrast=2.0),
        Preprocess(gamma=0.0),
        Preprocess(gamma=20.0),
        Preprocess(gamma=math.nan),
    ],
)
def test_out_of_range_adjustment_is_rejected(settings: Preprocess) -> None:
    with pytest.raises(StageError) as excinfo:
        apply_preprocess(_gradient(), settings)
    assert excinfo.value.code == "invalid_adjustment"
    assert excinfo.value.kind is ErrorKind.NEEDS_CONFIG


def test_non_finite_rotate_is_rejected() -> None:
    with pytest.raises(StageError) as excinfo:
        apply_preprocess(_gradient(), Preprocess(rotate=math.inf))
    assert excinfo.value.code == "invalid_adjustment"


def test_validate_does_not_need_an_image() -> None:
    Preprocess(brightness=0.2, gamma=1.5).validate()
    with pytest.raises(StageError):
        Preprocess(contrast=3.0).validate()


def test_payload_matches_manifest_shape() -> None:
    result = apply_preprocess(_gradient(), Preprocess(contrast=0.15, gamma=1.1))
    payload = result.settings.to_dict()
    assert payload == {
        "crop": {"x": 0, "y": 0, "width": 8, "height": 4},
        "rotate": 0.0,
        "brightness": 0.0,
        "contrast": 0.15,
        "gamma": 1.1,
        "invert": False,
    }


def test_payload_keeps_unresolved_crop_null() -> None:
    assert Preprocess().to_dict()["crop"] is None


def test_settings_are_reusable_for_the_same_result() -> None:
    """設定を持ち回れば同じ結果を作り直せる（非破壊のやり直し）。"""
    source = _gradient()
    settings = Preprocess(crop=Crop(1, 0, 5, 3), rotate=90, gamma=1.4, invert=True)
    first = apply_preprocess(source, settings).image
    second = apply_preprocess(source, settings).image
    assert first.tobytes() == second.tobytes()
