"""50MP / 100MB 境界と作業メモリ上限の検証（P1-016 / FR-01）。

境界そのものを実データで作ると 50MP の復号や 100MB の書き込みが要るため、上限判定が
見るところだけを実際に作る。画素数はヘッダ（IHDR）で、容量はファイル長で判定される
ので、ヘッダだけ正しい PNG と長さを合わせたファイルで境界を踏める。
"""

from __future__ import annotations

import struct
import tracemalloc
import zlib
from pathlib import Path

import pytest
from PIL import Image

from optpoet.config import ImageConfig
from optpoet.errors import StageError
from optpoet.image import GridSpec, build_density_map, estimate_working_bytes, inspect_image

MAX_PIXELS = 50_000_000
MAX_BYTES = 100 * 1024 * 1024
# 8000 x 6250 = 50,000,000。境界ちょうどを表せる寸法。
LIMIT_WIDTH = 8000
LIMIT_HEIGHT = 6250


def _chunk(kind: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)


def _png_header(path: Path, width: int, height: int, *, pad_to: int | None = None) -> Path:
    """寸法だけが本物の PNG を書く。実データは持たないので復号はできない。"""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    payload = b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", b"\x00")
    path.write_bytes(payload)
    if pad_to is not None:
        with path.open("r+b") as handle:
            handle.truncate(pad_to)
    return path


def test_default_limits_match_the_requirement() -> None:
    limits = ImageConfig()
    assert limits.max_pixels == MAX_PIXELS
    assert limits.max_bytes == MAX_BYTES


def test_exactly_fifty_megapixels_is_accepted() -> None:
    assert LIMIT_WIDTH * LIMIT_HEIGHT == MAX_PIXELS


def test_pixel_limit_accepts_the_boundary(tmp_path: Path) -> None:
    path = _png_header(tmp_path / "boundary.png", LIMIT_WIDTH, LIMIT_HEIGHT)
    info = inspect_image(path, decode=False)
    assert info.pixels == MAX_PIXELS


def test_pixel_limit_rejects_one_row_over(tmp_path: Path) -> None:
    path = _png_header(tmp_path / "over.png", LIMIT_WIDTH, LIMIT_HEIGHT + 1)
    with pytest.raises(StageError) as excinfo:
        inspect_image(path, decode=False)
    error = excinfo.value
    assert error.code == "too_many_pixels"
    assert error.hint is not None


def test_byte_limit_accepts_the_boundary(tmp_path: Path) -> None:
    path = _png_header(tmp_path / "boundary_bytes.png", 100, 100, pad_to=MAX_BYTES)
    assert path.stat().st_size == MAX_BYTES
    assert inspect_image(path, decode=False).bytes == MAX_BYTES


def test_byte_limit_rejects_one_byte_over(tmp_path: Path) -> None:
    path = _png_header(tmp_path / "over_bytes.png", 100, 100, pad_to=MAX_BYTES + 1)
    with pytest.raises(StageError) as excinfo:
        inspect_image(path, decode=False)
    error = excinfo.value
    assert error.code == "too_large_bytes"
    assert error.hint is not None


def test_working_memory_limit_covers_the_pixel_limit() -> None:
    """上限画素数の画像でも、既定の作業メモリ上限内に収まる見積りにする。"""
    assert estimate_working_bytes(MAX_PIXELS) <= ImageConfig().max_working_bytes


def test_working_memory_estimate_is_linear() -> None:
    assert estimate_working_bytes(2_000_000) == 2 * estimate_working_bytes(1_000_000)


def test_density_map_is_rejected_just_below_the_estimate() -> None:
    image = Image.new("RGB", (200, 100), (128, 128, 128))
    estimate = estimate_working_bytes(200 * 100)
    limits = ImageConfig(max_working_bytes=estimate - 1)
    with pytest.raises(StageError) as excinfo:
        build_density_map(image, GridSpec(columns=10, rows=5), limits=limits)
    assert excinfo.value.code == "memory_limit"


def test_density_map_runs_at_the_estimate() -> None:
    image = Image.new("RGB", (200, 100), (128, 128, 128))
    limits = ImageConfig(max_working_bytes=estimate_working_bytes(200 * 100))
    assert build_density_map(image, GridSpec(columns=10, rows=5), limits=limits).shape == (5, 10)


def test_density_map_stays_within_the_estimate() -> None:
    """実測ピークが見積りを超えないことを確かめる。

    tracemalloc は NumPy の確保（専用ドメイン）を含む。Pillow の C 側確保は含まないが、
    見積りはその分も乗せた保守側の値なので、上限としては成立する。
    """
    image = Image.new("RGB", (800, 600), (90, 90, 90))
    grid = GridSpec(columns=40, rows=30)
    tracemalloc.start()
    try:
        build_density_map(image, grid)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak <= estimate_working_bytes(800 * 600)
