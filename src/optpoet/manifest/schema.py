"""manifest の層 A スキーマ（既知キーのみ許可）。

ブロック構成と必須区分は docs/decisions/project-manifest.md「必須ブロックと必須項目」、
キー名は docs/samples/manifest.sample.json に対応する。値の型・単位・列挙値は同 docs が
Phase 1 実装へ委譲しているため、本モジュールは「既知キーの集合」と必須区分だけを固定し、
値の検証は各工程（P1-B 以降）に任せる。未確定の領域は `Free` で明示する。

スキーマ記述形式は言語内定義とする（docs/decisions/secret-exclusion-test.md が Phase 1 へ
委譲）。外部依存を増やさず、未知キー拒否（D-01）と禁止キー名（D-02）を同じ走査で扱える。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

type Node = Obj | Arr | Free


@dataclass(frozen=True, slots=True)
class Free:
    """値スキーマ未確定の領域。キーも値も検査しない（禁止キー名走査は全域で別途行う）。"""


@dataclass(frozen=True, slots=True)
class Arr:
    """配列。全要素が同じ形を取る。"""

    item: Node


@dataclass(frozen=True, slots=True)
class Obj:
    """オブジェクト。`required` / `optional` に無いキーは未知キーとして拒否する。"""

    required: Mapping[str, Node] = field(default_factory=dict)
    optional: Mapping[str, Node] = field(default_factory=dict)


def _free(*names: str) -> dict[str, Node]:
    """値スキーマ未確定のキー集合。"""
    return {name: FREE for name in names}


FREE = Free()

# ref の共通形（project-manifest.md「ref の共通形」）
REF = Obj(
    required=_free("path", "hash", "media_type"),
    optional=_free("schema_version", "bytes"),
)

_SIZE = Obj(required=_free("width", "height"))

# 密度測定と最終描画で共有する描画設定（NFR-02。中身は P1-C で締める）
_RENDER = Obj(
    optional={
        **_free(
            "engine",
            "engine_version",
            "freetype_version",
            "layout_engine",
            "mode",
            "pixel_size",
            "background",
            "foreground",
            "antialias",
        ),
        "cell": _SIZE,
    }
)

_PROVENANCE = Obj(
    required={
        "model_id": Obj(
            required=_free("provider", "model", "version"),
            optional=_free("requested"),
        ),
        "prompt_ref": REF,
        **_free("request_hash", "token_usage", "route", "created_at"),
        "retry_count": Obj(optional=_free("attempts", "total_wait_ms", "classes")),
    }
)

MANIFEST_SPEC = Obj(
    required={
        "manifest": Obj(
            required=_free(
                "schema_version", "project_id", "app_version", "created_at", "updated_at"
            ),
            optional=_free("title"),
        ),
        "input": Obj(
            required={
                "source": REF,
                "pixel_size": _SIZE,
                "byte_size": FREE,
                "normalization": Obj(
                    optional=_free("exif_orientation", "exif_stripped", "icc", "alpha")
                ),
            },
            optional={"normalized_ref": REF},
        ),
        "preprocess": Obj(
            required={
                "crop": Obj(required=_free("x", "y", "width", "height")),
                **_free("rotate", "brightness", "contrast", "gamma", "invert"),
            },
            optional={"result_ref": REF},
        ),
        "grid": Obj(
            required={
                **_free(
                    "cols",
                    "rows",
                    "cell_aspect",
                    "font_size",
                    "line_spacing",
                    "char_spacing",
                    "reading_order",
                    "normalization_form",
                ),
                "output_size": _SIZE,
            }
        ),
        "fonts": Obj(
            required={
                # 文字種はフォント割当の拡張とともに増えるため写像ごと未確定扱いにする。
                "assignments": FREE,
                "font_files": Arr(
                    Obj(
                        required=_free("font_key", "file_name", "hash", "weight", "version"),
                        optional=_free("license"),
                    )
                ),
                "render_settings": _RENDER,
                "dictionary_id": FREE,
                "missing_glyphs": Arr(FREE),
            },
            optional={"dictionary_ref": REF},
        ),
        "density": Obj(
            required={
                "method": Obj(
                    optional=_free("name", "gamma", "local_contrast", "edge_weight", "levels")
                )
            },
            optional={"map_ref": REF, "edge_ref": REF},
        ),
        "semantic_design": Obj(
            required=_free("author_edited", "pinned"),
            optional=_free("observed", "interpreted", "source_call"),
        ),
        "text": Obj(
            required={
                "mode": FREE,
                "chaos": Obj(optional=_free("grammar_order", "individual_rate")),
            },
            optional={
                "draft_refs": Arr(REF),
                "candidate_refs": Arr(REF),
                "final_ref": REF,
                "materials": Arr(FREE),
            },
        ),
        "optimization": Obj(
            required={
                "weights": Obj(
                    required=_free(
                        "visual_similarity",
                        "language_quality",
                        "image_relevance",
                        "style_consistency",
                    )
                ),
                **_free("tolerance", "max_iterations", "seed"),
                "algorithm": Obj(required=_free("name"), optional=_free("version")),
                "pins": Obj(optional=_free("regions", "phrases", "stages")),
                "budget_caps": Obj(
                    optional={
                        **_free("currency", "cost_cap", "calls_cap"),
                        "token_cap": Obj(optional=_free("input", "output")),
                    }
                ),
            },
            optional={"trace_ref": REF},
        ),
        "ai_calls": Arr(
            Obj(
                required={
                    **_free("call_id", "capability", "operation", "status"),
                    "request_ref": REF,
                    "response_ref": REF,
                    "provenance": _PROVENANCE,
                },
                optional=_free("seq", "failure_class", "superseded_by"),
            )
        ),
        "edits": Arr(
            Obj(
                required=_free("edit_id", "at", "target", "change", "invalidated"),
                optional=_free("seq", "kind", "note"),
            )
        ),
        "evaluation": Obj(
            optional={
                "metrics": Obj(
                    required=_free("spec_version"),
                    optional=_free(
                        "mae_draft",
                        "mae_opt",
                        "improvement_rate",
                        "ssim",
                        "edge_dice",
                        "region_mae",
                    ),
                ),
                "cell_check": Obj(
                    required=_free("expected_cells", "displayed_chars"),
                    optional=_free("result"),
                ),
            }
        ),
        "outputs": Obj(
            optional={"png_ref": REF, "txt_ref": REF, "render_metadata": _RENDER},
        ),
    }
)

# 禁止キー名（secret-exclusion-test.md D-02）。スキーマが緩められた場合の保険。
FORBIDDEN_KEY_NAMES = frozenset(
    {
        "apikey",
        "authorization",
        "auth",
        "token",
        "accesstoken",
        "refreshtoken",
        "secret",
        "password",
        "credential",
        "bearer",
        "xapikey",
        "cookie",
        "session",
    }
)


def normalize_key(name: str) -> str:
    """禁止キー名の比較用正規形（小文字化し `-` `_` を除去）。"""
    return name.lower().replace("-", "").replace("_", "")
