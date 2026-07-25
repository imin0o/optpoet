"""P0-015 スパイク: 2,000 / 5,000 セルの画像処理・描画メモリ使用量を測定する.

目的:
  NFR（参照 PC のリソース内で作品を生成できること）の裏付けとして、密度測定と
  最終描画（P0-013 で決定した Pillow / FreeType, layout_engine=BASIC）を
  2,000 / 5,000 セル規模で実行したときの画像処理・描画メモリを実測する。

測定対象（作品 1 枚を生成する主要メモリ経路）:
  R1 描画: N セルのグリッドを共有 render_cell() で組み立て、最終 PNG を保存。
  R2 画像処理: 最終グリッドを NumPy 配列化し、セル単位の黒画素率（密度）を
     ブロック平均で算出する（密度辞書・評価が触る配列表現）。

計測方法:
  - tracemalloc: Python 側アロケーションのピーク（PIL の C 側確保は含みにくい）。
  - psutil RSS: プロセス実 RSS を背景スレッドで poll し、フェーズ別ピークを取る。
    PIL/FreeType/NumPy の C 確保を含む実測値。両者を併記する。

使い方:
  python memory_spike.py                 # 2000, 5000 を測定し表を表示
  python memory_spike.py --cells 3000    # 任意セル数を追加測定
  python memory_spike.py --keep-png      # 生成 PNG を out/ に残す

前提:
  参照 PC の CJK フォント C:\\Windows\\Fonts\\NotoSansJP-VF.ttf（源ノ角ゴシック相当）。
  描画パラメータは P0-013 / P0-014 と同一（size=48 / cell=64x64 / mode=L / BASIC）。
"""
from __future__ import annotations

import argparse
import math
import threading
import time
import tracemalloc
from pathlib import Path

import numpy as np
import psutil
from PIL import Image, ImageDraw, ImageFont
from PIL import features as pil_features

# --- 固定描画パラメータ（P0-013 rendering-engine.md / P0-014 と同一） ---
FONT_PATH = r"C:\Windows\Fonts\NotoSansJP-VF.ttf"
PIXEL_SIZE = 48
CELL_W, CELL_H = 64, 64
IMAGE_MODE = "L"
BG_COLOR = 255
FG_COLOR = 0
LAYOUT = ImageFont.Layout.BASIC

# 密度の異なる文字を巡回させ、単色ビットマップの再利用に依存しない現実的な負荷にする
SAMPLE_CHARS = "白薄光密闇鬱永のあ書字画像点線面積階調"

MB = 1024 * 1024


def load_font() -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_PATH, PIXEL_SIZE, layout_engine=LAYOUT)


def render_cell(char: str, font: ImageFont.FreeTypeFont) -> np.ndarray:
    """1 セルを描画して NumPy 配列で返す共有コードパス（P0-014 と同一方式）."""
    img = Image.new(IMAGE_MODE, (CELL_W, CELL_H), BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw.text((CELL_W / 2, CELL_H / 2), char, font=font, fill=FG_COLOR, anchor="mm")
    return np.asarray(img)


def grid_shape(n_cells: int) -> tuple[int, int]:
    """N セルを概ね正方に並べる (cols, rows)."""
    cols = math.ceil(math.sqrt(n_cells))
    rows = math.ceil(n_cells / cols)
    return cols, rows


class RSSPeak:
    """背景スレッドで RSS を poll し、区間ピークを記録するサンプラ."""

    def __init__(self, proc: psutil.Process, interval: float = 0.005) -> None:
        self._proc = proc
        self._interval = interval
        self._peak = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _run(self) -> None:
        while not self._stop.is_set():
            rss = self._proc.memory_info().rss
            if rss > self._peak:
                self._peak = rss
            time.sleep(self._interval)

    def __enter__(self) -> "RSSPeak":
        self._peak = self._proc.memory_info().rss
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()

    @property
    def peak(self) -> int:
        return self._peak


def measure(n_cells: int, out_dir: Path, keep_png: bool) -> dict:
    cols, rows = grid_shape(n_cells)
    grid_w, grid_h = CELL_W * cols, CELL_H * rows
    font = load_font()
    proc = psutil.Process()

    rss_base = proc.memory_info().rss

    # --- R1 描画: N セルを共有関数でグリッドへ貼り込み最終 PNG を保存 ---
    tracemalloc.start()
    with RSSPeak(proc) as rss_render:
        grid = Image.new(IMAGE_MODE, (grid_w, grid_h), BG_COLOR)
        for i in range(n_cells):
            ch = SAMPLE_CHARS[i % len(SAMPLE_CHARS)]
            cx, cy = (i % cols) * CELL_W, (i // cols) * CELL_H
            grid.paste(Image.fromarray(render_cell(ch, font)), (cx, cy))
        png_path = out_dir / f"grid_{n_cells}.png"
        grid.save(png_path)
    render_py_peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()

    # --- R2 画像処理: 配列化 + セル単位の黒画素率（密度）をブロック平均で算出 ---
    tracemalloc.start()
    with RSSPeak(proc) as rss_proc:
        arr = np.asarray(grid)                                  # (grid_h, grid_w) uint8
        blocks = arr.reshape(rows, CELL_H, cols, CELL_W)        # セルブロックへ再配置
        density = (255.0 - blocks.mean(axis=(1, 3))) / 255.0    # (rows, cols) 黒画素率
        _ = float(density.mean())                               # 参照して最適化除去を防ぐ
    proc_py_peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()

    if not keep_png:
        png_path.unlink(missing_ok=True)

    return {
        "n_cells": n_cells,
        "grid": f"{cols}x{rows}",
        "px": f"{grid_w}x{grid_h}",
        "grid_bytes": grid_w * grid_h,          # mode=L の 1 枚分実配列
        "render_py_peak": render_py_peak,
        "render_rss_peak_delta": rss_render.peak - rss_base,
        "proc_py_peak": proc_py_peak,
        "proc_rss_peak_delta": rss_proc.peak - rss_base,
        "rss_base": rss_base,
    }


def run(cell_counts: list[int], out_dir: Path, keep_png: bool) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=== P0-015 memory spike ===")
    print(f"Pillow  : {Image.__version__}  freetype: {pil_features.version('freetype2')}")
    print(f"font    : {FONT_PATH}")
    print(f"params  : size={PIXEL_SIZE} cell={CELL_W}x{CELL_H} mode={IMAGE_MODE} "
          f"layout={LAYOUT.name}")
    print()

    results = [measure(n, out_dir, keep_png) for n in cell_counts]

    print(f"{'cells':>6} {'grid':>9} {'px':>11} {'PNG配列':>9} "
          f"{'描画py':>8} {'描画RSS':>9} {'処理py':>8} {'処理RSS':>9}")
    print(f"{'':>6} {'':>9} {'':>11} {'(MB)':>9} "
          f"{'(MB)':>8} {'(MB)':>9} {'(MB)':>8} {'(MB)':>9}")
    for r in results:
        print(f"{r['n_cells']:>6} {r['grid']:>9} {r['px']:>11} "
              f"{r['grid_bytes'] / MB:>9.2f} "
              f"{r['render_py_peak'] / MB:>8.2f} {r['render_rss_peak_delta'] / MB:>9.2f} "
              f"{r['proc_py_peak'] / MB:>8.2f} {r['proc_rss_peak_delta'] / MB:>9.2f}")
    print()
    print(f"RSS base(プロセス常駐): {results[0]['rss_base'] / MB:.1f} MB")
    print("py=tracemalloc(Python確保ピーク) / RSS=psutil実RSS区間ピーク差(C確保含む)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cells", type=int, action="append", default=None,
                        help="測定するセル数（複数可）。既定は 2000 と 5000。")
    parser.add_argument("--out", default=str(Path(__file__).parent / "out"),
                        help="PNG 出力先")
    parser.add_argument("--keep-png", action="store_true",
                        help="生成した PNG を残す（既定は削除）")
    args = parser.parse_args()
    cells = args.cells if args.cells else [2000, 5000]
    return run(cells, Path(args.out), args.keep_png)


if __name__ == "__main__":
    raise SystemExit(main())
