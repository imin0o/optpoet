# 同一画素スパイク（密度辞書 = 最終 PNG）

**状態**: 検証済み（2026-07-25 実測）
**目的**: 同じ文字が密度辞書の測定時と最終 PNG の描画時で**同じ画素**になることを、参照 PC 上で実測し、描画一貫性（NFR-02）の実装可能性を確定する。
**対象タスク**: [P0-014](../roadmap/phase-0.md)
**関連**: [rendering-engine.md](rendering-engine.md)（P0-013 の描画エンジン決定）、[font-and-license.md](font-and-license.md)、[python-and-libraries.md](python-and-libraries.md)、[requirements.md](../requirements.md)（FR-08 / FR-12）、[quality-and-operations.md](../quality-and-operations.md)（NFR-02 / AC-02）、[P0-G02](../roadmap/phase-0.md)（完了ゲート）

本書は [P0-013](rendering-engine.md) で決定した描画エンジン（Pillow `ImageDraw` + `ImageFont` / FreeType, `layout_engine=BASIC`）が、NFR-02 の「密度測定と最終出力で同じ画素」を実際に満たすかを、実行スパイクで確認した検証記録である。スパイクのコードと成果物は [`spikes/p0-014-pixel-identity/`](../../spikes/p0-014-pixel-identity/) に置く。

## 検証環境

| 項目 | 値 | 出典 |
| --- | --- | --- |
| Python | 3.14.3 / win_amd64 | [reference-pc.md](reference-pc.md) / [python-and-libraries.md](python-and-libraries.md) |
| Pillow | 11.3.0 | [python-and-libraries.md](python-and-libraries.md) |
| FreeType | 2.13.3（`PIL.features.version("freetype2")`） | 本スパイク実測 |
| フォント | `C:\Windows\Fonts\NotoSansJP-VF.ttf`（源ノ角ゴシック相当） | スパイク用。基準フォントの版・ハッシュ固定は [P1-020](../roadmap/phase-1.md) |
| 描画パラメータ | size=48 / cell=64x64 / mode=`L` / layout=`BASIC` | [rendering-engine.md](rendering-engine.md) |

> フォントは検証の便宜上 OS 同梱の Noto Sans JP（源ノ角ゴシックと同系）を用いた。本スパイクは「**描画方式が同一画素を保証するか**」の確認であり、基準フォントファイルの同梱・版固定・ハッシュ記録は [P1-020](../roadmap/phase-1.md) で別途行う。

## 検証方法

密度測定と最終描画を**単一の共有関数** `render_cell(char, font)` に通し、両経路の画素を突き合わせる。

| ID | 検証内容 | 判定基準 |
| --- | --- | --- |
| T1 | 共有コードパス: 測定用の単独セル描画と、グリッドへ配置した最終描画から切り出した同一セルを比較 | `numpy.array_equal` がバイト一致 |
| T2 | プロセス内決定性: フォントを毎回読み直しても同一文字のセルが一致 | 再ロード間で一致 |
| T3 | プロセス間決定性: 別プロセスで再描画したセルの SHA-256 が一致 | ハッシュ一致 |
| T4 | 健全性: 密度の異なる文字は異なる画素・異なるハッシュになる（測定が意味を持つ） | 重複ビットマップ無し・黒画素率が単調に分離 |

検証文字: `白 薄 光 密 闇 鬱 永 の`（薄い〜濃いを含む 8 文字）。

## 結果（実測: 2026-07-25）

**総合: PASS。** 測定と最終描画は同一コードパスでバイト一致し、プロセス内・プロセス間で決定的。

- **T1**: 8 文字すべてで測定セル == 最終グリッド切り出しセル（`equal=True`）。各セルの SHA-256 が一致。
- **T2**: フォント再ロード後も 8 文字すべて一致。
- **T3**: 別プロセスで再描画した 8 文字の SHA-256 がすべて一致。
- **T4**: 8 文字のビットマップハッシュはすべて相異なり、黒画素率は濃淡順に分離。

黒画素率（`(255 - 輝度).mean() / 255`）の実測、薄い順:

| 文字 | 黒画素率 |
| --- | --- |
| の | 0.0443 |
| 永 | 0.0560 |
| 白 | 0.0568 |
| 光 | 0.0587 |
| 密 | 0.0814 |
| 薄 | 0.1027 |
| 闇 | 0.1181 |
| 鬱 | 0.1249 |

成果物: `spikes/p0-014-pixel-identity/out/`（`final_grid.png`、セル PNG サンプル）。

## 結論

- P0-013 の描画方式（Pillow / FreeType, `layout_engine=BASIC`, 固定パラメータ）で、**密度辞書と最終 PNG の同一画素は成立する**。NFR-02 の前提が実装可能であることを確認した。
- 同一性の鍵は**測定と描画で `render_cell()` を共有すること**。別描画関数・別ラスタライザを持たない設計（[rendering-engine.md](rendering-engine.md) の「共有コードパス」）が要件である。
- 密度辞書のキーには、フォントファイル・版・ハッシュに加え、本スパイクで固定した描画パラメータ（size / cell / mode / layout）を含める（[P1-023](../roadmap/phase-1.md)）。

これにより完了ゲート [P0-G02](../roadmap/phase-0.md)（基準フォントと描画エンジンの実測整合）の技術的裏付けが得られた。ゲート自体のクローズは基準フォントファイル確定（[P1-020](../roadmap/phase-1.md)）後に行う。

## 未確定・次工程へ委譲

- **基準フォントでの再実測**: 本スパイクは Noto Sans JP-VF で実施。同梱する基準フォントファイル確定後（[P1-020](../roadmap/phase-1.md)）に同一手順で再確認する。
- **メモリ使用量**: 2,000 / 5,000 セル描画時の実測は [P0-015](../roadmap/phase-0.md) で完了。→ [memory-usage.md](memory-usage.md)
- **欠落グリフ検出**: 暗黙代替 0 件（AC-02）の実装・検証は Font Profiler（[P1-020](../roadmap/phase-1.md) 以降）。
- **可変フォントの軸固定**: VF を採用する場合はウェイト軸（`wght`）の固定値を版と併せて記録する（[P1-020](../roadmap/phase-1.md) / [P1-023](../roadmap/phase-1.md)）。

## 更新履歴

| 日付 | 変更点 |
| --- | --- |
| 2026-07-25 | 初版。Python 3.14.3 / Pillow 11.3.0 / FreeType 2.13.3 で同一画素スパイクを実施し PASS。測定と最終描画が共有コードパスでバイト一致・プロセス内外で決定的であることを実測確認。 |
