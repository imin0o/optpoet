"""保存・再読込後の再生（P1-046 / FR-17）。

再生は「保存した manifest と TXT だけから、同じ PNG と同じ TXT をもう一度作れるか」を
確かめる工程。作り直すのに要るのは、グリッド寸法（`grid`）、描画設定（
`outputs.render_metadata`）、見た目（`outputs.style`）、そして本文（`outputs/artwork.txt`）
で、いずれも保存済み。

再生した結果は内容ハッシュで突き合わせる。バイト一致しない場合でも黙って上書きせず、
記録側と再生側の両方のハッシュを返して呼び出し側に判断させる。フォント実体が差し替わった
場合や描画エンジンの版が変わった場合はここで露見する（`settings_from_dict` が版を照合する）。

`text.content_cells`（本文が占めたセル数）は manifest に持たないため、再生した配置では
全セルを本文とみなす。TXT の文字列そのものは元と一致するので、再生の判定には影響しない。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from optpoet.errors import StageError
from optpoet.font.profile import FontProfile
from optpoet.font.render import settings_from_dict
from optpoet.hashing import hash_bytes, parse_hash
from optpoet.image.grid import GridSpec
from optpoet.pipeline.progress import StageProgress
from optpoet.render.output import TXT_ENCODING, Artwork, render_artwork
from optpoet.render.style import RenderStyle
from optpoet.storage import Stage
from optpoet.storage.layout import ProjectLayout
from optpoet.text.layout import TextLayout
from optpoet.text.normalize import NEWLINE

_STAGE = str(Stage.RENDER)


@dataclass(frozen=True, slots=True, eq=False)
class ReplayResult:
    """再生した成果物と、記録済みハッシュとの突合結果。"""

    artwork: Artwork
    png_hash: str
    txt_hash: str
    recorded_png_hash: str
    recorded_txt_hash: str

    @property
    def png_matches(self) -> bool:
        return self.png_hash == self.recorded_png_hash

    @property
    def txt_matches(self) -> bool:
        return self.txt_hash == self.recorded_txt_hash

    @property
    def matches(self) -> bool:
        return self.png_matches and self.txt_matches


def load_layout(project: ProjectLayout, manifest: Mapping[str, Any]) -> TextLayout:
    """保存済み TXT を読み、manifest のグリッドへ戻す。"""
    grid = grid_of(manifest)
    try:
        text = project.output_txt_path.read_text(encoding=TXT_ENCODING)
    except OSError as exc:
        raise _replay_error(f"TXT を読めない: {project.output_txt_path}") from exc
    lines = text.split(NEWLINE)
    if lines and lines[-1] == "":
        lines.pop()
    return TextLayout(lines=tuple(lines), grid=grid, content_cells=grid.cells)


def grid_of(manifest: Mapping[str, Any]) -> GridSpec:
    """manifest の `grid` から寸法を戻す。"""
    block = _require(manifest, "grid")
    try:
        return GridSpec(
            columns=int(block["cols"]),
            rows=int(block["rows"]),
            cell_aspect=float(block["cell_aspect"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise _replay_error(f"grid の寸法を読めない: {exc}") from exc


def replay_outputs(
    project: ProjectLayout,
    manifest: Mapping[str, Any],
    profile: FontProfile,
    *,
    progress: StageProgress | None = None,
) -> ReplayResult:
    """保存済みの設定で PNG / TXT を作り直し、記録した内容ハッシュと突き合わせる。"""
    outputs = _require(manifest, "outputs")
    metadata = outputs.get("render_metadata")
    if not isinstance(metadata, dict):
        raise _replay_error("outputs.render_metadata がないため再生できない")
    style_data = outputs.get("style")
    if not isinstance(style_data, dict):
        raise _replay_error("outputs.style がないため再生できない")

    artwork = render_artwork(
        load_layout(project, manifest),
        profile,
        settings_from_dict(metadata),
        RenderStyle.from_dict(style_data),
        progress=progress,
    )
    return ReplayResult(
        artwork=artwork,
        png_hash=hash_bytes(artwork.png),
        txt_hash=hash_bytes(artwork.txt),
        recorded_png_hash=_ref_hash(outputs, "png_ref"),
        recorded_txt_hash=_ref_hash(outputs, "txt_ref"),
    )


def _require(manifest: Mapping[str, Any], key: str) -> dict[str, Any]:
    block = manifest.get(key)
    if not isinstance(block, dict):
        raise _replay_error(f"manifest に {key} がない")
    return block


def _ref_hash(outputs: Mapping[str, Any], name: str) -> str:
    ref = outputs.get(name)
    if not isinstance(ref, dict) or "hash" not in ref:
        raise _replay_error(f"outputs.{name} に記録済みの内容ハッシュがない")
    return parse_hash(ref["hash"])


def _replay_error(message: str) -> StageError:
    return StageError(
        _STAGE,
        "replay_unavailable",
        message,
        hint="保存済みの manifest と outputs/ の実体が揃っているか確認する。",
    )
