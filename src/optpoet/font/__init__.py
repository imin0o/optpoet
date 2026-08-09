"""フォントプロファイルと文字密度辞書（P1-C）。

密度測定と最終描画は `render.render_cell()` を共有し、同一フォント・同一設定で同じ画素を
生む（NFR-02 / docs/environment/rendering-engine.md）。
"""

from optpoet.font.charset import (
    CHARSET_VERSION,
    Charset,
    CharsetSpec,
    build_charset,
)
from optpoet.font.dictionary import (
    DICTIONARY_ID_PREFIX,
    DICTIONARY_SCHEMA_VERSION,
    DICTIONARY_STAGE_VERSION,
    DensityDictionary,
    LevelScale,
    build_dictionary,
    dictionary_cache_key,
)
from optpoet.font.profile import FontProfile, load_font_profile, resolve_font_path
from optpoet.font.render import (
    ENGINE,
    LAYOUT_ENGINE,
    RenderSettings,
    black_ratio,
    load_font,
    render_cell,
)

__all__ = [
    "CHARSET_VERSION",
    "DICTIONARY_ID_PREFIX",
    "DICTIONARY_SCHEMA_VERSION",
    "DICTIONARY_STAGE_VERSION",
    "ENGINE",
    "LAYOUT_ENGINE",
    "Charset",
    "CharsetSpec",
    "DensityDictionary",
    "FontProfile",
    "LevelScale",
    "RenderSettings",
    "black_ratio",
    "build_charset",
    "build_dictionary",
    "dictionary_cache_key",
    "load_font",
    "load_font_profile",
    "render_cell",
    "resolve_font_path",
]
