"""P1-G03: 破損画像・上限超過・欠落グリフ・容量不足で安全停止することを確かめる。

実行: `python gates/p1/run_abnormal.py`

安全停止の条件は 2 つ。**構造化エラーで止まること**（工程・区分・原因・対処が付く）と、
**既に保存済みの有効版が壊れないこと**（save-and-migration.md A-08）。両方を確認する。
"""

from __future__ import annotations

import json
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from dataset import IMAGES, OVERSIZED
from project_fixture import build_project, render_case

from optpoet.config import ImageConfig
from optpoet.errors import StageError, StorageError
from optpoet.font import build_charset, load_font_profile
from optpoet.image import inspect_image
from optpoet.manifest.store import load_manifest
from optpoet.project import OpenMode, open_project
from optpoet.render import replay_outputs
from optpoet.render.output import write_outputs
from optpoet.text import require_supported

OUT = Path(__file__).resolve().parent / "out"
FONT = Path(r"C:\Windows\Fonts\NotoSansJP-VF.ttf")

PADDING = b"\x00" * (8 * 1024 * 1024)


def broken_image(work: Path) -> dict[str, Any]:
    """途中で切れた JPEG。ヘッダは通り、復号で落ちる。"""
    source = IMAGES[2].path  # portrait-3（最小の JPEG）
    target = work / "broken.jpg"
    data = source.read_bytes()
    target.write_bytes(data[: len(data) // 5])
    return _expect_stage_error(lambda: inspect_image(target, ImageConfig()))


def oversized_pixels(work: Path) -> dict[str, Any]:
    """50MP 超の原本（validation-dataset.md 4.2 の上限超過用 = 50,291,940 px）。"""
    return _expect_stage_error(lambda: inspect_image(OVERSIZED.path, ImageConfig()))


def oversized_bytes(work: Path) -> dict[str, Any]:
    """100MB 超のファイル。復号前にファイル長で止まる。"""
    source = next(a for a in IMAGES if a.slot == "still-life-1")
    target = work / "huge.jpg"
    with target.open("wb") as handle:
        handle.write(source.path.read_bytes())
        for _ in range(13):  # 8MB × 13 で 100MB を超える
            handle.write(PADDING)
    return _expect_stage_error(lambda: inspect_image(target, ImageConfig()))


def missing_glyph(work: Path) -> dict[str, Any]:
    """フォントに無い文字。cmap を根拠に描画前で止める（暗黙代替を許さない）。"""
    profile = load_font_profile(FONT)
    # 基準フォント（Noto Sans JP）が持たない字。デーヴァナーガリー・ハングル・絵文字。
    absent = "".join(chr(cp) for cp in (0x0915, 0xAC00, 0x1F600) if not profile.supports(chr(cp)))
    if not absent:
        raise SystemExit("フォントに無い文字を用意できない（フォントを見直す）")
    return _expect_stage_error(lambda: profile.require(absent))


def unsupported_char(work: Path) -> dict[str, Any]:
    """許可文字集合の外にある文字。入力時点で示して止める（暗黙削除を許さない）。"""
    charset = build_charset()
    return _expect_stage_error(lambda: require_supported("これはＡＢＣ😀です", charset))


def disk_full(work: Path) -> dict[str, Any]:
    """保存中の容量不足。直前の有効版が残り、再読込と再生が通ることを確かめる。"""
    import optpoet.project.save as save_module

    layout, manifest, artwork = build_project(work / "project", FONT)
    write_outputs(layout, artwork, manifest)
    first = load_manifest(layout.manifest_path).data
    first_updated = first["manifest"]["updated_at"]

    original = save_module.write_and_sync

    def no_space(path: Path, data: bytes) -> None:
        raise StorageError(f"容量不足で書けない（模擬 ENOSPC）: {path}")

    save_module.write_and_sync = no_space  # type: ignore[assignment]
    try:
        second = render_case(FONT, text="いろはにほへとちりぬるを")
        record = _expect_error(lambda: write_outputs(layout, second, dict(manifest)), StorageError)
    finally:
        save_module.write_and_sync = original  # type: ignore[assignment]

    opened = open_project(layout)
    replay = replay_outputs(layout, opened.manifest.data, load_font_profile(FONT))
    record["recovered"] = {
        "open_mode": opened.mode.value,
        "manifest_unchanged": opened.manifest.data["manifest"]["updated_at"] == first_updated,
        "replay_matches": replay.matches,
    }
    record["safe"] = bool(
        opened.mode is OpenMode.NORMAL
        and record["recovered"]["manifest_unchanged"]
        and replay.matches
    )
    return record


CASES: dict[str, Callable[[Path], dict[str, Any]]] = {
    "broken_image": broken_image,
    "oversized_pixels": oversized_pixels,
    "oversized_bytes": oversized_bytes,
    "missing_glyph": missing_glyph,
    "unsupported_char": unsupported_char,
    "disk_full": disk_full,
}


def _expect_stage_error(call: Callable[[], Any]) -> dict[str, Any]:
    return _expect_error(call, StageError)


def _expect_error(call: Callable[[], Any], expected: type[Exception]) -> dict[str, Any]:
    try:
        call()
    except expected as exc:
        record: dict[str, Any] = {"stopped": True, "error_type": type(exc).__name__}
        for name in ("stage", "code", "failure_class", "hint"):
            value = getattr(exc, name, None)
            if value is not None:
                record[name] = str(value)
        record["message"] = str(exc)
        record["safe"] = True
        return record
    except Exception as exc:
        # 想定と違う例外も記録して不合格にする（黙って通さない）。
        return {
            "stopped": True,
            "safe": False,
            "error_type": type(exc).__name__,
            "message": str(exc),
        }
    return {"stopped": False, "safe": False, "message": "停止しなかった"}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="optpoet-gate-") as tmp:
        work = Path(tmp)
        for name, case in CASES.items():
            results[name] = case(work)
            mark = "安全停止" if results[name]["safe"] else "不合格"
            print(f"  {name:<18} {mark}: {results[name].get('code', '-')}")
    (OUT / "abnormal.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    failed = [name for name, record in results.items() if not record["safe"]]
    print(f"[P1-G03] {'合格' if not failed else '不合格: ' + ', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
