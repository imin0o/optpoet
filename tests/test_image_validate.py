"""入力画像の形式・破損・上限判定の検証（P1-010 / FR-01）。"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from optpoet.config import ImageConfig
from optpoet.errors import ErrorKind, StageError
from optpoet.image import ImageInfo, inspect_image

FORMATS = [
    ("JPEG", "sample.jpg", "RGB"),
    ("PNG", "sample.png", "RGB"),
    ("TIFF", "sample.tif", "RGB"),
    ("WEBP", "sample.webp", "RGB"),
]


def _write_image(
    path: Path,
    image_format: str,
    *,
    size: tuple[int, int] = (32, 24),
    mode: str = "RGB",
) -> Path:
    Image.new(mode, size, color=(120, 60, 30) if mode == "RGB" else 120).save(
        path, format=image_format
    )
    return path


@pytest.mark.parametrize(("image_format", "name", "mode"), FORMATS)
def test_accepts_supported_formats(tmp_path: Path, image_format: str, name: str, mode: str) -> None:
    path = _write_image(tmp_path / name, image_format, mode=mode)
    info = inspect_image(path)
    assert isinstance(info, ImageInfo)
    assert info.format == image_format
    assert (info.width, info.height) == (32, 24)
    assert info.pixels == 32 * 24
    assert info.bytes == path.stat().st_size


def test_format_is_decided_by_content_not_suffix(tmp_path: Path) -> None:
    """拡張子が実体と食い違っても中身で判定する。"""
    path = _write_image(tmp_path / "actually.png", "PNG")
    renamed = path.replace(tmp_path / "claims.jpg")
    assert inspect_image(renamed).format == "PNG"


def test_grayscale_mode_is_reported(tmp_path: Path) -> None:
    path = _write_image(tmp_path / "gray.png", "PNG", mode="L")
    assert inspect_image(path).mode == "L"


def test_rejects_unsupported_format(tmp_path: Path) -> None:
    path = _write_image(tmp_path / "sample.bmp", "BMP")
    with pytest.raises(StageError) as excinfo:
        inspect_image(path)
    assert excinfo.value.code == "unsupported_format"
    assert excinfo.value.kind is ErrorKind.NEEDS_CONFIG
    assert excinfo.value.hint is not None


def test_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(StageError) as excinfo:
        inspect_image(tmp_path / "none.png")
    assert excinfo.value.code == "not_found"


def test_rejects_directory(tmp_path: Path) -> None:
    directory = tmp_path / "dir.png"
    directory.mkdir()
    with pytest.raises(StageError) as excinfo:
        inspect_image(directory)
    assert excinfo.value.code == "not_found"


def test_rejects_garbage_bytes(tmp_path: Path) -> None:
    path = tmp_path / "garbage.png"
    path.write_bytes(b"not an image at all")
    with pytest.raises(StageError) as excinfo:
        inspect_image(path)
    assert excinfo.value.code == "corrupted"


def test_rejects_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.png"
    path.write_bytes(b"")
    with pytest.raises(StageError) as excinfo:
        inspect_image(path)
    assert excinfo.value.code == "corrupted"


def test_rejects_truncated_image(tmp_path: Path) -> None:
    """ヘッダは読めるが実データが途中で切れている場合も破損として弾く。"""
    path = _write_image(tmp_path / "truncated.png", "PNG", size=(200, 200))
    data = path.read_bytes()
    path.write_bytes(data[: len(data) // 2])
    with pytest.raises(StageError) as excinfo:
        inspect_image(path)
    assert excinfo.value.code == "corrupted"


def test_truncated_image_passes_header_only_check(tmp_path: Path) -> None:
    """decode=False はヘッダだけを見るため、途中で切れたファイルを検出しない。"""
    path = _write_image(tmp_path / "truncated.png", "PNG", size=(200, 200))
    data = path.read_bytes()
    path.write_bytes(data[: len(data) // 2])
    info = inspect_image(path, decode=False)
    assert (info.width, info.height) == (200, 200)


def test_rejects_too_many_pixels_with_resize_hint(tmp_path: Path) -> None:
    path = _write_image(tmp_path / "big.png", "PNG", size=(400, 200))
    limits = ImageConfig(max_pixels=20_000, max_bytes=100 * 1024 * 1024)
    with pytest.raises(StageError) as excinfo:
        inspect_image(path, limits)
    error = excinfo.value
    assert error.code == "too_many_pixels"
    assert error.kind is ErrorKind.NEEDS_CONFIG
    # 縮小案は元の縦横比を保ち、上限内に収まる寸法を示す（sqrt(20000/80000)=0.5）。
    assert error.hint == "200x100 以下へ縮小する。"


def test_rejects_too_large_bytes(tmp_path: Path) -> None:
    path = _write_image(tmp_path / "heavy.png", "PNG", size=(64, 64))
    limits = ImageConfig(max_pixels=50_000_000, max_bytes=1)
    with pytest.raises(StageError) as excinfo:
        inspect_image(path, limits)
    error = excinfo.value
    assert error.code == "too_large_bytes"
    assert error.hint is not None and "縮小" in error.hint


def test_byte_limit_is_checked_before_decode(tmp_path: Path) -> None:
    """容量超過は復号前に判定するので、壊れたファイルでも容量側の理由を返す。"""
    path = tmp_path / "heavy_broken.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 4096)
    limits = ImageConfig(max_pixels=50_000_000, max_bytes=1024)
    with pytest.raises(StageError) as excinfo:
        inspect_image(path, limits)
    assert excinfo.value.code == "too_large_bytes"


def test_default_limits_accept_normal_image(tmp_path: Path) -> None:
    path = _write_image(tmp_path / "normal.png", "PNG", size=(1200, 800))
    info = inspect_image(path)
    assert info.pixels < ImageConfig().max_pixels
    assert info.bytes < ImageConfig().max_bytes


def test_error_payload_carries_stage_and_code(tmp_path: Path) -> None:
    path = _write_image(tmp_path / "sample.bmp", "BMP")
    with pytest.raises(StageError) as excinfo:
        inspect_image(path)
    payload = excinfo.value.to_dict()
    assert payload["stage"] == "normalize"
    assert payload["code"] == "unsupported_format"
    assert payload["kind"] == "needs_config"
