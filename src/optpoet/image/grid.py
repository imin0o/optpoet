"""グリッド寸法と実測セル比から縮小領域を決める（P1-013 / FR-02）。

密度マップは「画像をセル単位へ縮小した配列」なので、縮小前に **どの矩形を** セル数へ
落とすかを決める必要がある。文字セルは正方とは限らず（実測字面と行送りから決まる
`cell_aspect`）、グリッド全体の画素比は `columns * cell_aspect : rows` になる。この比と
画像の比が食い違うと、そのまま縮小すれば絵が伸びる。

そこで縮小領域を先に確定する。

- `COVER`: グリッド比に合う最大の矩形を中央から切り出す（はみ出しは捨てる）。
- `CONTAIN`: 画像全体が入る矩形へ広げる（不足分は背景色で埋める）。
- `STRETCH`: 画像全体をそのまま使う（比は保たれず伸びる）。

領域は前処理後画像の座標系で持つ。`CONTAIN` では画像の外へ出るため、`x` / `y` が負に
なり `width` / `height` が原寸を超えることがある。実際の切り出しは `extract_region`
が背景色の台紙へ貼って行う。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from PIL import Image

from optpoet.config import GridConfig
from optpoet.errors import StageError
from optpoet.image.normalize import WHITE
from optpoet.storage import Stage

_STAGE = str(Stage.DENSITY_MAP)


class Fit(StrEnum):
    """グリッド比と画像比が食い違うときの合わせ方。"""

    COVER = "cover"
    CONTAIN = "contain"
    STRETCH = "stretch"


@dataclass(frozen=True, slots=True)
class GridSpec:
    """文字グリッドの寸法と実測セル比。

    `cell_aspect` はセル幅 / セル高。1.0 で正方、1.0 未満で縦長（日本語の等幅組では
    行送りが字幅より大きいことが多い）。
    """

    columns: int
    rows: int
    cell_aspect: float = 1.0

    @property
    def cells(self) -> int:
        return self.columns * self.rows

    @property
    def aspect(self) -> float:
        """グリッド全体の画素比（幅 / 高）。セル高を 1 とみなして求める。"""
        return (self.columns * self.cell_aspect) / self.rows

    @classmethod
    def from_config(cls, grid: GridConfig, cell_aspect: float = 1.0) -> GridSpec:
        return cls(columns=grid.columns, rows=grid.rows, cell_aspect=cell_aspect)

    @classmethod
    def from_cell_size(
        cls,
        columns: int,
        rows: int,
        cell_width: float,
        cell_height: float,
    ) -> GridSpec:
        """実測したセル画素サイズから比を求める。"""
        if cell_width <= 0 or cell_height <= 0:
            raise _invalid_grid(f"セル寸法が不正: {cell_width}x{cell_height}")
        return cls(columns=columns, rows=rows, cell_aspect=cell_width / cell_height)

    def validate(self) -> None:
        if self.columns <= 0 or self.rows <= 0:
            raise _invalid_grid(f"セル数は 1 以上: {self.columns}x{self.rows}")
        if not math.isfinite(self.cell_aspect) or self.cell_aspect <= 0:
            raise _invalid_grid(f"cell_aspect は正の有限値: {self.cell_aspect!r}")

    def to_dict(self) -> dict[str, float | int]:
        """manifest の `grid` へ入れる寸法部分。"""
        return {"cols": self.columns, "rows": self.rows, "cell_aspect": self.cell_aspect}


@dataclass(frozen=True, slots=True)
class ReduceRegion:
    """縮小元の矩形と、落とし込む先のセル数。"""

    x: int
    y: int
    width: int
    height: int
    columns: int
    rows: int
    fit: Fit

    @property
    def box(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    @property
    def pixels(self) -> int:
        return self.width * self.height

    def padded_against(self, size: tuple[int, int]) -> bool:
        """`size` の画像に対し、領域が外へはみ出すか（背景色で埋める必要があるか）。"""
        width, height = size
        if self.x < 0 or self.y < 0:
            return True
        return self.x + self.width > width or self.y + self.height > height

    def to_dict(self) -> dict[str, int | str]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "columns": self.columns,
            "rows": self.rows,
            "fit": str(self.fit),
        }


def plan_region(size: tuple[int, int], grid: GridSpec, fit: Fit = Fit.COVER) -> ReduceRegion:
    """`size` の画像から `grid` へ縮小するときの元矩形を決める。中央合わせにする。"""
    grid.validate()
    width, height = size
    if width <= 0 or height <= 0:
        raise _invalid_grid(f"画像サイズが不正: {width}x{height}")

    if fit is Fit.STRETCH:
        region_width, region_height = width, height
    else:
        target = grid.aspect
        wider = width / height > target
        # COVER は内側へ収め、CONTAIN は外側へ広げる。判定が逆になるだけで式は同じ。
        keep_height = wider if fit is Fit.COVER else not wider
        if keep_height:
            region_width, region_height = max(1, round(height * target)), height
        else:
            region_width, region_height = width, max(1, round(width / target))

    return ReduceRegion(
        x=(width - region_width) // 2,
        y=(height - region_height) // 2,
        width=region_width,
        height=region_height,
        columns=grid.columns,
        rows=grid.rows,
        fit=fit,
    )


def extract_region(
    image: Image.Image,
    region: ReduceRegion,
    *,
    background: tuple[int, int, int] = WHITE,
) -> Image.Image:
    """`region` の矩形を切り出す。画像外へ出た分は `background` で埋める。

    元の `image` は変更しない。Pillow の `crop` は画像外を黒で埋めるため、はみ出す
    場合だけ背景色の台紙へ貼り直す。
    """
    if not region.padded_against(image.size):
        return image.crop(region.box)
    canvas = Image.new("RGB", (region.width, region.height), background)
    canvas.paste(image.convert("RGB"), (-region.x, -region.y))
    return canvas


def _invalid_grid(message: str) -> StageError:
    return StageError(
        _STAGE,
        "invalid_grid",
        message,
        hint="セル数とセル比を見直す。",
    )
