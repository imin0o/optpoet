"""テキストの正規化・配置・密度最適化（P1-D）。

工程の並びは 正規化（P1-030）→ セル数突合（P1-032）→ 配置（P1-031）→ 誤差評価（P1-033）
→ 局所探索（P1-035 / P1-036）で、基準配置（P1-034）とトレース（P1-037）が比較と説明を担う。
"""

from optpoet.text.baseline import build_baseline
from optpoet.text.evaluate import (
    CellError,
    DensityError,
    density_table,
    evaluate_layout,
    normalized_density,
)
from optpoet.text.fit import Adjustment, FitReport, check_fit, require_fit
from optpoet.text.layout import (
    FULL_SPACE,
    HALF_SPACE,
    NO_LINE_END,
    NO_LINE_START,
    LineBreak,
    TextLayout,
    count_cells,
    layout_text,
)
from optpoet.text.normalize import (
    NEWLINE,
    NORMALIZATION_FORM,
    NormalizedText,
    UnsupportedChar,
    inspect_text,
    normalize_text,
    require_supported,
)
from optpoet.text.optimize import (
    ALGORITHM_NAME,
    ALGORITHM_VERSION,
    STOPPED_CONVERGED,
    STOPPED_MAX_ITERATIONS,
    OptimizeResult,
    OptimizeSettings,
    optimize_layout,
)
from optpoet.text.trace import (
    TRACE_SCHEMA_VERSION,
    TRACE_STAGE_VERSION,
    OptimizationTrace,
    TraceEntry,
)
from optpoet.text.variants import VARIANTS_VERSION, VariantTable, default_variants

__all__ = [
    "ALGORITHM_NAME",
    "ALGORITHM_VERSION",
    "FULL_SPACE",
    "HALF_SPACE",
    "NEWLINE",
    "NORMALIZATION_FORM",
    "NO_LINE_END",
    "NO_LINE_START",
    "STOPPED_CONVERGED",
    "STOPPED_MAX_ITERATIONS",
    "TRACE_SCHEMA_VERSION",
    "TRACE_STAGE_VERSION",
    "VARIANTS_VERSION",
    "Adjustment",
    "CellError",
    "DensityError",
    "FitReport",
    "LineBreak",
    "NormalizedText",
    "OptimizationTrace",
    "OptimizeResult",
    "OptimizeSettings",
    "TextLayout",
    "TraceEntry",
    "UnsupportedChar",
    "VariantTable",
    "build_baseline",
    "check_fit",
    "count_cells",
    "default_variants",
    "density_table",
    "evaluate_layout",
    "inspect_text",
    "layout_text",
    "normalize_text",
    "normalized_density",
    "optimize_layout",
    "require_fit",
    "require_supported",
]
