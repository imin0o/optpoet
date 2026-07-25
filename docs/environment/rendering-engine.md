# 描画エンジンの決定

**状態**: 決定（2026-07-25）
**目的**: 密度辞書の測定と最終出力の描画に用いる描画エンジンを 1 つに固定し、両者が同一フォントファイル・同一エンジン・同一版・同一設定で同じ画素を生成する（NFR-02）ための基準にする。
**対象タスク**: [P0-013](../roadmap/phase-0.md)
**関連**: [requirements.md](../requirements.md)（FR-08 / FR-12）、[quality-and-operations.md](../quality-and-operations.md)（NFR-02 / AC-02）、[architecture.md](../architecture.md)（Renderer / Font Profiler）、[python-and-libraries.md](python-and-libraries.md)、[font-and-license.md](font-and-license.md)、[P0-014](../roadmap/phase-0.md)（同一画素スパイク）

本書は「密度測定と最終描画に**どの描画エンジンを使うか**」を確定する正規決定記録である。密度辞書キー（[P1-023](../roadmap/phase-1.md)）と Renderer 実装（[P3-001](../roadmap/phase-3.md) 以降）は本書の決定を前提にする。同一画素の実測確認は [P0-014](../roadmap/phase-0.md) で行う。

## 決定要件（何を満たすエンジンか）

| 要件 | 根拠 | 判断への影響 |
| --- | --- | --- |
| 密度測定時と最終描画時で**同一画素**を再現できる | NFR-02 | 測定と描画で同一のコードパス・同一エンジンを共有できることが必須。別ラスタライザの併用は不可。 |
| 参照 PC の Python 3.14.3 / win_amd64 で動作する | [python-and-libraries.md](python-and-libraries.md) | cp314 wheel が実測済みのライブラリに限定する。 |
| 源ノ角ゴシック（OTF/TTF）を欠落グリフなく描画できる | [font-and-license.md](font-and-license.md)、AC-02 | 任意の TrueType/OpenType フォントを埋め込みで描画でき、CJK グリフを扱えること。 |
| 描画結果を NumPy 配列として黒画素率・評価へ直接渡せる | 概念（密度離散化）、NFR | 画像処理・評価スタック（NumPy / OpenCV / scikit-image）と同一配列表現で接続できること。 |
| アンチエイリアス・レイアウトを決定的に固定できる | NFR-02 | AA・ヒンティング・レイアウトが版と設定で再現可能であること。 |

## 決定

- **描画エンジン**: **Pillow（PIL）の `ImageDraw.text` + `ImageFont.truetype`（FreeType バックエンド）を、密度測定と最終描画の単一エンジンとする。**
- **共有コードパス**: 密度測定（セル 1 文字を描画 → NumPy で黒画素率算出）と最終描画（同一呼び出しでグリッドへ配置）は、**同一の描画関数**を通す。測定専用・描画専用の別実装を持たない。
- **固定する描画パラメータ**（フォントプロファイルへ保存 / [P1-020](../roadmap/phase-1.md) / [P1-023](../roadmap/phase-1.md)）:
  - フォントファイル・版・SHA-256（[font-and-license.md](font-and-license.md)）
  - ピクセルサイズ（`ImageFont.truetype(size=...)`）とセル寸法・余白・基準原点
  - 画像モード（グレースケール `L` を基準。密度は輝度から算出）
  - 背景色・描画色（既定は白背景・黒文字）
  - `layout_engine`（**`ImageFont.Layout.BASIC` に固定**。決定性を優先し、libraqm 依存を MVP では持ち込まない）
  - Pillow 版・FreeType 版（`PIL.features.version("freetype2")` を記録）
- **版固定**: Pillow 11.3.0（cp314 wheel 実測済み / [python-and-libraries.md](python-and-libraries.md)）を採用候補とし、確定版と FreeType 版を依存ロック時に本書「更新履歴」へ記録する。

## 根拠

- **同一プロセス・同一エンジンで画素一致を保証しやすい**: 測定と描画を Pillow の同一関数で行えば、AA・ヒンティング・ラスタライズが完全に一致し、NFR-02 の「同じ画素」を最小の追加検証で満たせる。別エンジン併用が生む画素差リスクを構造的に排除する。
- **参照 PC で実測済み**: Pillow 11.3.0 は Python 3.14.3 / win_amd64 で cp314 wheel が揃い `import` 成功済み（[python-and-libraries.md](python-and-libraries.md)）。追加の環境リスクがない。
- **任意 TrueType/OpenType フォントを埋め込み描画できる**: `ImageFont.truetype` は FreeType 経由で源ノ角ゴシック OTF/TTF を直接読み、CJK グリフを描画できる（[font-and-license.md](font-and-license.md) の基準フォントと整合）。
- **NumPy・評価スタックへ直結**: 描画結果は `numpy.asarray(img)` で即配列化でき、黒画素率算出・SSIM 等の視覚評価（OpenCV / scikit-image）へ同一表現で渡せる（architecture.md 技術構成案）。
- **決定性を固定できる**: `layout_engine=BASIC` とサイズ・モードを固定すれば、環境非依存で再現可能なラスタライズになる。

## 却下・保留した選択肢

| 案 | 却下/保留理由 |
| --- | --- |
| OpenCV `cv2.putText` | CJK フォントを直接扱えず（Hershey フォントのみ）、任意 TrueType の埋め込み描画に非対応。基準フォント描画に使えない。前処理・エッジ検出用途に留める。 |
| matplotlib テキスト描画 | AA・DPI・バックエンド差でラスタライズが変動しやすく、決定的な画素固定が不透明。依存も重い。却下。 |
| HarfBuzz + FreeType 直接／libraqm（RAQM レイアウト） | 複雑テキスト整形（合字・BiDi）に強いが MVP には過剰で、追加ネイティブ依存を持ち込む。将来のカーニング・縦組み検討時の**保留候補**とし、MVP は BASIC 固定。 |
| SVG 生成 → 外部ラスタライザ（cairosvg 等） | 測定と最終描画で別ラスタライザを経由すると画素が一致せず NFR-02 を満たしにくい。作品用 Web の SVG 出力は別工程として切り離す。 |
| ブラウザ / Canvas レンダリング | 別プロセス・別ラスタライザで、測定側（Pillow）と最終側の画素が一致しない。NFR-02 に反するため基準描画には使わない。 |

## MVP での運用

- **測定と描画の同一性**: 密度辞書生成時と最終レンダリング時で、同梱した同一フォントファイル・同一版・同一ハッシュ、および本書で固定した Pillow / FreeType 版・描画パラメータを使う（NFR-02）。パラメータはフォントプロファイルへ保存する（[P1-023](../roadmap/phase-1.md)）。
- **欠落グリフ**: 暗黙代替を行わず、FreeType がグリフを持たない文字は不足として作者へ示し描画を停止する（FR-08 / AC-02 / architecture.md「暗黙処理を避ける」）。
- **来歴記録**: レンダリング設定（フォント / サイズ / エンジン版 / layout_engine / モード）を render metadata と manifest に保存する（architecture.md データ構造の方針）。

## 未確定・次工程へ委譲

- **採用版の確定**: Pillow・FreeType の具体版は依存ロック時に固定し、本書「更新履歴」に記録する。
- **同一画素の実測**: 密度辞書と最終 PNG で同一文字が同一画素になることは [P0-014](../roadmap/phase-0.md) のスパイクで確認する。
- **メモリ使用量**: 2,000 / 5,000 セル描画時の画像処理・描画メモリは [P0-015](../roadmap/phase-0.md) で実測済み（5,000 セルで総 RSS 約 76 MB、参照 PC 内で成立）。→ [memory-usage.md](memory-usage.md)
- **RAQM レイアウトの要否**: 縦書き・ルビ・複雑合字が要件化した場合に libraqm 併用を再評価する（MVP 対象外）。

## 更新履歴

| 日付 | 変更点 |
| --- | --- |
| 2026-07-25 | 初版。描画エンジンを Pillow（ImageDraw + ImageFont / FreeType, `layout_engine=BASIC`）に決定。測定と描画で同一コードパス・同一設定を共有し NFR-02 を満たす方針を確定。採用版は依存ロック時に固定。 |
