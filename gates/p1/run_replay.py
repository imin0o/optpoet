"""P1-G04: AI を使わずに保存・再読込・再生が完了することを確かめる。

実行: `python gates/p1/run_replay.py [--slot portrait-3]`

手順は 1 本の流れで確かめる。実画像から最適化まで通す → PNG / TXT / manifest を保存 →
プロジェクトを開き直す → manifest だけを頼りに再生する → PNG と TXT がバイト一致する。
`ai_calls` が空であることも記録し、AI 応答なしで再生できたことを示す（AC-04 / AC-05）。
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from dataset import IMAGES, TEXT
from pipeline import run_case
from project_fixture import build_manifest
from run_gate import FONT, SETTINGS, STYLE

from optpoet.font import build_charset, build_dictionary, load_font_profile
from optpoet.image import GridSpec
from optpoet.manifest.store import load_manifest
from optpoet.project import OpenMode, open_project
from optpoet.render import load_layout, replay_outputs, write_outputs
from optpoet.storage import ProjectLayout, verify_refs

OUT = Path(__file__).resolve().parent / "out"
GRID = GridSpec(columns=50, rows=40)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", default="portrait-3")
    args = parser.parse_args()

    asset = next(a for a in IMAGES if a.slot == args.slot)
    profile = load_font_profile(FONT)
    dictionary = build_dictionary(profile, build_charset(), SETTINGS, levels=8)
    case = run_case(
        asset.slot,
        asset.path,
        TEXT.path.read_text(encoding="utf-8"),
        GRID,
        profile,
        dictionary,
        SETTINGS,
        STYLE,
    )

    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="optpoet-replay-") as tmp:
        layout = ProjectLayout(Path(tmp) / "project")
        layout.create()
        manifest = build_manifest(layout, SETTINGS)
        result = write_outputs(layout, case.optimized, manifest)

        opened = open_project(layout)
        stored = load_manifest(layout.manifest_path).data
        verify_refs(layout, stored)
        replay = replay_outputs(layout, stored, profile)
        reloaded_layout = load_layout(layout, stored)

        record: dict[str, Any] = {
            "slot": asset.slot,
            "grid": {"columns": GRID.columns, "rows": GRID.rows, "cells": GRID.cells},
            "open_mode": opened.mode.value,
            "ai_calls": len(stored["ai_calls"]),
            "png_ref": result.png_ref,
            "txt_ref": result.txt_ref,
            "replay": {
                "png_hash": replay.png_hash,
                "txt_hash": replay.txt_hash,
                "recorded_png_hash": replay.recorded_png_hash,
                "recorded_txt_hash": replay.recorded_txt_hash,
                "matches": replay.matches,
            },
            "txt_byte_identical": replay.artwork.txt == case.optimized.txt,
            "png_byte_identical": replay.artwork.png == case.optimized.png,
            "layout_identical": reloaded_layout.lines == case.optimized.layout.lines,
            "cell_check": stored["evaluation"]["cell_check"],
            "settings_identical": stored["outputs"]["render_metadata"] == SETTINGS.to_dict(),
        }

    record["safe"] = bool(
        opened.mode is OpenMode.NORMAL
        and record["ai_calls"] == 0
        and replay.matches
        and record["txt_byte_identical"]
        and record["png_byte_identical"]
        and record["layout_identical"]
        and record["settings_identical"]
    )
    (OUT / "replay.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in record.items() if k != "replay"}, ensure_ascii=False))
    print(f"[P1-G04] {'合格' if record['safe'] else '不合格'}")
    return 0 if record["safe"] else 1


if __name__ == "__main__":
    sys.exit(main())
