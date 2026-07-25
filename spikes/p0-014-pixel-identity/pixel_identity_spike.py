"""P0-014 スパイク: 同一文字が密度辞書と最終 PNG で同一画素になることの検証.

目的:
  NFR-02（描画一貫性）の中核主張「密度測定時と最終描画時で同じ文字が同じ画素を生む」を、
  P0-013 で決定した描画エンジン（Pillow ImageDraw + ImageFont / FreeType,
  layout_engine=BASIC）で実測確認する。

検証項目:
  T1 共有コードパス: 単一の render_cell() を通せば、測定用の単独描画と、
     グリッドへ配置した最終描画から切り出した同一セルが、バイト単位で一致する。
  T2 決定性（プロセス内・再ロード）: フォントを毎回読み直しても同一文字の
     セル画素は一致する。
  T3 決定性（プロセス間）: 別プロセスで再描画したセルの SHA-256 が一致する
     （--emit-hashes モードで自プロセスのハッシュのみ出力し、親が比較する）。
  T4 グリフ差の可視化: 密度の異なる文字は当然異なる画素になる（測定が
     意味を持つことの健全性確認）。

使い方:
  python pixel_identity_spike.py            # 全検証を実行し PASS/FAIL を表示
  python pixel_identity_spike.py --emit-hashes  # セル SHA-256 を JSON で出力（T3 用）

前提:
  参照 PC の CJK フォント C:\\Windows\\Fonts\\NotoSansJP-VF.ttf（源ノ角ゴシック相当）を
  使用する。本スパイクは「描画方式が同一画素を保証するか」を確認するもので、
  基準フォントの版・ハッシュ固定は P1-020 で別途行う。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from PIL import features as pil_features

# --- 固定描画パラメータ（P0-013 rendering-engine.md で確定した項目） ---
FONT_PATH = r"C:\Windows\Fonts\NotoSansJP-VF.ttf"  # 源ノ角ゴシック相当（スパイク用）
PIXEL_SIZE = 48          # ImageFont.truetype(size=...)
CELL_W, CELL_H = 64, 64  # セル寸法
IMAGE_MODE = "L"         # グレースケール（密度は輝度から算出）
BG_COLOR = 255           # 白背景
FG_COLOR = 0             # 黒文字
LAYOUT = ImageFont.Layout.BASIC  # 決定性優先・libraqm 非依存

SAMPLE_CHARS = ["白", "薄", "光", "密", "闇", "鬱", "永", "の"]


def load_font() -> ImageFont.FreeTypeFont:
    """固定パラメータでフォントを読み込む（測定・描画で共有する唯一の入口）."""
    return ImageFont.truetype(FONT_PATH, PIXEL_SIZE, layout_engine=LAYOUT)


def render_cell(char: str, font: ImageFont.FreeTypeFont) -> np.ndarray:
    """1 セル（1 文字）を描画して NumPy 配列で返す共有コードパス.

    測定用も最終描画用もこの関数だけを通す。セル内の原点は固定で、
    グリフはセル中央に配置する（anchor="mm"）。
    """
    img = Image.new(IMAGE_MODE, (CELL_W, CELL_H), BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw.text((CELL_W / 2, CELL_H / 2), char, font=font, fill=FG_COLOR, anchor="mm")
    return np.asarray(img)


def black_ratio(cell: np.ndarray) -> float:
    """密度辞書が使う黒画素率（0=白, 1=真っ黒）。輝度から算出."""
    return float((255 - cell.astype(np.float64)).mean() / 255.0)


def cell_hash(cell: np.ndarray) -> str:
    return hashlib.sha256(cell.tobytes()).hexdigest()


def build_final_grid(chars: list[str], font: ImageFont.FreeTypeFont, cols: int = 4):
    """最終描画を模したグリッド画像を作り、各セルを共有関数で貼り込む.

    返り値: (グリッド画像, セル位置 [(x0, y0), ...])
    """
    rows = (len(chars) + cols - 1) // cols
    grid = Image.new(IMAGE_MODE, (CELL_W * cols, CELL_H * rows), BG_COLOR)
    positions = []
    for i, ch in enumerate(chars):
        cx, cy = (i % cols) * CELL_W, (i // cols) * CELL_H
        cell_img = Image.fromarray(render_cell(ch, font))  # 測定と同一の render_cell
        grid.paste(cell_img, (cx, cy))
        positions.append((cx, cy))
    return grid, positions


def crop_cell(grid: Image.Image, pos: tuple[int, int]) -> np.ndarray:
    x0, y0 = pos
    return np.asarray(grid.crop((x0, y0, x0 + CELL_W, y0 + CELL_H)))


def emit_hashes() -> None:
    """T3 用: このプロセスで描いた各文字セルの SHA-256 を JSON 出力."""
    font = load_font()
    out = {ch: cell_hash(render_cell(ch, font)) for ch in SAMPLE_CHARS}
    print(json.dumps(out))


def run_checks(out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []

    print("=== P0-014 pixel-identity spike ===")
    print(f"Python  : {sys.version.split()[0]}")
    print(f"Pillow  : {Image.__version__}")
    print(f"freetype: {pil_features.version('freetype2')}")
    print(f"font    : {FONT_PATH}")
    print(f"params  : size={PIXEL_SIZE} cell={CELL_W}x{CELL_H} mode={IMAGE_MODE} "
          f"layout={LAYOUT.name}")
    print()

    # --- T1: 測定セル == 最終グリッドから切り出したセル（バイト一致） ---
    font = load_font()
    grid, positions = build_final_grid(SAMPLE_CHARS, font)
    grid.save(out_dir / "final_grid.png")
    print("T1 共有コードパス（測定セル vs 最終グリッド切り出し）:")
    for ch, pos in zip(SAMPLE_CHARS, positions):
        measured = render_cell(ch, font)        # 密度辞書側
        final = crop_cell(grid, pos)            # 最終 PNG 側
        same = np.array_equal(measured, final)
        br = black_ratio(measured)
        h = cell_hash(measured)
        status = "OK " if same else "NG "
        print(f"  {status}'{ch}' black={br:6.4f} sha256={h[:16]} equal={same}")
        if not same:
            failures.append(f"T1 '{ch}' measured!=final")
    print()

    # --- T2: フォント再ロードでも同一（プロセス内決定性） ---
    print("T2 決定性（フォント再ロード）:")
    font_a, font_b = load_font(), load_font()
    for ch in SAMPLE_CHARS:
        same = np.array_equal(render_cell(ch, font_a), render_cell(ch, font_b))
        if not same:
            failures.append(f"T2 '{ch}' reload mismatch")
    print(f"  {'OK ' if not any(f.startswith('T2') for f in failures) else 'NG '}"
          f"全 {len(SAMPLE_CHARS)} 文字が再ロードで一致")
    print()

    # --- T3: 別プロセスの SHA-256 と一致（プロセス間決定性） ---
    print("T3 決定性（別プロセス）:")
    this_hashes = {ch: cell_hash(render_cell(ch, font)) for ch in SAMPLE_CHARS}
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--emit-hashes"],
        capture_output=True, text=True, check=True,
    )
    other_hashes = json.loads(proc.stdout.strip())
    for ch in SAMPLE_CHARS:
        if this_hashes[ch] != other_hashes.get(ch):
            failures.append(f"T3 '{ch}' cross-process mismatch")
    print(f"  {'OK ' if not any(f.startswith('T3') for f in failures) else 'NG '}"
          f"全 {len(SAMPLE_CHARS)} 文字が別プロセスと SHA-256 一致")
    print()

    # --- T4: 密度差の健全性（異なる文字は異なる画素） ---
    print("T4 グリフ差の健全性（濃淡順・重複ハッシュ無し）:")
    ratios = [(ch, black_ratio(render_cell(ch, font))) for ch in SAMPLE_CHARS]
    hashes = {ch: cell_hash(render_cell(ch, font)) for ch in SAMPLE_CHARS}
    if len(set(hashes.values())) != len(SAMPLE_CHARS):
        failures.append("T4 duplicate glyph bitmaps")
    for ch, br in sorted(ratios, key=lambda x: x[1]):
        print(f"  '{ch}' black={br:6.4f}")
    print()

    # --- サンプル保存 ---
    for ch in ("白", "鬱"):
        Image.fromarray(render_cell(ch, font)).save(out_dir / f"cell_{ord(ch):05x}.png")

    print("=== RESULT ===")
    if failures:
        print(f"FAIL ({len(failures)} 件):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS: 測定と最終描画は同一コードパスでバイト一致、"
          "プロセス内外で決定的。NFR-02 の同一画素前提を満たす。")
    print(f"成果物: {out_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit-hashes", action="store_true",
                        help="T3 用: セル SHA-256 を JSON 出力して終了")
    parser.add_argument("--out", default=str(Path(__file__).parent / "out"),
                        help="成果物出力先")
    args = parser.parse_args()
    if args.emit_hashes:
        emit_hashes()
        return 0
    return run_checks(Path(args.out))


if __name__ == "__main__":
    raise SystemExit(main())
