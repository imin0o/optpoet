"""文字密度辞書（P1-022 / P1-023 / P1-025 / P1-026）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from optpoet.errors import StageCancelledError, StageError
from optpoet.font.charset import CharsetSpec, build_charset
from optpoet.font.dictionary import (
    DICTIONARY_ID_PREFIX,
    DensityDictionary,
    LevelScale,
    build_dictionary,
)
from optpoet.font.profile import FontProfile, load_font_profile
from optpoet.font.render import RenderSettings
from optpoet.hashing import HASH_PREFIX
from optpoet.pipeline.cancel import CancelToken
from optpoet.pipeline.progress import StageProgress
from optpoet.storage import Stage

SETTINGS = RenderSettings(pixel_size=20, cell_width=24, cell_height=24)
SPEC = CharsetSpec(name="test", version="1.0", ranges=((0x3042, 0x3060),), extra="永鬱の光 ")
SMALL_SPEC = CharsetSpec(name="test", version="1.0", ranges=((0x3042, 0x3046),), extra="")


@pytest.fixture
def profile(font_file: Path) -> FontProfile:
    return load_font_profile(font_file)


@pytest.fixture
def dictionary(profile: FontProfile) -> DensityDictionary:
    return build_dictionary(profile, build_charset(SPEC), SETTINGS, levels=8)


def test_every_char_has_a_ratio(dictionary: DensityDictionary) -> None:
    assert len(dictionary.ratios) == len(dictionary.charset)
    assert all(0.0 <= ratio <= 1.0 for ratio in dictionary.ratios)
    assert dictionary.ratio_of(" ") == pytest.approx(0.0, abs=1e-6)
    assert dictionary.ratio_of("鬱") > dictionary.ratio_of("の")


def test_levels_partition_the_charset(dictionary: DensityDictionary) -> None:
    assert len(dictionary.thresholds) == dictionary.levels - 1
    assert list(dictionary.thresholds) == sorted(dictionary.thresholds)
    collected = [char for level in range(dictionary.levels) for char in dictionary.chars_at(level)]
    assert sorted(collected) == sorted(dictionary.chars)
    assert dictionary.level_of(" ") == 0
    assert dictionary.level_of("鬱") == dictionary.levels - 1


def test_levels_are_configurable(profile: FontProfile) -> None:
    charset = build_charset(SPEC)
    for levels in (5, 10):
        built = build_dictionary(profile, charset, SETTINGS, levels=levels)
        assert built.levels == levels
        assert len(built.thresholds) == levels - 1


@pytest.mark.parametrize("levels", [4, 11])
def test_levels_outside_the_range_are_rejected(profile: FontProfile, levels: int) -> None:
    with pytest.raises(StageError) as info:
        build_dictionary(profile, build_charset(SPEC), SETTINGS, levels=levels)
    assert info.value.code == "invalid_levels"


def test_quantile_scale_spreads_chars_across_levels(profile: FontProfile) -> None:
    charset = build_charset(SPEC)
    built = build_dictionary(profile, charset, SETTINGS, levels=5, scale=LevelScale.QUANTILE)
    counts = [len(built.chars_at(level)) for level in range(built.levels)]
    assert all(count > 0 for count in counts)


def test_density_map_value_maps_to_the_same_levels(dictionary: DensityDictionary) -> None:
    assert dictionary.level_for_density(0.0) == 0
    assert dictionary.level_for_density(1.0) == dictionary.levels - 1


def test_dictionary_id_uses_the_fixed_notation(dictionary: DensityDictionary) -> None:
    assert dictionary.dictionary_id.startswith(f"{DICTIONARY_ID_PREFIX}{HASH_PREFIX}")
    assert dictionary.dictionary_id == DICTIONARY_ID_PREFIX + dictionary.cache_key


def test_key_changes_with_render_settings_and_levels(profile: FontProfile) -> None:
    charset = build_charset(SPEC)
    base = build_dictionary(profile, charset, SETTINGS, levels=8)
    bigger = build_dictionary(profile, charset, RenderSettings(pixel_size=22), levels=8)
    coarse = build_dictionary(profile, charset, SETTINGS, levels=6)
    wider = build_dictionary(
        profile,
        build_charset(CharsetSpec(name="test", version="1.1", ranges=((0x3042, 0x3060),))),
        SETTINGS,
        levels=8,
    )
    keys = {base.cache_key, bigger.cache_key, coarse.cache_key, wider.cache_key}
    assert len(keys) == 4


def test_rebuild_is_byte_identical(profile: FontProfile) -> None:
    charset = build_charset(SPEC)
    first = build_dictionary(profile, charset, SETTINGS, levels=8)
    second = build_dictionary(profile, build_charset(SPEC), SETTINGS, levels=8)
    assert first.to_bytes() == second.to_bytes()
    assert first.dictionary_id == second.dictionary_id


def test_dictionary_body_carries_identity(dictionary: DensityDictionary) -> None:
    body = dictionary.to_dict()
    assert body["font"] == dictionary.font.to_dict()
    assert body["render_settings"] == dictionary.settings.to_dict()
    assert body["charset"]["hash"] == dictionary.charset.hash
    assert len(body["entries"]) == len(dictionary.charset)


def test_missing_glyph_stops_before_rendering(profile: FontProfile) -> None:
    charset = build_charset(
        CharsetSpec(name="test", version="1.0", ranges=((0xE000, 0xE001),), encoding=None)
    )
    with pytest.raises(StageError) as info:
        build_dictionary(profile, charset, SETTINGS)
    assert info.value.code == "missing_glyph"


def test_unknown_char_is_not_silently_zero(dictionary: DensityDictionary) -> None:
    with pytest.raises(StageError) as info:
        dictionary.ratio_of("漢")
    assert info.value.code == "unknown_char"


def test_progress_reports_each_char(profile: FontProfile) -> None:
    charset = build_charset(SMALL_SPEC)
    events: list[int] = []
    progress = StageProgress(
        str(Stage.DICTIONARY),
        total=len(charset),
        sink=lambda event: events.append(event.completed),
    )
    build_dictionary(profile, charset, SETTINGS, progress=progress)
    assert events == list(range(1, len(charset) + 1))


def test_cancel_stops_the_build(profile: FontProfile) -> None:
    charset = build_charset(SMALL_SPEC)
    token = CancelToken()
    token.cancel()
    progress = StageProgress(str(Stage.DICTIONARY), total=len(charset), cancel=token)
    with pytest.raises(StageCancelledError):
        build_dictionary(profile, charset, SETTINGS, progress=progress)
