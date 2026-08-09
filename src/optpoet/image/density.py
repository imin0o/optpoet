"""密度マップを生成する（P1-014 / FR-03）。

密度は 0.00（白）〜1.00（黒）で、セル 1 つに 1 値を持つ（requirements.md 用語）。
基本は **平均明度** で、そこへ選択項目を混ぜる。

- **ガンマ**: 密度そのものへ指数を掛ける。1.0 で無変換、1.0 超で中間調が薄くなる。
- **局所コントラスト**: セル内の明度標準偏差。平坦な面より模様のある面を濃く出せる。
- **エッジ重み**: Sobel 強度のセル平均。輪郭を文字密度へ拾わせるための補助。

混合は凸結合にする。`(1 - contrast_weight - edge_weight) * 平均明度 + ...` とし、重みの
合計は 1 以下に制限する。各項が 0〜1 に収まるため、結果も 0〜1 から出ない。

エッジ結果は重みが 0 でも常に持つ。FR-03 が「元画像、密度マップ、エッジ補助結果を
比較でき、設定を再編集できる」ことを求めるため、比較材料を後から作り直させない。

作業配列は float32 で、領域画素数に比例する。上限（`ImageConfig.max_working_bytes`）を
超える見込みならセル化前に止める（P1-016）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray
from PIL import Image

from optpoet.config import ImageConfig
from optpoet.errors import StageError
from optpoet.image.grid import Fit, GridSpec, ReduceRegion, extract_region, plan_region
from optpoet.image.normalize import WHITE
from optpoet.image.preprocess import MAX_GAMMA, MIN_GAMMA
from optpoet.storage import Stage

# 局所コントラストの飽和点。白黒が半々のセルで明度標準偏差は 0.5（正規化明度）になる。
CONTRAST_FULL_SCALE = 0.5
# Sobel 強度の飽和点。3x3 カーネルの片側和 4 が縦横に立った場合の sqrt(2) * 4。
EDGE_FULL_SCALE = math.sqrt(2.0) * 4.0

# 作業配列 1 要素のバイト数（float32）と、同時に確保しうる本数の見積り。
# ピークはエッジ算出時で、明度・Sobel x / y・強度・正規化後の 5 本に加え、PIL 側の
# 画像 2 枚と一時配列を見込む。実測は 1 画素あたり約 24 バイト（P1-016 のテスト）。
BYTES_PER_SAMPLE = 4
WORKING_COPIES = 8

_STAGE = str(Stage.DENSITY_MAP)

Array = NDArray[np.float32]


@dataclass(frozen=True, slots=True)
class DensityMethod:
    """密度マップの算出設定（manifest の `density.method`）。"""

    gamma: float = 1.0
    contrast_weight: float = 0.0
    edge_weight: float = 0.0
    fit: Fit = Fit.COVER

    def validate(self) -> None:
        if not MIN_GAMMA <= self.gamma <= MAX_GAMMA:
            raise _invalid_method("gamma", self.gamma, f"{MIN_GAMMA}〜{MAX_GAMMA} の範囲にする。")
        for name, value in (
            ("contrast_weight", self.contrast_weight),
            ("edge_weight", self.edge_weight),
        ):
            if not 0.0 <= value <= 1.0:
                raise _invalid_method(name, value, "0.0〜1.0 の範囲にする。")
        total = self.contrast_weight + self.edge_weight
        if total > 1.0:
            raise _invalid_method("contrast_weight + edge_weight", total, "合計を 1.0 以下にする。")

    def to_dict(self) -> dict[str, Any]:
        return {
            "base": "mean_luminance",
            "gamma": self.gamma,
            "contrast_weight": self.contrast_weight,
            "edge_weight": self.edge_weight,
            "fit": str(self.fit),
        }


@dataclass(frozen=True, slots=True, eq=False)
class DensityMap:
    """セル単位の密度と、その来歴。

    `values` と `edges` は形状 (rows, columns) の float32。読み順は横書き（左→右、
    上→下）で、`sequence()` がそのまま密度列になる。
    """

    values: Array
    edges: Array
    grid: GridSpec
    region: ReduceRegion
    method: DensityMethod = field(default_factory=DensityMethod)

    @property
    def shape(self) -> tuple[int, int]:
        return (self.grid.rows, self.grid.columns)

    def sequence(self) -> Array:
        """密度マップを読み順へ並べた一次元配列（複製）。"""
        return self.values.reshape(-1).copy()

    def to_dict(self) -> dict[str, Any]:
        """manifest の `density` と突合できる形。実体の ref は保存側で足す。"""
        return {
            "method": self.method.to_dict(),
            "grid": self.grid.to_dict(),
            "region": self.region.to_dict(),
        }


def estimate_working_bytes(pixels: int) -> int:
    """密度マップ生成の作業メモリ見積り。memory-usage.md の線形則に合わせる。"""
    return pixels * BYTES_PER_SAMPLE * WORKING_COPIES


def build_density_map(
    image: Image.Image,
    grid: GridSpec,
    method: DensityMethod | None = None,
    *,
    limits: ImageConfig | None = None,
    background: tuple[int, int, int] = WHITE,
) -> DensityMap:
    """前処理後画像 `image` から `grid` の密度マップを作る。元の `image` は変更しない。"""
    method = method or DensityMethod()
    method.validate()
    grid.validate()
    limits = limits or ImageConfig()

    region = plan_region(image.size, grid, method.fit)
    _check_working_memory(region, limits)

    luminance = _luminance(extract_region(image, region, background=background))
    mean = _to_cells(luminance, grid)
    edges = _to_cells(_edge_strength(luminance), grid)

    base = np.power(1.0 - mean, method.gamma, dtype=np.float32)
    contrast = _local_contrast(luminance, mean, grid)
    values = _blend(base, contrast, edges, method)
    return DensityMap(values=values, edges=edges, grid=grid, region=region, method=method)


def _luminance(sample: Image.Image) -> Array:
    """0.0〜1.0 の明度配列にする。以降の計算はすべてこの配列を元にする。"""
    array = np.asarray(sample.convert("L"), dtype=np.float32)
    return np.divide(array, 255.0, dtype=np.float32)


def _to_cells(array: Array, grid: GridSpec) -> Array:
    """セル数へ落とす。縮小は面積平均、拡大（領域がセル数より小さい場合）は線形補間。"""
    height, width = array.shape
    shrinking = width >= grid.columns and height >= grid.rows
    interpolation = cv2.INTER_AREA if shrinking else cv2.INTER_LINEAR
    reduced = cv2.resize(array, (grid.columns, grid.rows), interpolation=interpolation)
    return np.asarray(reduced, dtype=np.float32)


def _local_contrast(luminance: Array, mean: Array, grid: GridSpec) -> Array:
    """セル内の明度標準偏差を 0〜1 へ正規化する。E[x^2] - E[x]^2 から求める。"""
    squared_mean = _to_cells(np.square(luminance, dtype=np.float32), grid)
    variance = np.clip(squared_mean - np.square(mean, dtype=np.float32), 0.0, None)
    deviation = np.sqrt(variance, dtype=np.float32)
    return np.clip(deviation / CONTRAST_FULL_SCALE, 0.0, 1.0).astype(np.float32)


def _edge_strength(luminance: Array) -> Array:
    """Sobel 強度を 0〜1 へ正規化した全画素配列。"""
    gx = cv2.Sobel(luminance, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(luminance, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = cv2.magnitude(gx, gy)
    return _as_array(np.clip(magnitude / EDGE_FULL_SCALE, 0.0, 1.0))


def _blend(base: Array, contrast: Array, edges: Array, method: DensityMethod) -> Array:
    """凸結合で混ぜる。重みが 0 の項は結果に影響しない。"""
    base_weight = 1.0 - method.contrast_weight - method.edge_weight
    mixed = base * base_weight + contrast * method.contrast_weight + edges * method.edge_weight
    # 浮動小数の誤差で境界をわずかに外れることがあるため最後に丸め込む。
    return _as_array(np.clip(mixed, 0.0, 1.0))


def _as_array(values: Any) -> Array:
    """float32 の配列として扱う。cv2 由来の値も含めてここで型を揃える。"""
    return np.asarray(values, dtype=np.float32)


def _check_working_memory(region: ReduceRegion, limits: ImageConfig) -> None:
    estimate = estimate_working_bytes(region.pixels)
    if estimate <= limits.max_working_bytes:
        return
    scale = math.sqrt(limits.max_working_bytes / estimate)
    raise StageError(
        _STAGE,
        "memory_limit",
        (
            f"密度マップの作業メモリ見積りが上限を超えた: "
            f"{_mib(estimate)} MB > {_mib(limits.max_working_bytes)} MB "
            f"({region.width}x{region.height})"
        ),
        hint=(
            f"長辺を約 {max(1, int(scale * 100))}% へ縮小するか、"
            "image.max_working_bytes を引き上げる。"
        ),
    )


def _invalid_method(name: str, value: float, hint: str) -> StageError:
    return StageError(
        _STAGE,
        "invalid_method",
        f"density.{name} の値が不正: {value!r}",
        hint=hint,
    )


def _mib(value: int) -> str:
    return f"{value / (1024 * 1024):.1f}"
