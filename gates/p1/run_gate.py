"""P1-G01 / P1-G02 / P1-G05 を固定 12 画像で実行し、結果を JSON へ残す。

実行: `python gates/p1/run_gate.py [--cells 2000 5000] [--slots portrait-1 ...]`

- P1-G01: 全ケースで表示文字数 = セル数（AC-01）、欠落グリフ・暗黙代替 0 件（AC-02）。
- P1-G02: 両尺度の MAE・改善率・除外枚数・探索記録を測定して保存する（OI-004）。
  AC-03 の判定値は密度領域 MAE（evaluation-metrics.md 3.1）で、20% の合否は P2-G01 で課す。
- P1-G05: 工程別の所要時間を 2,000 / 5,000 セルで記録する。
"""

from __future__ import annotations

import argparse
import ctypes
import json
import statistics
import sys
import time
from ctypes import wintypes
from pathlib import Path

from dataset import IMAGES, TEXT
from pipeline import case_record, run_case

from optpoet.font import RenderSettings, build_charset, build_dictionary, load_font_profile
from optpoet.image import GridSpec
from optpoet.render import RenderStyle

OUT = Path(__file__).resolve().parent / "out"
FONT = Path(r"C:\Windows\Fonts\NotoSansJP-VF.ttf")

# 2,000 セル = 50×40、5,000 セル = 100×50（NFR-04 の基準寸法）。
GRIDS = {2000: GridSpec(columns=50, rows=40), 5000: GridSpec(columns=100, rows=50)}

SETTINGS = RenderSettings(pixel_size=48, cell_width=64, cell_height=64)
STYLE = RenderStyle()
AC03_THRESHOLD = 0.20


class _MemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def peak_working_set() -> int:
    """プロセスのピーク作業セット（バイト）。P0-015 と同じ「ピーク実メモリ」の代用。"""
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    psapi = ctypes.windll.psapi  # type: ignore[attr-defined]
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_MemoryCounters),
        wintypes.DWORD,
    ]
    counters = _MemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(
        kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
    ):
        return 0
    return int(counters.PeakWorkingSetSize)


def build_dict(levels: int = 8) -> tuple[object, object]:
    profile = load_font_profile(FONT)
    charset = build_charset()
    dictionary = build_dictionary(profile, charset, SETTINGS, levels=levels)
    return profile, dictionary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cells", type=int, nargs="+", default=[2000, 5000])
    parser.add_argument("--slots", nargs="+", default=None)
    args = parser.parse_args()

    assets = [a for a in IMAGES if args.slots is None or a.slot in args.slots]
    missing = [a.slot for a in assets if not a.path.is_file()]
    if missing:
        raise SystemExit(f"資産が未取得: {missing}（先に fetch_assets.py を実行する）")
    source = TEXT.path.read_text(encoding="utf-8")

    OUT.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    profile, dictionary = build_dict()
    dictionary_seconds = time.perf_counter() - started
    print(f"辞書構築 {dictionary_seconds:.1f}s / 文字 {len(dictionary.ratios):,}")  # type: ignore[attr-defined]
    print(
        f"  dictionary_id {dictionary.dictionary_id} / "  # type: ignore[attr-defined]
        f"ratio {dictionary.min_ratio:.4f}–{dictionary.max_ratio:.4f}"  # type: ignore[attr-defined]
    )

    runs: dict[str, object] = {}
    for cells in args.cells:
        grid = GRIDS[cells]
        records = []
        for index, asset in enumerate(assets, start=1):
            case = run_case(
                asset.slot,
                asset.path,
                source,
                grid,
                profile,  # type: ignore[arg-type]
                dictionary,  # type: ignore[arg-type]
                SETTINGS,
                STYLE,
            )
            record = case_record(case)
            records.append(record)
            density = record["density_metrics"]
            rate = density["improvement_rate"]
            print(
                f"  [{index:2d}/{len(assets)}] {asset.slot:<15} "
                f"密度 MAE {density['mae_draft']:.4f} → {density['mae_opt']:.4f} "
                f"({0.0 if rate is None else rate:+.2%}) {record['total_seconds']:.1f}s"
            )
            _save_outputs(case, cells)
        summary = _summarize(records, dictionary_seconds)
        summary["peak_working_set_mb"] = round(peak_working_set() / (1024 * 1024), 1)
        runs[str(cells)] = summary

    report = {
        "font": {"path": str(FONT), "family": profile.family, "hash": profile.hash},  # type: ignore[attr-defined]
        "render_settings": SETTINGS.to_dict(),
        # 密度領域 MAE の正規化条件（evaluation-metrics.md 3.1）。辞書が違う値を同列比較しない。
        "dictionary": {
            "id": dictionary.dictionary_id,  # type: ignore[attr-defined]
            "chars": len(dictionary.ratios),  # type: ignore[attr-defined]
            "min_ratio": dictionary.min_ratio,  # type: ignore[attr-defined]
            "max_ratio": dictionary.max_ratio,  # type: ignore[attr-defined]
        },
        "text": {"title": TEXT.title, "author": TEXT.author, "url": TEXT.url},
        "dictionary_seconds": round(dictionary_seconds, 3),
        "runs": runs,
    }
    name = "gate-" + "-".join(str(c) for c in args.cells) + ".json"
    (OUT / name).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return _verdict(runs)


def _save_outputs(case: object, cells: int) -> None:
    directory = OUT / f"cells-{cells}" / case.slot  # type: ignore[attr-defined]
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "artwork.png").write_bytes(case.optimized.png)  # type: ignore[attr-defined]
    (directory / "artwork.txt").write_bytes(case.optimized.txt)  # type: ignore[attr-defined]
    (directory / "draft.png").write_bytes(case.draft.png)  # type: ignore[attr-defined]
    case.target.save(directory / "target.png")  # type: ignore[attr-defined]


def _summarize(records: list[dict], dictionary_seconds: float) -> dict:
    density_rates = [
        r["density_metrics"]["improvement_rate"]
        for r in records
        if r["density_metrics"]["improvement_rate"] is not None
    ]
    pixel_rates = [
        r["metrics"]["improvement_rate"]
        for r in records
        if r["metrics"].get("improvement_rate") is not None
    ]
    stages: dict[str, list[float]] = {}
    for record in records:
        for name, value in record["timings"].items():
            stages.setdefault(name, []).append(value)
    return {
        "cases": records,
        "ac01_cell_match": all(
            r["cell_check"]["displayed_chars"] == r["grid"]["cells"]
            and r["cell_check"]["result"] == "ok"
            for r in records
        ),
        "ac02_missing_glyphs": sum(len(r["missing_glyphs"]) for r in records),
        # AC-03 の判定値は密度領域（evaluation-metrics.md 3.1 / OI-003）。
        "ac03_median_improvement": (
            round(statistics.median(density_rates), 4) if density_rates else None
        ),
        "ac03_excluded": len(records) - len(density_rates),
        "density_median_mae": {
            key: round(
                statistics.median([r["density_metrics"][f"mae_{key}"] for r in records]), 4
            )
            for key in ("draft", "opt", "baseline")
        },
        # 画素領域は補助指標（同 3.2）。合否には用いない。
        "pixel_median_improvement": (
            round(statistics.median(pixel_rates), 4) if pixel_rates else None
        ),
        "pixel_excluded": len(records) - len(pixel_rates),
        "pixel_median_mae": {
            key: round(statistics.median([r["metrics"][f"mae_{key}"] for r in records]), 4)
            for key in ("draft", "opt")
        },
        "traced_cases": sum(1 for r in records if r["optimization"]["trace_entries"] > 0),
        "stage_median_seconds": {
            name: round(statistics.median(values), 3) for name, values in stages.items()
        },
        "total_median_seconds": round(
            statistics.median([r["total_seconds"] for r in records]), 3
        ),
        "dictionary_seconds": round(dictionary_seconds, 3),
    }


def _verdict(runs: dict) -> int:
    failed = False
    for cells, run in runs.items():
        median = run["ac03_median_improvement"]
        pixel = run["pixel_median_improvement"]
        ok01 = run["ac01_cell_match"]
        ok02 = run["ac02_missing_glyphs"] == 0
        # P1-G02 は測定・記録できることが条件（OI-004）。20% の合否は P2-G01 で課す。
        recorded = (
            median is not None
            and pixel is not None
            and run["traced_cases"] == len(run["cases"])
        )
        reaches = median is not None and median >= AC03_THRESHOLD
        failed = failed or not (ok01 and ok02 and recorded)
        print(
            f"[{cells} セル] AC-01 {_mark(ok01)} / AC-02 {_mark(ok02)} / "
            f"P1-G02 {_mark(recorded)}"
        )
        print(f"  改善率中央値 密度領域(判定) {median:.2%} / 画素領域(補助) {pixel:.2%}")
        print(f"  AC-03 20% 到達: {'到達' if reaches else '未到達'}（判定は P2-G01）")
        print(f"  密度 MAE 中央値 {run['density_median_mae']}")
        print(f"  画素 MAE 中央値 {run['pixel_median_mae']}")
        print(f"  除外枚数 密度 {run['ac03_excluded']} / 画素 {run['pixel_excluded']}")
        print(f"  工程別中央値 {run['stage_median_seconds']}")
        print(f"  ピーク作業セット {run['peak_working_set_mb']} MB")
    return 1 if failed else 0


def _mark(ok: bool) -> str:
    return "合格" if ok else "不合格"


if __name__ == "__main__":
    sys.exit(main())
