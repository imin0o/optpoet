# 自動評価指標の計算仕様（MAE・SSIM・エッジ一致率）

**状態**: P0-034 作成完了  
**目的**: [quality-and-operations.md](../quality-and-operations.md) 7章の自動受入条件（AC-03 密度 MAE、84 行の SSIM・エッジ一致率・重要領域誤差）を、第三者が同一手順・同一数値で再現できる計算仕様に固定する。  
**関連**: [quality-and-operations.md](../quality-and-operations.md) 7章、[architecture.md](../architecture.md)（第1段階 密度離散化）、[validation-dataset.md](validation-dataset.md)、[human-evaluation.md](human-evaluation.md)、[python-and-libraries.md](python-and-libraries.md)

本書は密度 MAE・SSIM・エッジ一致率の入力・座標系・前処理・式・集計・合格判定を一意に定める。
数値だけで作品価値を断定しない前提（[quality-and-operations.md](../quality-and-operations.md) 84 行）は本書でも保持し、
本指標は人間評価（[human-evaluation.md](human-evaluation.md)）と対で用いる。[NFR-01](../quality-and-operations.md) の
決定性を満たすため、全パラメータを固定し、乱数・環境依存の既定値を持たない。

## 1. 用語と比較対象

- **目標画像**: 検証データセットの原本（[validation-dataset.md](validation-dataset.md) 4.1）。
- **生成結果 PNG**: 文章をグリッドへ配置し基準フォントでレンダリングした最終 PNG（[architecture.md](../architecture.md) 第6段階）。
- **草稿配置**: 第2段階の草稿をそのまま配置した状態（最適化前）。
- **最適化後**: 第4・第5段階の組み合わせ探索・局所修正を経た状態。
- 指標は 3 領域で測る。**密度領域**（セルグリッド上）で MAE、**画素領域**（共通解像度の画像上）で SSIM とエッジ一致率。

## 2. 共通前処理

すべての指標で同一の前処理を用い、実装間・実行間で結果を一致させる。

- **グレースケール化**: sRGB を線形化せず、輝度 `Y = 0.2126R + 0.7152G + 0.0722B`（Rec.709 係数）を
  各チャンネル 0–255 から算出し、`0.0–1.0` へ正規化する（[validation-dataset.md](validation-dataset.md) 6章と同係数）。
- **密度の向き**: 密度 `d = 1 − Y`。白（明）= 密度 0、黒（濃）= 密度 1。[architecture.md](../architecture.md)
  第1段階の「濃いほど高密度」に一致させる。
- **アルファ**: 生成結果 PNG に透過があれば白 (`Y=1.0`) で合成してから輝度化する。
- **リサイズ**: 縮小は面積平均（OpenCV `INTER_AREA`）、拡大は Lanczos（`INTER_LANCZOS4`）で行い、手法を混在させない。

## 3. 密度 MAE（AC-03）

セルグリッド（列 × 行 = 出力の文字グリッド）を共通座標系とする。グリッド寸法は当該作品の設定に従う。

- **目標密度 `D_target[c]`**: 目標画像を各セル矩形へ面積平均で縮約し、2章の `d = 1 − Y` を取る（連続値 0–1）。
  [architecture.md](../architecture.md) 第1段階の 8 段階離散化は探索の目的関数側で用い、**MAE は離散化前の連続密度**で測る
  （量子化誤差を評価へ持ち込まないため）。
- **達成密度 `D_achieved[c]`**: 生成結果 PNG の同一セル矩形を面積平均で縮約し `d = 1 − Y` を取る。
  実レンダリング結果（フォント形状・字形）を反映した実測値とする。
- **セル MAE**:

  ```
  MAE = (1 / N) * Σ_c | D_target[c] − D_achieved[c] |      （N = 総セル数）
  ```

- **AC-03 判定（視覚改善）**: 各画像で草稿配置と最適化後の MAE を測り、改善率を

  ```
  改善率 = (MAE_draft − MAE_opt) / MAE_draft
  ```

  で求める。合格は **12 枚全体の改善率の中央値が 0.20（20%）以上**。`MAE_draft = 0` の画像は改善率を定義せず母集団から除外し、
  除外枚数を記録する。

## 4. SSIM

構造的類似度は画素領域で測る（scikit-image `structural_similarity`）。

- **比較解像度**: 生成結果 PNG の画素寸法を基準とし、目標画像を 2章のリサイズ規則で同寸法へ揃える。
- **入力**: 2章のグレースケール（0–1）。`data_range = 1.0`。
- **窓**: `gaussian_weights=True`、`sigma=1.5`、`use_sample_covariance=False`（Wang ら 2004 の既定）。窓が画像に収まらない場合はエラーとし黙って縮めない。
- **値域**: `−1.0 – 1.0`。報告は小数第 3 位まで。値が高いほど構造が近い。
- MVP では SSIM は補助指標とし固定閾値の合否には用いない（[quality-and-operations.md](../quality-and-operations.md) 84 行）。
  草稿配置と最適化後の双方を記録し、劣化がないことの確認に使う。

## 5. エッジ一致率

エッジの重なりを Dice 係数で測る（OpenCV）。

- **前処理**: 4章と同一の共通解像度・グレースケール（0–1）を `uint8` 0–255 へ戻し、ガウシアンぼかし
  `GaussianBlur(ksize=(5,5), sigmaX=1.0)` を掛ける。
- **エッジ抽出**: `Canny(threshold1=100, threshold2=200, apertureSize=3, L2gradient=True)` で二値エッジを得る。
  目標画像から `E_target`、生成結果 PNG から `E_achieved`。
- **一致率（Dice）**:

  ```
  エッジ一致率 = 2 * |E_target ∩ E_achieved| / (|E_target| + |E_achieved|)
  ```

  分母が 0（双方エッジ無し）の場合は 1.0 と定義する。値域 `0.0–1.0`、高いほど輪郭が近い。
- MVP では補助指標とし固定閾値の合否には用いない。輪郭崩れ（[architecture.md](../architecture.md) 121 行）の追跡に使う。

## 6. 重要領域誤差（補助）

[quality-and-operations.md](../quality-and-operations.md) 84 行の「重要領域の誤差」は、作者が指定した領域
（[NFR-03](../quality-and-operations.md) の編集で固定した矩形・重み領域）に限定した密度 MAE として測る。

- 指定が無い作品では算出せず「該当なし」と記録する。恣意的な自動領域抽出は MVP では行わない。
- 指定がある場合、3章の MAE を当該セル集合に限定して計算し、全体 MAE と併記する。

## 7. 集計と記録

- 記録単位は (画像 slot, モード, プロンプト/モデル/フォント/設定/シード) の 1 組。
- 各作品で `MAE_draft` / `MAE_opt` / 改善率 / SSIM / エッジ一致率 / 重要領域 MAE を記録する。
- データセット全体の集計は改善率の中央値（3章）で AC-03 を判定する。他指標は中央値と分布を併記し単一値で断定しない。
- 使用ライブラリの版（OpenCV / scikit-image / NumPy、[python-and-libraries.md](python-and-libraries.md)）を記録し、
  版差で数値が動く指標（SSIM・Canny）の再現条件を残す。

```md
## 指標記録（作品ID: <slot>-<mode>-<連番>）

- グリッド寸法: <列>×<行>  / 比較解像度: <W>×<H>px
- MAE_draft: <..>  MAE_opt: <..>  改善率: <..>
- SSIM(opt): <..>  エッジ一致率(opt): <..>
- 重要領域MAE: <.. / 該当なし>
- ライブラリ版: OpenCV <..> / scikit-image <..> / NumPy <..>
```

## 8. 次工程

- **P0-035**: AC-01〜AC-07 の受入記録テンプレートへ、本書の AC-03 判定（3章）と補助指標（4〜6章）を引用する。
- 実運用は Phase 2 以降の受入判定で用い、人間評価（[human-evaluation.md](human-evaluation.md)）と対にして可否を判断する。
