"""画像入力の受入判定と前処理。

FR-01（画像入力と前処理）の実装。
"""

from optpoet.image.validate import (
    SUPPORTED_FORMATS,
    ImageInfo,
    inspect_image,
)

__all__ = [
    "SUPPORTED_FORMATS",
    "ImageInfo",
    "inspect_image",
]
