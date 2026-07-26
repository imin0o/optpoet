"""入力画像の形式・破損・上限を判定する（P1-010 / FR-01）。

判定順は「安いものから」で固定する。ファイル長 → ヘッダ（形式・寸法）→ 実データの
復号。上限超過や未対応形式で復号まで進まないため、巨大ファイルや壊れたファイルを
掴んだときの待ち時間を作らない。

上限は 50 メガピクセルか 100 MB の小さい方（requirements.md FR-01）。既定値は
`optpoet.config.ImageConfig` にあり、超過時は理由に加えて縮小案を `hint` へ入れる。

失敗は工程 `normalize` の `StageError` にする。区分はいずれも `needs_config` で、
作者が別の画像を選ぶか縮小するまで再試行しても結果は変わらない。
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from optpoet.config import ImageConfig
from optpoet.errors import StageError
from optpoet.storage import Stage

# Pillow の format 名 → 作者向け表示名。この 4 形式以外は受け入れない。
SUPPORTED_FORMATS: dict[str, str] = {
    "JPEG": "JPEG",
    "PNG": "PNG",
    "TIFF": "TIFF",
    "WEBP": "WebP",
}

_STAGE = str(Stage.NORMALIZE)


@dataclass(frozen=True, slots=True)
class ImageInfo:
    """受入判定を通った画像のヘッダ情報。前処理の入力になる。"""

    path: Path
    format: str
    mode: str
    width: int
    height: int
    bytes: int

    @property
    def pixels(self) -> int:
        return self.width * self.height


def inspect_image(
    path: Path,
    limits: ImageConfig | None = None,
    *,
    decode: bool = True,
) -> ImageInfo:
    """`path` の画像を判定し、通れば `ImageInfo` を返す。

    `decode` を False にすると実データの復号を省き、ヘッダだけで判定する。一覧表示の
    ような速度優先の用途向けで、途中で切れたファイルは検出できない。
    """
    limits = limits or ImageConfig()
    size = _stat_bytes(path)
    if size > limits.max_bytes:
        raise _too_large_bytes(path, size, limits.max_bytes)

    with _opened(path) as image:
        image_format = image.format or ""
        if image_format not in SUPPORTED_FORMATS:
            raise _unsupported_format(path, image_format)
        width, height = image.size
        info = ImageInfo(
            path=path,
            format=image_format,
            mode=image.mode,
            width=width,
            height=height,
            bytes=size,
        )

    if info.pixels > limits.max_pixels:
        raise _too_many_pixels(info, limits.max_pixels)
    if decode:
        _decode(path)
    return info


def _stat_bytes(path: Path) -> int:
    try:
        stat = path.stat()
    except OSError as exc:
        raise StageError(
            _STAGE,
            "not_found",
            f"画像ファイルを読めない: {path}",
            hint="パスと読み取り権限を確認する。",
        ) from exc
    if not path.is_file():
        raise StageError(
            _STAGE,
            "not_found",
            f"画像ファイルではない: {path}",
            hint="ファイルを指定する。",
        )
    return stat.st_size


def _opened(path: Path) -> Image.Image:
    """ヘッダだけを読んで開く。復号は `_decode` で別に行う。"""
    try:
        # 上限は limits で判定するため、Pillow 側の既定しきい値の警告は抑える。
        # DecompressionBombError（既定の 2 倍超）は寸法超過として扱う。
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            return Image.open(path)
    except Image.DecompressionBombError as exc:
        raise StageError(
            _STAGE,
            "too_many_pixels",
            f"画像の画素数が大きすぎる: {path}",
            hint="縮小してから読み込む。",
        ) from exc
    except UnidentifiedImageError as exc:
        raise StageError(
            _STAGE,
            "corrupted",
            f"画像として解釈できない: {path}",
            hint="ファイルが壊れていないか、対応形式かを確認する。",
        ) from exc
    except OSError as exc:
        raise StageError(
            _STAGE,
            "corrupted",
            f"画像ヘッダを読めない: {path}: {exc}",
            hint="ファイルが壊れていないかを確認する。",
        ) from exc


def _decode(path: Path) -> None:
    """実データを復号し、途中で切れたファイルや壊れた圧縮データを弾く。"""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                image.load()
    except (OSError, ValueError, SyntaxError) as exc:
        raise StageError(
            _STAGE,
            "corrupted",
            f"画像データが壊れている: {path}: {exc}",
            hint="元のファイルを取り直す。",
        ) from exc


def _unsupported_format(path: Path, image_format: str) -> StageError:
    supported = " / ".join(SUPPORTED_FORMATS.values())
    detected = image_format or "不明"
    return StageError(
        _STAGE,
        "unsupported_format",
        f"未対応の画像形式: {detected}: {path}",
        hint=f"{supported} のいずれかへ変換する。",
    )


def _too_large_bytes(path: Path, size: int, limit: int) -> StageError:
    return StageError(
        _STAGE,
        "too_large_bytes",
        f"ファイル容量が上限を超えた: {_mib(size)} MB > {_mib(limit)} MB: {path}",
        hint=f"再圧縮するか、長辺を約 {_ratio_percent(limit, size)}% へ縮小して保存し直す。",
    )


def _too_many_pixels(info: ImageInfo, limit: int) -> StageError:
    scale = math.sqrt(limit / info.pixels)
    width = max(1, int(info.width * scale))
    height = max(1, int(info.height * scale))
    return StageError(
        _STAGE,
        "too_many_pixels",
        (
            f"画素数が上限を超えた: {info.pixels:,} px > {limit:,} px "
            f"({info.width}x{info.height}): {info.path}"
        ),
        hint=f"{width}x{height} 以下へ縮小する。",
    )


def _mib(value: int) -> str:
    return f"{value / (1024 * 1024):.1f}"


def _ratio_percent(limit: int, size: int) -> int:
    """容量比から長辺の縮小率の目安を出す。容量は面積にほぼ比例するとみなす。"""
    return max(1, int(math.sqrt(limit / size) * 100))
