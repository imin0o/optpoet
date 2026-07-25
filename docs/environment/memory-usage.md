# メモリ使用量スパイク（2,000 / 5,000 セル）

**状態**: 検証済み（2026-07-25 実測）
**目的**: 作品 1 枚の生成規模（2,000 / 5,000 セル）で、密度測定と最終描画（P0-013 で決定した Pillow / FreeType）にかかる画像処理・描画メモリを参照 PC 上で実測し、参照 PC のリソース内で生成が成立することを確認する。
**対象タスク**: [P0-015](../roadmap/phase-0.md)
**関連**: [rendering-engine.md](rendering-engine.md)（P0-013 の描画エンジン決定）、[pixel-identity-spike.md](pixel-identity-spike.md)（P0-014 の同一画素スパイク）、[reference-pc.md](reference-pc.md)、[python-and-libraries.md](python-and-libraries.md)、[requirements.md](../requirements.md)、[quality-and-operations.md](../quality-and-operations.md)（NFR）

本書は [P0-013](rendering-engine.md) の描画方式を 2,000 / 5,000 セル規模で走らせたときのメモリを実測した記録である。スパイクのコードと成果物は [`spikes/p0-015-memory/`](../../spikes/p0-015-memory/) に置く。

## 検証環境

| 項目 | 値 | 出典 |
| --- | --- | --- |
| Python | 3.14.3 / win_amd64 | [reference-pc.md](reference-pc.md) / [python-and-libraries.md](python-and-libraries.md) |
| Pillow | 11.3.0 | [python-and-libraries.md](python-and-libraries.md) |
| FreeType | 2.13.3（`PIL.features.version("freetype2")`） | 本スパイク実測 |
| NumPy / psutil | 2.4.2 / 7.2.2 | 本スパイク実測 |
| フォント | `C:\Windows\Fonts\NotoSansJP-VF.ttf`（源ノ角ゴシック相当） | スパイク用。基準フォントは [P1-020](../roadmap/phase-1.md) |
| 描画パラメータ | size=48 / cell=64x64 / mode=`L` / layout=`BASIC` | [rendering-engine.md](rendering-engine.md) |

## 測定方法

作品 1 枚を生成する主要メモリ経路を 2 フェーズに分け、共有関数 `render_cell(char, font)`（[P0-014](pixel-identity-spike.md) と同一方式）を通して測定する。

| ID | 測定内容 |
| --- | --- |
| R1 描画 | N セルのグリッドを共有 `render_cell()` で組み立て、最終 PNG を保存 |
| R2 画像処理 | 最終グリッドを NumPy 配列化し、セル単位の黒画素率（密度）をブロック平均で算出 |

計測は 2 系統を併記する。

- **tracemalloc（py）**: Python 側アロケーションのピーク。PIL の C 側確保は含みにくい。
- **psutil RSS（RSS）**: 背景スレッドで実 RSS を poll したフェーズ別ピークと常駐 RSS の差。PIL / FreeType / NumPy の C 確保を含む実測値。

N セルは概ね正方（`cols = ceil(sqrt(N))`）に並べる。密度の異なる文字を巡回させ、単色ビットマップ再利用に依存しない負荷にする。

## 結果（実測: 2026-07-25）

**総合: 参照 PC のリソース内で成立。** 5,000 セルでも追加 RSS は約 40 MB、プロセス総 RSS は約 76 MB に収まる。

常駐 RSS（プロセスベース）: **35.5 MB**

| セル数 | グリッド | 画素 | PNG配列(MB) | 描画 py(MB) | 描画 RSS差(MB) | 処理 py(MB) | 処理 RSS差(MB) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2,000 | 45x45 | 2880x2880 | 7.91 | 1.13 | 12.18 | 15.84 | 19.29 |
| 5,000 | 71x71 | 4544x4544 | 19.69 | 0.26 | 21.11 | 39.43 | 40.56 |

- **PNG配列**: `mode=L` の最終グリッド 1 枚分の実配列サイズ（画素数 = バイト数）。セル数にほぼ線形（2,000→7.91 MB、5,000→19.69 MB）。
- **描画（R1）**: RSS ピーク差は 5,000 セルで約 21 MB。セル画像は 1 枚ずつ生成して貼り込むため、`render_cell` の一時確保は 1 セル分に留まり、支配的なのは最終グリッド 1 枚。
- **画像処理（R2）**: RSS ピーク差は 5,000 セルで約 41 MB。配列化と密度算出時に元配列に加え平均計算用の一時領域が乗り、ピークは概ねグリッド配列の約 2 倍。
- **最大値**: 全フェーズ通じた追加 RSS は 5,000 セルで約 41 MB。常駐 35.5 MB と合わせて総 **約 76 MB**。

## 結論

- P0-013 の描画方式で 2,000 / 5,000 セルを生成しても、メモリは常駐込みで約 76 MB（5,000 セル）に収まり、参照 PC（[reference-pc.md](reference-pc.md)）のリソースに対し十分な余裕がある。
- メモリはセル数に対しほぼ線形で増える。支配項は「最終グリッド 1 枚の `mode=L` 配列」とその画像処理時の一時領域（約 2 倍）であり、セル単位の描画は一時確保を 1 セル分に抑えられる。
- セル数を大きく超える将来要件が出た場合の指標: 追加 RSS ≒ グリッド画素数 × 約 2（画像処理ピーク）+ 数 MB。10,000 セル相当でも 100 MB 台に収まる見込み。

## 未確定・次工程へ委譲

- **基準フォントでの再実測**: 本スパイクは Noto Sans JP-VF。基準フォントファイル確定後（[P1-020](../roadmap/phase-1.md)）に同一手順で再確認する。グリフ形状は RSS にほぼ影響しない（配列サイズは同一）。
- **入力写真の解析メモリ**: 本スパイクは描画・密度側を対象とする。入力画像の読み込み・リサイズ・エッジ検出（OpenCV / scikit-image）のメモリは解析パイプライン実装時（[Phase 2](../roadmap/phase-2.md) 以降）に実測する。
- **カラー/中間バッファ**: MVP は `mode=L`。カラー中間表現や複数バッファ併用が要件化した場合は係数を見直す。

## 更新履歴

| 日付 | 変更点 |
| --- | --- |
| 2026-07-25 | 初版。Python 3.14.3 / Pillow 11.3.0 / FreeType 2.13.3 で 2,000 / 5,000 セルのメモリを実測。5,000 セルで追加 RSS 約 41 MB・総 RSS 約 76 MB、参照 PC 内で成立を確認。 |
