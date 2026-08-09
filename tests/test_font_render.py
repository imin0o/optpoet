"""測定と最終描画で共有する 1 セル描画（P1-022 / P1-023 / NFR-02）。"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from optpoet.errors import StageError
from optpoet.font.profile import load_font_profile
from optpoet.font.render import (
    ENGINE,
    LAYOUT_ENGINE,
    RenderSettings,
    black_ratio,
    load_font,
    render_cell,
)

SETTINGS = RenderSettings(pixel_size=24, cell_width=32, cell_height=32)


def test_render_cell_is_deterministic_across_reloads(font_file: Path) -> None:
    profile = load_font_profile(font_file)
    first = render_cell("永", load_font(profile, SETTINGS), SETTINGS)
    second = render_cell("永", load_font(profile, SETTINGS), SETTINGS)
    assert np.array_equal(first, second)


def test_measured_cell_matches_grid_placement(font_file: Path) -> None:
    """辞書測定用のセルと、グリッドへ貼った最終描画の切り出しが一致する（NFR-02）。"""
    font = load_font(load_font_profile(font_file), SETTINGS)
    measured = render_cell("鬱", font, SETTINGS)

    grid = Image.new(SETTINGS.mode, (SETTINGS.cell_width * 2, SETTINGS.cell_height), 255)
    grid.paste(Image.fromarray(render_cell("鬱", font, SETTINGS)), (SETTINGS.cell_width, 0))
    placed = np.asarray(
        grid.crop((SETTINGS.cell_width, 0, SETTINGS.cell_width * 2, SETTINGS.cell_height))
    )
    assert np.array_equal(measured, placed)


def test_cell_shape_and_dtype(font_file: Path) -> None:
    cell = render_cell("あ", load_font(load_font_profile(font_file), SETTINGS), SETTINGS)
    assert cell.shape == (SETTINGS.cell_height, SETTINGS.cell_width)
    assert cell.dtype == np.uint8


def test_black_ratio_separates_light_and_dark(font_file: Path) -> None:
    font = load_font(load_font_profile(font_file), SETTINGS)
    light = black_ratio(render_cell("の", font, SETTINGS), SETTINGS)
    dark = black_ratio(render_cell("鬱", font, SETTINGS), SETTINGS)
    blank = black_ratio(render_cell(" ", font, SETTINGS), SETTINGS)
    assert blank == pytest.approx(0.0, abs=1e-6)
    assert 0.0 < light < dark < 1.0


def test_render_settings_to_dict_records_engine_versions() -> None:
    settings = SETTINGS.to_dict()
    assert settings["engine"] == ENGINE
    assert settings["layout_engine"] == LAYOUT_ENGINE
    assert settings["cell"] == {"width": 32, "height": 32}
    assert settings["engine_version"] and settings["freetype_version"]


@pytest.mark.parametrize(
    "settings",
    [
        RenderSettings(pixel_size=0),
        RenderSettings(cell_width=0),
        RenderSettings(mode="RGB"),
        RenderSettings(background=300),
        RenderSettings(background=0, foreground=0),
    ],
)
def test_invalid_settings_are_rejected(settings: RenderSettings) -> None:
    with pytest.raises(StageError) as info:
        settings.validate()
    assert info.value.code == "invalid_render_settings"


def test_unknown_variation_axes_are_reported(font_file: Path) -> None:
    profile = load_font_profile(font_file)
    settings = RenderSettings(pixel_size=24, variation_axes=(400.0, 100.0, 100.0, 100.0))
    with pytest.raises(StageError) as info:
        load_font(profile, settings)
    assert info.value.code == "invalid_render_settings"
