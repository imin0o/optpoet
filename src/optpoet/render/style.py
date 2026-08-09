"""最終描画の見た目設定（P1-041 / FR-12）。

`RenderSettings`（P1-023）は密度辞書と共有する「1 セルの画素を決める」設定で、変えれば
辞書ごと作り直しになる。対して `RenderStyle` は 1 セルの画素配置を変えずに、**セルの
並べ方**（字間・行間）と **塗り方**（文字色・背景色・二値化・反転）だけを決める。分けて
おけば、色や字間を変えても辞書を再生成しなくて済む。

塗りは **被覆率** を介する。被覆率は `black_ratio` と同じ `(背景 - 画素) / (背景 - 前景)`
で、0.0 が紙、1.0 が墨。二値化・反転・色付けはすべて被覆率へ掛かるため、`RenderSettings`
の `background` / `foreground` はグレースケール固定のままでよい。

字間・行間はセルの **送り幅**（升目の大きさ）で、既定はセル寸法そのもの。セル寸法より
小さい送りは字が重なるため受けない。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from optpoet.errors import StageError
from optpoet.font.render import RenderSettings
from optpoet.storage import Stage

type Color = tuple[int, int, int]

INK: Color = (0, 0, 0)
PAPER: Color = (255, 255, 255)

_STAGE = str(Stage.RENDER)


@dataclass(frozen=True, slots=True)
class RenderStyle:
    """最終描画の見た目。`char_spacing` / `line_spacing` が None ならセル寸法を使う。"""

    char_spacing: int | None = None
    line_spacing: int | None = None
    foreground: Color = INK
    background: Color = PAPER
    binarize: float | None = None
    """被覆率のしきい値（0.0〜1.0）。None ならアンチエイリアスの階調をそのまま使う。"""
    invert: bool = False
    """墨と紙を入れ替える。被覆率を 1 - 被覆率 にするのと同じ。"""

    @property
    def mode(self) -> str:
        """出力画像のモード。無彩色だけなら L にし、辞書のセルと同じ画素値を保つ。"""
        return "L" if _gray(self.foreground) and _gray(self.background) else "RGB"

    def char_pitch(self, settings: RenderSettings) -> int:
        return settings.cell_width if self.char_spacing is None else self.char_spacing

    def line_pitch(self, settings: RenderSettings) -> int:
        return settings.cell_height if self.line_spacing is None else self.line_spacing

    def validate(self, settings: RenderSettings) -> None:
        for name, color in (("foreground", self.foreground), ("background", self.background)):
            _validate_color(name, color)
        if self.foreground == self.background:
            raise _invalid_style("foreground と background が同値では文字が見えない")
        if self.binarize is not None and not 0.0 <= self.binarize <= 1.0:
            raise _invalid_style(f"binarize は 0.0〜1.0: {self.binarize}")
        pitch = self.char_pitch(settings)
        if pitch < settings.cell_width:
            raise _invalid_style(f"char_spacing がセル幅より狭い: {pitch} < {settings.cell_width}")
        line = self.line_pitch(settings)
        if line < settings.cell_height:
            raise _invalid_style(f"line_spacing がセル高より狭い: {line} < {settings.cell_height}")

    def to_dict(self, settings: RenderSettings) -> dict[str, Any]:
        """manifest の `outputs.render_metadata.style`。送りは解決後の値で記録する。"""
        return {
            "char_spacing": self.char_pitch(settings),
            "line_spacing": self.line_pitch(settings),
            "foreground_color": list(self.foreground),
            "background_color": list(self.background),
            "binarize": self.binarize,
            "invert": self.invert,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RenderStyle:
        """記録した見た目設定を復元する（P1-046）。欠けた項目は既定値にしない。"""
        try:
            return cls(
                char_spacing=_as_int(data["char_spacing"], "char_spacing"),
                line_spacing=_as_int(data["line_spacing"], "line_spacing"),
                foreground=_as_color(data["foreground_color"], "foreground_color"),
                background=_as_color(data["background_color"], "background_color"),
                binarize=_as_threshold(data["binarize"]),
                invert=bool(data["invert"]),
            )
        except KeyError as exc:
            raise _invalid_style(f"見た目設定に {exc.args[0]!r} がない") from None


def _gray(color: Color) -> bool:
    return color[0] == color[1] == color[2]


def _validate_color(name: str, color: Color) -> None:
    if len(color) != 3:
        raise _invalid_style(f"{name} は RGB の 3 要素: {color!r}")
    for value in color:
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 255:
            raise _invalid_style(f"{name} の成分は 0〜255 の整数: {color!r}")


def _as_int(value: Any, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise _invalid_style(f"{name} は整数: {value!r}")
    return value


def _as_color(value: Any, name: str) -> Color:
    if not isinstance(value, list | tuple) or len(value) != 3:
        raise _invalid_style(f"{name} は RGB の 3 要素: {value!r}")
    color = (_as_int(value[0], name), _as_int(value[1], name), _as_int(value[2], name))
    _validate_color(name, color)
    return color


def _as_threshold(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise _invalid_style(f"binarize は数値または null: {value!r}")
    return float(value)


def _invalid_style(message: str) -> StageError:
    return StageError(
        _STAGE,
        "invalid_style",
        message,
        hint="字間・行間・色・二値化の設定を見直す。",
    )
