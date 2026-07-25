"""アプリ設定の既定値と TOML 読込。

既定値の根拠:

- 画像上限 50MP / 100MB: docs/quality-and-operations.md、P1-016
- 密度クラス 5〜10 段階: P1-025（既定 8 は docs/architecture.md 第1段階）
- 基準フォントは未確定のため暫定 Noto Sans JP（P0-012 の決定待ち）
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Any

from optpoet.errors import ConfigError

MIN_DENSITY_LEVELS = 5
MAX_DENSITY_LEVELS = 10


@dataclass(frozen=True, slots=True)
class GridConfig:
    """文字グリッドの寸法。"""

    columns: int = 60
    rows: int = 40

    @property
    def cells(self) -> int:
        return self.columns * self.rows

    def validate(self) -> None:
        _require_positive("grid.columns", self.columns)
        _require_positive("grid.rows", self.rows)


@dataclass(frozen=True, slots=True)
class ImageConfig:
    """入力画像の受入上限。"""

    max_pixels: int = 50_000_000
    max_bytes: int = 100 * 1024 * 1024

    def validate(self) -> None:
        _require_positive("image.max_pixels", self.max_pixels)
        _require_positive("image.max_bytes", self.max_bytes)


@dataclass(frozen=True, slots=True)
class DensityConfig:
    """密度マップと文字密度辞書の離散化設定。"""

    levels: int = 8

    def validate(self) -> None:
        if not MIN_DENSITY_LEVELS <= self.levels <= MAX_DENSITY_LEVELS:
            span = f"{MIN_DENSITY_LEVELS}〜{MAX_DENSITY_LEVELS}"
            raise ConfigError(f"density.levels は {span} の範囲: {self.levels}")


@dataclass(frozen=True, slots=True)
class FontConfig:
    """描画に使う基準フォント。path 未指定なら暗黙代替せず描画を止める。"""

    family: str = "Noto Sans JP"
    path: Path | None = None
    size_px: int = 32

    def validate(self) -> None:
        if not self.family:
            raise ConfigError("font.family が空")
        _require_positive("font.size_px", self.size_px)


@dataclass(frozen=True, slots=True)
class PathsConfig:
    """成果物とキャッシュの保存先。"""

    output_dir: Path = Path("output")
    cache_dir: Path = Path("cache")

    def validate(self) -> None:
        if self.output_dir == self.cache_dir:
            raise ConfigError("paths.output_dir と paths.cache_dir が同一")


@dataclass(frozen=True, slots=True)
class AppConfig:
    """アプリ全体の設定。"""

    grid: GridConfig = field(default_factory=GridConfig)
    image: ImageConfig = field(default_factory=ImageConfig)
    density: DensityConfig = field(default_factory=DensityConfig)
    font: FontConfig = field(default_factory=FontConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    seed: int = 0

    def validate(self) -> None:
        self.grid.validate()
        self.image.validate()
        self.density.validate()
        self.font.validate()
        self.paths.validate()
        if self.seed < 0:
            raise ConfigError(f"seed は 0 以上: {self.seed}")


_SECTIONS: dict[str, type] = {
    "grid": GridConfig,
    "image": ImageConfig,
    "density": DensityConfig,
    "font": FontConfig,
    "paths": PathsConfig,
}


def load_config(path: Path | None = None) -> AppConfig:
    """設定ファイルを読み、既定値へ重ねた `AppConfig` を返す。

    `path` が None の場合は既定値のみを返す。未知のキーや型不一致は
    `ConfigError` にし、暗黙に無視しない。
    """
    config = AppConfig()
    if path is not None:
        config = _apply(config, _read_toml(path))
    config.validate()
    return config


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except OSError as exc:
        raise ConfigError(f"設定ファイルを読めない: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"設定ファイルの TOML が不正: {path}: {exc}") from exc


def _apply(config: AppConfig, data: dict[str, Any]) -> AppConfig:
    updates: dict[str, Any] = {}
    for key, value in data.items():
        if key in _SECTIONS:
            if not isinstance(value, dict):
                raise ConfigError(f"[{key}] はテーブルである必要がある")
            updates[key] = _apply_section(key, getattr(config, key), value)
        elif key == "seed":
            updates[key] = _coerce("seed", value, int)
        else:
            raise ConfigError(f"未知の設定キー: {key}")
    return replace(config, **updates)


def _apply_section(section: str, current: Any, data: dict[str, Any]) -> Any:
    names = {f.name for f in fields(current)}
    updates: dict[str, Any] = {}
    for key, value in data.items():
        if key not in names:
            raise ConfigError(f"未知の設定キー: {section}.{key}")
        name = f"{section}.{key}"
        target = getattr(current, key)
        # 既定が None のフィールドは font.path のみ（`Path | None`）。
        if isinstance(target, Path) or target is None:
            updates[key] = Path(_coerce(name, value, str))
        elif isinstance(target, bool):
            updates[key] = _coerce(name, value, bool)
        elif isinstance(target, int):
            updates[key] = _coerce(name, value, int)
        else:
            updates[key] = _coerce(name, value, str)
    return replace(current, **updates)


def _coerce(name: str, value: Any, expected: type) -> Any:
    # bool は int の派生なので、int 期待時に True を通さない。
    if expected is int and isinstance(value, bool):
        raise ConfigError(f"{name} は整数である必要がある: {value!r}")
    if not isinstance(value, expected):
        raise ConfigError(f"{name} は {expected.__name__} である必要がある: {value!r}")
    return value


def _require_positive(name: str, value: int) -> None:
    if value <= 0:
        raise ConfigError(f"{name} は 1 以上: {value}")
