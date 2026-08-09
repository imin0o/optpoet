"""PNG / UTF-8 TXT / project JSON の書き出しとセル列の検証（P1-042 / P1-043 / FR-12）。

出力は 3 つで 1 組にする。PNG は見た目、TXT は文字そのもの、project JSON（manifest）は
両者の来歴。3 つが食い違うと再生（P1-046）が成り立たないため、書き出す前に **TXT の
セル列と PNG の描画列が一致すること** を検証する（P1-043）。検証結果は manifest の
`evaluation.cell_check` に残す。

TXT は UTF-8（BOM なし）、行区切りは LF、末尾に LF を 1 つ置く。改行はセルに数えない
（FR-10）ので、1 行の文字数はそのままグリッドの列数になる。

書き込み順は「実体 → manifest」。manifest の置換 1 点がコミット点なので（A-08）、
実体だけが残った場合でも直前の有効版は壊れない。
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

from optpoet.errors import StageError
from optpoet.font.profile import FontProfile
from optpoet.font.render import RenderSettings
from optpoet.hashing import hash_bytes
from optpoet.pipeline.progress import StageProgress
from optpoet.project.save import SaveResult, save_project
from optpoet.render.grid import output_size, render_grid
from optpoet.render.style import RenderStyle
from optpoet.storage import ArtifactCache, Stage
from optpoet.storage.atomic import atomic_write
from optpoet.storage.layout import ProjectLayout
from optpoet.text.layout import TextLayout
from optpoet.text.normalize import NEWLINE, NORMALIZATION_FORM

PNG_MEDIA_TYPE = "image/png"
TXT_MEDIA_TYPE = "text/plain"
TXT_ENCODING = "utf-8"
READING_ORDER = "horizontal_ltr_ttb"

_STAGE = str(Stage.RENDER)


@dataclass(frozen=True, slots=True)
class CellCheck:
    """TXT と PNG のセル列が一致したかどうか（manifest の `evaluation.cell_check`）。"""

    expected_cells: int
    displayed_chars: int
    result: str = "ok"

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_cells": self.expected_cells,
            "displayed_chars": self.displayed_chars,
            "result": self.result,
        }


@dataclass(frozen=True, slots=True, eq=False)
class Artwork:
    """描画済みの 1 組。`png` / `txt` は書き出すバイト列そのもの。"""

    layout: TextLayout
    image: Image.Image
    settings: RenderSettings
    style: RenderStyle
    png: bytes
    txt: bytes
    cell_check: CellCheck


@dataclass(frozen=True, slots=True)
class OutputResult:
    """書き出し結果。ref はそのまま manifest の `outputs` に入っている値。"""

    png_ref: dict[str, Any]
    txt_ref: dict[str, Any]
    save: SaveResult


def encode_txt(layout: TextLayout) -> bytes:
    """配置を UTF-8 TXT へ直列化する。1 行 = グリッド 1 行。"""
    return (layout.text + NEWLINE).encode(TXT_ENCODING)


def encode_png(image: Image.Image) -> bytes:
    """PNG へ符号化する。時刻等のメタデータを載せず、同じ画素なら同じバイト列にする。"""
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def verify_cells(
    layout: TextLayout,
    image: Image.Image,
    settings: RenderSettings,
    style: RenderStyle,
    *,
    txt: bytes,
) -> CellCheck:
    """TXT のセル列と PNG の描画列が一致することを検証する（P1-043）。

    TXT は書き出すバイト列から読み直して数える。配置オブジェクトを信用して数えると、
    直列化で崩れた場合を素通しする。
    """
    grid = layout.grid
    lines = txt.decode(TXT_ENCODING).split(NEWLINE)
    if lines and lines[-1] == "":
        lines.pop()
    if len(lines) != grid.rows:
        raise _cell_mismatch(f"TXT の行数がグリッドと違う: {len(lines)} != {grid.rows}")
    for row, line in enumerate(lines):
        if len(line) != grid.columns:
            raise _cell_mismatch(
                f"TXT {row + 1} 行目の文字数が列数と違う: {len(line)} != {grid.columns}"
            )
    expected = output_size(grid, settings, style)
    if image.size != expected:
        raise _cell_mismatch(f"PNG の画素寸法が描画列と違う: {image.size} != {expected}")
    return CellCheck(expected_cells=grid.cells, displayed_chars=sum(len(line) for line in lines))


def render_artwork(
    layout: TextLayout,
    profile: FontProfile,
    settings: RenderSettings | None = None,
    style: RenderStyle | None = None,
    *,
    progress: StageProgress | None = None,
) -> Artwork:
    """描画し、符号化し、セル列を検証するまでを 1 組で行う。"""
    settings = settings or RenderSettings()
    style = style or RenderStyle()
    image = render_grid(layout, profile, settings, style, progress=progress)
    txt = encode_txt(layout)
    png = encode_png(image)
    check = verify_cells(layout, image, settings, style, txt=txt)
    return Artwork(
        layout=layout,
        image=image,
        settings=settings,
        style=style,
        png=png,
        txt=txt,
        cell_check=check,
    )


def render_metadata(settings: RenderSettings) -> dict[str, Any]:
    """manifest の `outputs.render_metadata`。辞書側の `render_settings` と一致させる（I-03）。"""
    return settings.to_dict()


def style_block(settings: RenderSettings, style: RenderStyle) -> dict[str, Any]:
    """manifest の `outputs.style`。見た目は 1 セルの画素を変えないため I-03 の外に置く。"""
    return style.to_dict(settings)


def grid_block(layout: TextLayout, settings: RenderSettings, style: RenderStyle) -> dict[str, Any]:
    """manifest の `grid`。寸法・送り・読み順・正規化形式を出力と揃える。"""
    width, height = output_size(layout.grid, settings, style)
    return {
        **layout.grid.to_dict(),
        "output_size": {"width": width, "height": height},
        "font_size": settings.pixel_size,
        "line_spacing": style.line_pitch(settings),
        "char_spacing": style.char_pitch(settings),
        "reading_order": READING_ORDER,
        "normalization_form": NORMALIZATION_FORM,
    }


def write_outputs(
    project: ProjectLayout,
    artwork: Artwork,
    manifest_data: dict[str, Any],
    *,
    updated_at: str | None = None,
) -> OutputResult:
    """PNG / TXT を配置し、`outputs` を更新した manifest を原子的に保存する（P1-042）。"""
    data = dict(manifest_data)
    _require_shared_settings(data, artwork.settings)

    png_ref = _write(project, project.output_png_path, artwork.png, PNG_MEDIA_TYPE)
    txt_ref = _write(project, project.output_txt_path, artwork.txt, TXT_MEDIA_TYPE)

    data["grid"] = {
        **data.get("grid", {}),
        **grid_block(artwork.layout, artwork.settings, artwork.style),
    }
    data["text"] = {**data.get("text", {}), "final_ref": _final_text_ref(project, artwork.txt)}
    data["outputs"] = {
        "png_ref": png_ref,
        "txt_ref": txt_ref,
        "render_metadata": render_metadata(artwork.settings),
        "style": style_block(artwork.settings, artwork.style),
    }
    data["evaluation"] = {
        **data.get("evaluation", {}),
        "cell_check": artwork.cell_check.to_dict(),
    }
    save = save_project(project, data, updated_at=updated_at)
    return OutputResult(png_ref=png_ref, txt_ref=txt_ref, save=save)


def _require_shared_settings(data: dict[str, Any], settings: RenderSettings) -> None:
    """辞書と同じ描画設定で描いたことを、保存前に確かめる（I-03 / NFR-02）。"""
    recorded = data.get("fonts", {}).get("render_settings")
    if recorded is not None and recorded != settings.to_dict():
        raise StageError(
            _STAGE,
            "settings_mismatch",
            "fonts.render_settings と描画に使った設定が違う",
            hint="密度辞書と同じ RenderSettings で描き直すか、辞書を作り直す。",
        )


def _final_text_ref(project: ProjectLayout, txt: bytes) -> dict[str, Any]:
    """最終文章を内容アドレスで置き、`text.final_ref` にする。

    manifest は `text.final_ref` と `outputs.txt_ref` の内容一致を要求するため、TXT と
    同じバイト列をそのまま最終文章の実体にする。
    """
    entry = ArtifactCache(project).store(Stage.TEXT, hash_bytes(txt), "txt", txt)
    return {
        "path": entry.relative_path,
        "hash": entry.hash,
        "media_type": TXT_MEDIA_TYPE,
        "bytes": len(txt),
    }


def _write(
    project: ProjectLayout,
    path: Path,
    data: bytes,
    media_type: str,
) -> dict[str, Any]:
    atomic_write(path, data, tmp_dir=project.tmp_dir)
    return {
        "path": project.relative(path),
        "hash": hash_bytes(data),
        "media_type": media_type,
        "bytes": len(data),
    }


def _cell_mismatch(message: str) -> StageError:
    return StageError(
        _STAGE,
        "cell_mismatch",
        message,
        hint="同じ配置と描画設定で描き直す。TXT と PNG は同じ工程で作る。",
    )
