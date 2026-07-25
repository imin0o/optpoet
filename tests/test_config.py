"""設定の既定値・読込・検証のテスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

from optpoet import AppConfig, ConfigError, load_config


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_defaults() -> None:
    config = load_config()
    assert config.grid.columns == 60
    assert config.grid.cells == 2400
    assert config.image.max_pixels == 50_000_000
    assert config.image.max_bytes == 100 * 1024 * 1024
    assert config.density.levels == 8
    assert config.font.path is None
    assert config.paths.output_dir == Path("output")
    assert config.seed == 0


def test_load_overrides(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        """
        seed = 7

        [grid]
        columns = 100
        rows = 50

        [density]
        levels = 10

        [font]
        family = "Noto Serif JP"
        path = "C:/fonts/NotoSerifJP.ttf"

        [paths]
        output_dir = "out"
        """,
    )
    config = load_config(path)
    assert config.seed == 7
    assert config.grid.cells == 5000
    assert config.density.levels == 10
    assert config.font.family == "Noto Serif JP"
    assert config.font.path == Path("C:/fonts/NotoSerifJP.ttf")
    assert config.paths.output_dir == Path("out")
    # 未指定のセクションは既定値を保つ。
    assert config.image.max_pixels == AppConfig().image.max_pixels
    assert config.paths.cache_dir == Path("cache")


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="読めない"):
        load_config(tmp_path / "absent.toml")


def test_broken_toml(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="TOML が不正"):
        load_config(_write(tmp_path, "grid = ["))


@pytest.mark.parametrize(
    ("body", "match"),
    [
        ("unknown = 1", "未知の設定キー: unknown"),
        ("[grid]\ncols = 10", "未知の設定キー: grid.cols"),
        ('grid = "x"', r"\[grid\] はテーブル"),
        ('[grid]\ncolumns = "10"', "grid.columns は int"),
        ("[grid]\ncolumns = true", "grid.columns は整数"),
        ("[grid]\ncolumns = 0", "grid.columns は 1 以上"),
        ("[density]\nlevels = 4", "density.levels は 5〜10"),
        ("[density]\nlevels = 11", "density.levels は 5〜10"),
        ('[font]\nfamily = ""', "font.family が空"),
        ("[font]\nsize_px = -1", "font.size_px は 1 以上"),
        ("seed = -1", "seed は 0 以上"),
        ('[paths]\noutput_dir = "same"\ncache_dir = "same"', "同一"),
    ],
)
def test_invalid_values(tmp_path: Path, body: str, match: str) -> None:
    with pytest.raises(ConfigError, match=match):
        load_config(_write(tmp_path, body))


def test_config_is_frozen() -> None:
    config = load_config()
    with pytest.raises(AttributeError):
        config.seed = 1  # type: ignore[misc]
