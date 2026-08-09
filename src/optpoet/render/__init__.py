"""描画・比較・出力（P1-E）。

工程の並びは 描画（P1-040 / P1-041）→ セル列の検証（P1-043）→ 書き出し（P1-042）で、
比較表示（P1-044）と評価指標（P1-045）が結果の確認を、再生（P1-046）が保存後の再現を担う。
"""

from optpoet.render.compare import (
    ComparisonSet,
    build_comparison,
    density_waveform,
    difference_image,
    error_heatmap,
)
from optpoet.render.grid import cell_origin, coverage_of, output_size, paint, render_grid
from optpoet.render.metrics import (
    METRICS_SPEC_VERSION,
    Metrics,
    cell_density,
    density_mae,
    edge_dice,
    evaluate_outputs,
    ssim_score,
)
from optpoet.render.output import (
    Artwork,
    CellCheck,
    OutputResult,
    encode_png,
    encode_txt,
    grid_block,
    render_artwork,
    render_metadata,
    style_block,
    verify_cells,
    write_outputs,
)
from optpoet.render.replay import ReplayResult, load_layout, replay_outputs
from optpoet.render.style import INK, PAPER, RenderStyle

__all__ = [
    "INK",
    "METRICS_SPEC_VERSION",
    "PAPER",
    "Artwork",
    "CellCheck",
    "ComparisonSet",
    "Metrics",
    "OutputResult",
    "RenderStyle",
    "ReplayResult",
    "build_comparison",
    "cell_density",
    "cell_origin",
    "coverage_of",
    "density_mae",
    "density_waveform",
    "difference_image",
    "edge_dice",
    "encode_png",
    "encode_txt",
    "error_heatmap",
    "evaluate_outputs",
    "grid_block",
    "load_layout",
    "output_size",
    "paint",
    "render_artwork",
    "render_grid",
    "render_metadata",
    "replay_outputs",
    "ssim_score",
    "style_block",
    "verify_cells",
    "write_outputs",
]
