"""自動評価指標（P1-045 / AC-03）。

計算仕様は docs/environment/evaluation-metrics.md に従い、値が環境で動かないよう
パラメータをすべて固定する。

- 共通前処理: 輝度 `Y = 0.2126R + 0.7152G + 0.0722B`、密度 `d = 1 - Y`、透過は白で合成。
  縮小は面積平均（`INTER_AREA`）、拡大は Lanczos（`INTER_LANCZOS4`）。
- 密度 MAE（3 章）: セルグリッド上で測る。離散化前の連続密度を使い、量子化誤差を
  評価へ持ち込まない。
- SSIM（4 章）: 生成結果 PNG の画素寸法を比較解像度とし、目標画像をそこへ揃える。
- エッジ一致率（5 章）: ガウシアンぼかし → Canny → Dice 係数。

SSIM とエッジ一致率は MVP では補助指標で、固定閾値の合否には使わない。AC-03 の判定は
密度 MAE の改善率（草稿配置と最適化後の比較）で行う。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray
from PIL import Image
from skimage.metrics import structural_similarity

from optpoet.errors import StageError
from optpoet.image.grid import GridSpec
from optpoet.storage import Stage

METRICS_SPEC_VERSION = "1.0"

LUMA_COEFFICIENTS = (0.2126, 0.7152, 0.0722)
"""Rec.709 の輝度係数（validation-dataset.md 6 章と同係数）。"""

SSIM_SIGMA = 1.5
SSIM_WINDOW = 7
BLUR_KERNEL = (5, 5)
BLUR_SIGMA = 1.0
CANNY_LOW = 100
CANNY_HIGH = 200

_STAGE = str(Stage.RENDER)

Array = NDArray[np.float32]
Mask = NDArray[np.bool_]


@dataclass(frozen=True, slots=True)
class Metrics:
    """1 作品分の評価値（manifest の `evaluation.metrics`）。"""

    mae_opt: float
    ssim: float
    edge_dice: float
    mae_draft: float | None = None
    improvement_rate: float | None = None
    region_mae: float | None = None
    spec_version: str = METRICS_SPEC_VERSION

    def to_dict(self) -> dict[str, Any]:
        """値のない指標は「該当なし」であり、0 として記録しない。"""
        payload: dict[str, Any] = {"spec_version": self.spec_version, "mae_opt": self.mae_opt}
        for name in ("mae_draft", "improvement_rate", "region_mae"):
            value = getattr(self, name)
            if value is not None:
                payload[name] = value
        payload["ssim"] = self.ssim
        payload["edge_dice"] = self.edge_dice
        return payload


def luminance(image: Image.Image) -> Array:
    """0.0〜1.0 の輝度配列。透過があれば白で合成してから輝度化する。"""
    source = image
    if source.mode in {"RGBA", "LA", "PA"} or "transparency" in source.info:
        base = Image.new("RGBA", source.size, (255, 255, 255, 255))
        source = Image.alpha_composite(base, source.convert("RGBA"))
    rgb = np.asarray(source.convert("RGB"), dtype=np.float32) / np.float32(255.0)
    coefficients = np.asarray(LUMA_COEFFICIENTS, dtype=np.float32)
    return np.asarray(rgb @ coefficients, dtype=np.float32)


def density(image: Image.Image) -> Array:
    """密度 `d = 1 - Y`。白が 0、黒が 1（密度マップと同じ向き）。"""
    return np.asarray(1.0 - luminance(image), dtype=np.float32)


def resize(array: Array, size: tuple[int, int]) -> Array:
    """共通解像度へ揃える。縮小と拡大で補間を混ぜない。"""
    width, height = size
    if (array.shape[1], array.shape[0]) == size:
        return array
    shrinking = array.shape[1] >= width and array.shape[0] >= height
    interpolation = cv2.INTER_AREA if shrinking else cv2.INTER_LANCZOS4
    return np.asarray(cv2.resize(array, size, interpolation=interpolation), dtype=np.float32)


def cell_density(image: Image.Image, grid: GridSpec) -> Array:
    """画像をセル矩形へ面積平均で縮約した密度（形状 (rows, columns)）。"""
    grid.validate()
    return resize(density(image), (grid.columns, grid.rows))


def density_mae(target: Image.Image, rendered: Image.Image, grid: GridSpec) -> float:
    """セル単位の密度 MAE（3 章）。"""
    difference = cell_density(target, grid) - cell_density(rendered, grid)
    return float(np.abs(difference).mean())


def ssim_score(target: Image.Image, rendered: Image.Image) -> float:
    """SSIM（4 章）。比較解像度は生成結果 PNG に合わせる。"""
    actual = luminance(rendered)
    expected = resize(luminance(target), (actual.shape[1], actual.shape[0]))
    if min(actual.shape) < SSIM_WINDOW:
        raise StageError(
            _STAGE,
            "image_too_small",
            f"SSIM の窓 {SSIM_WINDOW}px が画像に収まらない: {actual.shape[1]}x{actual.shape[0]}",
            hint="セル寸法か字間・行間を大きくして出力画像を広げる。",
        )
    # scikit-image は型注釈を持たないため、戻り値をここで float へ確定させる。
    value = structural_similarity(  # type: ignore[no-untyped-call]
        expected,
        actual,
        data_range=1.0,
        gaussian_weights=True,
        sigma=SSIM_SIGMA,
        use_sample_covariance=False,
    )
    return float(value)


def edge_dice(target: Image.Image, rendered: Image.Image) -> float:
    """エッジ一致率（5 章）。双方にエッジが無い場合は 1.0 と定義する。"""
    actual = luminance(rendered)
    expected = resize(luminance(target), (actual.shape[1], actual.shape[0]))
    edges_actual = _edges(actual)
    edges_expected = _edges(expected)
    total = int(edges_actual.sum()) + int(edges_expected.sum())
    if total == 0:
        return 1.0
    overlap = int(np.logical_and(edges_actual, edges_expected).sum())
    return 2.0 * overlap / total


def evaluate_outputs(
    target: Image.Image,
    rendered: Image.Image,
    grid: GridSpec,
    *,
    draft: Image.Image | None = None,
    region: Mask | None = None,
) -> Metrics:
    """最適化後の成果物を評価する。`draft` を渡すと AC-03 の改善率も求める。"""
    mae_opt = density_mae(target, rendered, grid)
    mae_draft = None if draft is None else density_mae(target, draft, grid)
    return Metrics(
        mae_opt=mae_opt,
        ssim=ssim_score(target, rendered),
        edge_dice=edge_dice(target, rendered),
        mae_draft=mae_draft,
        improvement_rate=_improvement(mae_draft, mae_opt),
        region_mae=_region_mae(target, rendered, grid, region),
    )


def _edges(values: Array) -> Mask:
    levels = np.rint(np.clip(values, 0.0, 1.0) * 255.0).astype(np.uint8)
    blurred = cv2.GaussianBlur(levels, BLUR_KERNEL, BLUR_SIGMA)
    edges = cv2.Canny(blurred, CANNY_LOW, CANNY_HIGH, apertureSize=3, L2gradient=True)
    return np.asarray(edges > 0, dtype=np.bool_)


def _improvement(mae_draft: float | None, mae_opt: float) -> float | None:
    """改善率。`MAE_draft = 0` の作品は改善率を定義せず母集団から除く（3 章）。"""
    if mae_draft is None or mae_draft <= 0.0:
        return None
    return (mae_draft - mae_opt) / mae_draft


def _region_mae(
    target: Image.Image,
    rendered: Image.Image,
    grid: GridSpec,
    region: Mask | None,
) -> float | None:
    """重要領域 MAE（6 章）。指定が無ければ算出しない。"""
    if region is None:
        return None
    if region.shape != (grid.rows, grid.columns):
        raise StageError(
            _STAGE,
            "region_mismatch",
            f"重要領域の形状がグリッドと違う: {region.shape} != {(grid.rows, grid.columns)}",
            hint="領域マスクを (rows, columns) で作り直す。",
        )
    if not region.any():
        return None
    difference = cell_density(target, grid) - cell_density(rendered, grid)
    return float(np.abs(difference[region]).mean())
