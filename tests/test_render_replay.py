"""保存・再読込後の再生（P1-046）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from optpoet.errors import StageError
from optpoet.font.profile import load_font_profile
from optpoet.font.render import RenderSettings
from optpoet.image.grid import GridSpec
from optpoet.manifest.store import load_manifest
from optpoet.project.load import OpenMode, open_project
from optpoet.render.output import render_artwork, write_outputs
from optpoet.render.replay import load_layout, replay_outputs
from optpoet.render.style import RenderStyle
from optpoet.storage import ProjectLayout
from optpoet.text.layout import TextLayout, layout_text

SETTINGS = RenderSettings(pixel_size=16, cell_width=20, cell_height=20)
STYLE = RenderStyle(char_spacing=24, binarize=0.4)
GRID = GridSpec(columns=3, rows=2)


def build_layout() -> TextLayout:
    return layout_text("あいうえお", GRID)


def saved_project(
    font_file: Path,
    project_layout: ProjectLayout,
    manifest: dict[str, Any],
) -> tuple[bytes, bytes]:
    manifest["fonts"]["render_settings"] = SETTINGS.to_dict()
    artwork = render_artwork(build_layout(), load_font_profile(font_file), SETTINGS, STYLE)
    write_outputs(project_layout, artwork, manifest)
    return artwork.png, artwork.txt


def test_replay_reproduces_same_png_and_txt(
    font_file: Path,
    project_layout: ProjectLayout,
    materialized_manifest: dict[str, Any],
) -> None:
    png, txt = saved_project(font_file, project_layout, materialized_manifest)

    opened = open_project(project_layout)
    assert opened.mode is OpenMode.NORMAL
    result = replay_outputs(project_layout, opened.manifest.data, load_font_profile(font_file))

    assert result.matches
    assert result.artwork.png == png
    assert result.artwork.txt == txt


def test_replayed_layout_matches_saved_text(
    font_file: Path,
    project_layout: ProjectLayout,
    materialized_manifest: dict[str, Any],
) -> None:
    saved_project(font_file, project_layout, materialized_manifest)
    manifest = load_manifest(project_layout.manifest_path).data
    layout = load_layout(project_layout, manifest)
    assert layout.lines == build_layout().lines
    assert layout.grid.columns == GRID.columns
    assert layout.grid.rows == GRID.rows


def test_replay_without_outputs_is_reported(
    font_file: Path,
    project_layout: ProjectLayout,
    materialized_manifest: dict[str, Any],
) -> None:
    materialized_manifest["outputs"] = {}
    with pytest.raises(StageError) as info:
        replay_outputs(project_layout, materialized_manifest, load_font_profile(font_file))
    assert info.value.code == "replay_unavailable"


def test_engine_mismatch_stops_replay(
    font_file: Path,
    project_layout: ProjectLayout,
    materialized_manifest: dict[str, Any],
) -> None:
    """記録時と別の版で描き直して、違うバイト列を再生と称さない。"""
    saved_project(font_file, project_layout, materialized_manifest)
    manifest = dict(load_manifest(project_layout.manifest_path).data)
    outputs = dict(manifest["outputs"])
    outputs["render_metadata"] = {
        **outputs["render_metadata"],
        "engine_version": "0.0.0",
    }
    manifest["outputs"] = outputs

    with pytest.raises(StageError) as info:
        replay_outputs(project_layout, manifest, load_font_profile(font_file))
    assert info.value.code == "engine_mismatch"
