"""密度辞書と同じ描画エンジンでのグリッド描画（P1-040 / P1-041 / NFR-02）。"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from optpoet.errors import StageError
from optpoet.font.profile import load_font_profile
from optpoet.font.render import RenderSettings, load_font, render_cell
from optpoet.image.grid import GridSpec
from optpoet.render.grid import cell_origin, output_size, render_grid
from optpoet.render.style import RenderStyle
from optpoet.text.layout import TextLayout, layout_text

SETTINGS = RenderSettings(pixel_size=16, cell_width=20, cell_height=20)
GRID = GridSpec(columns=3, rows=2)


def build_layout() -> TextLayout:
    return layout_text("あいうえお", GRID)


def test_cell_region_matches_measured_cell(font_file: Path) -> None:
    """グリッドのセル領域が、辞書測定に使うセル画像と一致する（NFR-02）。"""
    profile = load_font_profile(font_file)
    layout = build_layout()
    image = render_grid(layout, profile, SETTINGS)

    x, y = cell_origin(1, 0, SETTINGS, RenderStyle())
    placed = np.asarray(image.crop((x, y, x + SETTINGS.cell_width, y + SETTINGS.cell_height)))
    measured = render_cell("え", load_font(profile, SETTINGS), SETTINGS)
    assert image.mode == "L"
    assert np.array_equal(placed, measured)


def test_render_is_deterministic(font_file: Path) -> None:
    profile = load_font_profile(font_file)
    layout = build_layout()
    first = np.asarray(render_grid(layout, profile, SETTINGS))
    second = np.asarray(render_grid(layout, profile, SETTINGS))
    assert np.array_equal(first, second)


def test_output_size_reflects_spacing(font_file: Path) -> None:
    style = RenderStyle(char_spacing=24, line_spacing=28)
    assert output_size(GRID, SETTINGS, style) == (72, 56)
    image = render_grid(build_layout(), load_font_profile(font_file), SETTINGS, style)
    assert image.size == (72, 56)


def test_binarize_leaves_two_levels(font_file: Path) -> None:
    image = render_grid(
        build_layout(),
        load_font_profile(font_file),
        SETTINGS,
        RenderStyle(binarize=0.5),
    )
    assert set(np.unique(np.asarray(image))) <= {0, 255}


def test_invert_swaps_ink_and_paper(font_file: Path) -> None:
    profile = load_font_profile(font_file)
    layout = build_layout()
    normal = np.asarray(render_grid(layout, profile, SETTINGS))
    inverted = np.asarray(render_grid(layout, profile, SETTINGS, RenderStyle(invert=True)))
    assert np.array_equal(inverted, 255 - normal)


def test_colored_style_produces_rgb(font_file: Path) -> None:
    style = RenderStyle(foreground=(200, 0, 0), background=(0, 0, 40))
    image = render_grid(build_layout(), load_font_profile(font_file), SETTINGS, style)
    assert image.mode == "RGB"
    assert image.getpixel((0, 0)) == (0, 0, 40)


def test_missing_glyph_stops_before_drawing(font_file: Path) -> None:
    """欠落グリフを豆腐で描かず、描画前に止める（AC-02）。"""
    profile = load_font_profile(font_file)
    # 面 14 のタグ文字。日本語フォントは収録しない。
    layout = TextLayout.from_cells(("\U000e0020",) * GRID.cells, GRID)
    with pytest.raises(StageError) as info:
        render_grid(layout, profile, SETTINGS)
    assert info.value.code == "missing_glyph"


@pytest.mark.parametrize(
    "style",
    [
        RenderStyle(char_spacing=8),
        RenderStyle(line_spacing=8),
        RenderStyle(binarize=1.5),
        RenderStyle(foreground=(0, 0, 0), background=(0, 0, 0)),
    ],
)
def test_invalid_style_is_rejected(style: RenderStyle) -> None:
    with pytest.raises(StageError) as info:
        style.validate(SETTINGS)
    assert info.value.code == "invalid_style"
