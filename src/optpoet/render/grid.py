"""密度辞書と同じ描画エンジンでグリッドを描く（P1-040 / P1-041 / FR-12 / NFR-02）。

最終 PNG も 1 セルずつ `render_cell()` で描き、そのセル画像を升目へ貼るだけにする。
まとめ描き（1 行を 1 回の `draw.text` で描く等）は字送りが FreeType 側の都合で動くため
使わない。辞書の黒画素率と最終画素が一致することが NFR-02 の前提になる。

塗りは被覆率（`RenderStyle` の説明）を経由する。既定（黒文字・白地・二値化なし・反転
なし）では被覆率から戻した画素値が `render_cell()` の出力と一致し、セル領域を切り出すと
辞書測定用のセルとバイト一致する。

欠落グリフは描画前に止める（AC-02）。豆腐を黙って描くと、密度も見た目も記録と食い違う。
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from optpoet.font.profile import FontProfile
from optpoet.font.render import Cell, RenderSettings, load_font, render_cell
from optpoet.image.grid import GridSpec
from optpoet.pipeline.progress import StageProgress
from optpoet.render.style import RenderStyle
from optpoet.text.layout import TextLayout

Coverage = NDArray[np.float32]


def output_size(grid: GridSpec, settings: RenderSettings, style: RenderStyle) -> tuple[int, int]:
    """出力画像の画素寸法。manifest の `grid.output_size` に入れる値。"""
    return (style.char_pitch(settings) * grid.columns, style.line_pitch(settings) * grid.rows)


def cell_origin(
    row: int,
    column: int,
    settings: RenderSettings,
    style: RenderStyle,
) -> tuple[int, int]:
    """セル画像を貼る左上座標。升目が広い場合はセルを中央へ置く。"""
    pitch_x = style.char_pitch(settings)
    pitch_y = style.line_pitch(settings)
    return (
        column * pitch_x + (pitch_x - settings.cell_width) // 2,
        row * pitch_y + (pitch_y - settings.cell_height) // 2,
    )


def render_grid(
    layout: TextLayout,
    profile: FontProfile,
    settings: RenderSettings | None = None,
    style: RenderStyle | None = None,
    *,
    progress: StageProgress | None = None,
) -> Image.Image:
    """配置済みテキストを 1 枚の画像へ描く。同じ入力なら常に同じ画素になる。"""
    settings = settings or RenderSettings()
    style = style or RenderStyle()
    settings.validate()
    style.validate(settings)
    layout.grid.validate()

    chars = tuple(dict.fromkeys(layout.cells))
    profile.require(chars)

    font = load_font(profile, settings)
    cache = {char: coverage_of(render_cell(char, font, settings), settings) for char in chars}

    width, height = output_size(layout.grid, settings, style)
    canvas = np.zeros((height, width), dtype=np.float32)
    for index, char in enumerate(layout.cells):
        row, column = layout.position(index)
        x, y = cell_origin(row, column, settings, style)
        canvas[y : y + settings.cell_height, x : x + settings.cell_width] = cache[char]
        if progress is not None:
            progress.advance()
    return paint(canvas, style)


def coverage_of(cell: Cell, settings: RenderSettings) -> Coverage:
    """セル画像を被覆率（0.0=紙, 1.0=墨）へ写す。`black_ratio` と同じ尺度。"""
    span = float(settings.background - settings.foreground)
    values = cell.astype(np.float32)
    return np.asarray((settings.background - values) / span, dtype=np.float32)


def paint(coverage: Coverage, style: RenderStyle) -> Image.Image:
    """被覆率を二値化・反転してから色を載せる（P1-041）。"""
    values = coverage
    if style.binarize is not None:
        values = (values >= style.binarize).astype(np.float32)
    if style.invert:
        values = np.asarray(1.0 - values, dtype=np.float32)

    foreground = np.asarray(style.foreground, dtype=np.float32)
    background = np.asarray(style.background, dtype=np.float32)
    mixed = background + values[..., None] * (foreground - background)
    pixels = np.rint(mixed).astype(np.uint8)
    if style.mode == "L":
        return Image.fromarray(pixels[..., 0], mode="L")
    return Image.fromarray(pixels, mode="RGB")
