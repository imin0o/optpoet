"""PNG / TXT / project JSON の書き出しとセル列の検証（P1-042 / P1-043）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from optpoet.errors import StageError
from optpoet.font.profile import load_font_profile
from optpoet.font.render import RenderSettings
from optpoet.hashing import hash_file
from optpoet.image.grid import GridSpec
from optpoet.manifest.store import load_manifest
from optpoet.render.output import (
    TXT_ENCODING,
    encode_txt,
    grid_block,
    render_artwork,
    render_metadata,
    style_block,
    verify_cells,
    write_outputs,
)
from optpoet.render.style import RenderStyle
from optpoet.storage import ProjectLayout
from optpoet.text.layout import TextLayout, layout_text

SETTINGS = RenderSettings(pixel_size=16, cell_width=20, cell_height=20)
GRID = GridSpec(columns=3, rows=2)


def build_layout() -> TextLayout:
    return layout_text("あいうえお", GRID)


def test_txt_keeps_one_line_per_grid_row() -> None:
    txt = encode_txt(build_layout())
    text = txt.decode(TXT_ENCODING)
    assert not txt.startswith(b"\xef\xbb\xbf")
    assert text.endswith("\n")
    assert [len(line) for line in text.split("\n")[:-1]] == [3, 3]


def test_cell_check_counts_match_grid(font_file: Path) -> None:
    artwork = render_artwork(build_layout(), load_font_profile(font_file), SETTINGS)
    assert artwork.cell_check.expected_cells == GRID.cells
    assert artwork.cell_check.displayed_chars == GRID.cells
    assert artwork.cell_check.result == "ok"


def test_png_size_mismatch_is_rejected() -> None:
    layout = build_layout()
    txt = encode_txt(layout)
    with pytest.raises(StageError) as info:
        verify_cells(layout, Image.new("L", (10, 10), 255), SETTINGS, RenderStyle(), txt=txt)
    assert info.value.code == "cell_mismatch"


def test_truncated_txt_is_rejected() -> None:
    layout = build_layout()
    image = Image.new("L", (60, 40), 255)
    with pytest.raises(StageError) as info:
        verify_cells(layout, image, SETTINGS, RenderStyle(), txt="あい\nえお\n".encode())
    assert info.value.code == "cell_mismatch"


def test_grid_block_records_spacing_and_output_size() -> None:
    style = RenderStyle(char_spacing=24, line_spacing=28)
    block = grid_block(build_layout(), SETTINGS, style)
    assert block["cols"] == 3
    assert block["rows"] == 2
    assert block["font_size"] == SETTINGS.pixel_size
    assert block["char_spacing"] == 24
    assert block["line_spacing"] == 28
    assert block["output_size"] == {"width": 72, "height": 56}


def test_render_metadata_matches_dictionary_settings() -> None:
    """I-03 のため、`render_metadata` は辞書と共有する描画設定そのものにする。"""
    assert render_metadata(SETTINGS) == SETTINGS.to_dict()


def test_style_block_records_appearance() -> None:
    style = style_block(SETTINGS, RenderStyle(binarize=0.5, invert=True))
    assert style["binarize"] == 0.5
    assert style["invert"] is True
    assert style["char_spacing"] == 20
    assert style["foreground_color"] == [0, 0, 0]


def test_settings_differing_from_dictionary_are_rejected(
    font_file: Path,
    project_layout: ProjectLayout,
    materialized_manifest: dict[str, Any],
) -> None:
    """辞書と違う描画設定のまま出力しない（I-03 / NFR-02）。"""
    artwork = render_artwork(build_layout(), load_font_profile(font_file), SETTINGS)
    with pytest.raises(StageError) as info:
        write_outputs(project_layout, artwork, materialized_manifest)
    assert info.value.code == "settings_mismatch"


def test_write_outputs_commits_png_txt_and_manifest(
    font_file: Path,
    project_layout: ProjectLayout,
    materialized_manifest: dict[str, Any],
) -> None:
    materialized_manifest["fonts"]["render_settings"] = SETTINGS.to_dict()
    artwork = render_artwork(build_layout(), load_font_profile(font_file), SETTINGS)
    result = write_outputs(project_layout, artwork, materialized_manifest)

    assert project_layout.output_png_path.read_bytes() == artwork.png
    assert project_layout.output_txt_path.read_bytes() == artwork.txt
    assert result.png_ref["hash"] == hash_file(project_layout.output_png_path)
    assert result.txt_ref["path"] == "outputs/artwork.txt"

    saved = load_manifest(result.save.manifest_path).data
    assert saved["outputs"]["png_ref"] == result.png_ref
    assert saved["outputs"]["render_metadata"] == SETTINGS.to_dict()
    assert saved["outputs"]["style"]["invert"] is False
    assert saved["text"]["final_ref"]["hash"] == result.txt_ref["hash"]
    assert saved["grid"]["output_size"] == {"width": 60, "height": 40}
    assert saved["evaluation"]["cell_check"] == {
        "expected_cells": 6,
        "displayed_chars": 6,
        "result": "ok",
    }
