# project manifest（必須項目・スキーマ版規則）

**状態**: 定義済み（2026-07-25）。manifest の**論理構造**（必須ブロック・必須項目・不変条件・スキーマ版規則）を確定する。物理ファイル配置・内容ハッシュ・キャッシュキーは [P0-041](../roadmap/phase-0.md)、来歴の詳細形式は [P0-042](../roadmap/phase-0.md)、原子的保存・読取専用オープン・移行手順は [P0-044](../roadmap/phase-0.md) で確定する。
**目的**: FR-17 の「入力ハッシュ・前処理・密度辞書識別子・AI 入出力・モデル識別子・設定・シード・編集履歴・評価・出力をスキーマ版付きで保存し、再読込と結果の再生を可能にする」を、実装が参照できる項目単位まで固定する。AC-04（保存応答からの再生で TXT バイト一致・PNG 一致）と AC-05（保存・再読込後に設定・固定箇所・中間生成物・評価値が一致）を満たす最小十分集合を定める。
**対象タスク**: [P0-040](../roadmap/phase-0.md)
**関連**: [requirements.md](../requirements.md)（FR-01〜FR-18、特に FR-17）、[architecture.md](../architecture.md)（Project Store、内容ハッシュとスキーマ版の受け渡し）、[quality-and-operations.md](../quality-and-operations.md)（NFR-01 / NFR-06 / NFR-08、AC-04 / AC-05）、[ai-adapter-contract.md](ai-adapter-contract.md)（応答エンベロープ・`provenance`）、[ai-cost-budget.md](ai-cost-budget.md)（キャップ保存）、[font-and-license.md](../environment/font-and-license.md)、[rendering-engine.md](../environment/rendering-engine.md)、[evaluation-metrics.md](../environment/evaluation-metrics.md)、[open-issues.md](open-issues.md)

## 位置づけと原則

- manifest は**プロジェクトの正規情報源**であり、再読込・再生に必要な情報をすべて指すか含む。
- 大きな実体（画像・密度マップ・AI 応答原文・出力 PNG）は manifest に埋め込まず、**参照（ref）**で持つ。ref は「パス＋内容ハッシュ＋スキーマ版」を伴う（[architecture.md](../architecture.md)）。
- manifest 単体では作品を再構成できないが、**manifest が指す集合**は再構成に十分であること（欠落は読込時に検出可能であること）を不変条件とする。
- 秘密情報（API キー・トークン・資格情報）を manifest およびその参照先へ含めない（[P0-043](../roadmap/phase-0.md)、NFR-08）。
- 未確定領域は「後で追加できる任意ブロック」として空けるのではなく、**ブロックを予約し必須項目のみ確定**する。

## ref の共通形（参照の最小形）

manifest 中のすべての外部実体参照は次の形を取る。物理配置規則は [P0-041](../roadmap/phase-0.md)。

| フィールド | 必須 | 意味 |
| --- | --- | --- |
| `path` | 必須 | プロジェクトルートからの相対パス（絶対パス・端末固有パスを禁止） |
| `hash` | 必須 | 実体の内容ハッシュ（アルゴリズム識別子を含む） |
| `media_type` | 必須 | 実体の種別（画像・JSON・テキスト等） |
| `schema_version` | 条件付き必須 | 実体が構造化データの場合、その実体自身のスキーマ版 |
| `bytes` | 任意 | 実体サイズ（欠落・破損検出の補助） |

## 必須ブロックと必須項目

以下 12 ブロックを manifest のトップレベルに置く。**必須**は保存時に値が確定していなければならない項目、**条件付き必須**は当該工程が実行済みなら必須の項目を指す。

### 1. `manifest`（識別とバージョン）

| 項目 | 区分 | 意味 |
| --- | --- | --- |
| `schema_version` | 必須 | manifest 全体のスキーマ版（版付け規則は後述）。他実体の版とは独立軸 |
| `project_id` | 必須 | プロジェクトの一意識別子（再保存で変わらない） |
| `app_version` | 必須 | 生成したアプリ版 |
| `created_at` / `updated_at` | 必須 | 作成・最終更新時刻 |
| `title` | 任意 | 作者が付ける表示名 |

### 2. `input`（入力画像、FR-01）

| 項目 | 区分 | 意味 |
| --- | --- | --- |
| `source` | 必須 | 原本画像への ref（`hash` が FR-17 の入力ハッシュ） |
| `pixel_size` / `byte_size` | 必須 | 原本の画素数・バイト数（MVP 上限判定の記録） |
| `normalization` | 必須 | EXIF Orientation・ICC・透過の正規化結果（適用した変換の記録） |
| `normalized_ref` | 条件付き必須 | 正規化後画像の ref（生成済みなら必須） |

### 3. `preprocess`（非破壊前処理設定、FR-01）

| 項目 | 区分 | 意味 |
| --- | --- | --- |
| `crop` / `rotate` | 必須 | トリミング・回転（未適用は無変換値を明示。省略で暗黙既定を意味させない） |
| `brightness` / `contrast` / `gamma` / `invert` | 必須 | 階調調整値 |
| `result_ref` | 条件付き必須 | 前処理後画像の ref |

### 4. `grid`（グリッドと組版、FR-02 / FR-07 / FR-10）

| 項目 | 区分 | 意味 |
| --- | --- | --- |
| `cols` / `rows` | 必須 | 横・縦セル数（積が MVP 範囲 2,000〜5,000 か試験扱いかを判別可能にする） |
| `cell_aspect` | 必須 | セル縦横比 |
| `output_size` | 必須 | 出力画素サイズ |
| `font_size` / `line_spacing` / `char_spacing` | 必須 | フォントサイズ・行間・字間 |
| `reading_order` | 必須 | 読み順（MVP は横書き固定だが、将来拡張を識別できるよう明示保存） |
| `normalization_form` | 必須 | 文字正規化形式（FR-10、MVP は NFC） |

### 5. `fonts`（フォント割当と密度辞書、FR-04 / FR-11 / NFR-02）

| 項目 | 区分 | 意味 |
| --- | --- | --- |
| `assignments` | 必須 | 文字種→フォントの割当（MVP は文字種ごとに固定フォント 1 つ） |
| `font_files` | 必須 | 各フォントのファイル識別（ファイル名・**ファイルハッシュ**・ウェイト・版） |
| `render_settings` | 必須 | 密度測定と最終描画に共通の描画設定（アンチエイリアス・二値化・エンジン版、[rendering-engine.md](../environment/rendering-engine.md)） |
| `dictionary_id` | 必須 | 文字密度辞書の識別子（文字集合＋フォントハッシュ＋サイズ＋描画設定から決まる、FR-04 のキー） |
| `dictionary_ref` | 条件付き必須 | 密度辞書実体の ref（キャッシュ配置は [P0-041](../roadmap/phase-0.md)） |
| `missing_glyphs` | 必須 | 欠落グリフの記録（0 件でも空として明示。暗黙代替の非発生を示す、AC-02） |

### 6. `density`（密度マップ、FR-03）

| 項目 | 区分 | 意味 |
| --- | --- | --- |
| `method` | 必須 | 平均明度・ガンマ・局所コントラスト・エッジ重みの選択と各パラメータ |
| `map_ref` | 条件付き必須 | 密度マップ実体の ref |
| `edge_ref` | 任意 | エッジ補助結果の ref |

### 7. `semantic_design`（画像解釈、FR-05）

| 項目 | 区分 | 意味 |
| --- | --- | --- |
| `observed` / `interpreted` | 条件付き必須 | 観察事実と推測・詩的解釈を分離して保持（実体が大きい場合は ref） |
| `author_edited` | 必須 | 作者が編集したか（編集内容は `edits` で追跡） |
| `pinned` | 必須 | 固定された項目（FR-14 の再生成範囲判定に使う） |
| `source_call` | 条件付き必須 | 由来する AI 呼出の識別子（`ai_calls` のエントリを指す。手入力時は手入力である旨） |

### 8. `text`（文章、FR-06 / FR-09 / FR-15 / FR-16）

| 項目 | 区分 | 意味 |
| --- | --- | --- |
| `mode` | 必須 | 文章モード（記述 / 散文詩 / 簡易カットアップ） |
| `chaos` | 必須 | 文法秩序と FR-16 の個別率 |
| `draft_refs` | 条件付き必須 | 初期草稿・素材の ref 列（追跡可能性、FR-09-5） |
| `candidate_refs` | 条件付き必須 | 言い換え候補と採否・評価値の ref |
| `final_ref` | 条件付き必須 | 最終文章の ref（出力 TXT と同一内容であること） |
| `materials` | 条件付き必須 | カットアップ素材ごとの出典・権利状態・言語（FR-15） |

### 9. `optimization`（最適化条件、FR-08 / FR-09 / FR-14）

| 項目 | 区分 | 意味 |
| --- | --- | --- |
| `weights` | 必須 | `visual_similarity` / `language_quality` / `image_relevance` / `style_consistency` |
| `tolerance` / `max_iterations` | 必須 | 密度許容差・反復上限 |
| `seed` | 必須 | ローカル決定的工程のシード（NFR-01） |
| `algorithm` | 必須 | 探索方式と版（MVP はビームサーチまたは局所探索） |
| `pins` | 必須 | 固定された領域・語句・段階（FR-14） |
| `budget_caps` | 必須 | 費用・呼出回数・トークンのキャップ設定（[ai-cost-budget.md](ai-cost-budget.md)） |
| `trace_ref` | 条件付き必須 | 探索履歴の ref |

### 10. `ai_calls`（外部 AI 呼出の来歴、FR-17 / X-06）

各エントリは [ai-adapter-contract.md](ai-adapter-contract.md) の `provenance` をそのまま持ち、加えて manifest 側で次を必須とする。詳細形式は [P0-042](../roadmap/phase-0.md)。

| 項目 | 区分 | 意味 |
| --- | --- | --- |
| `call_id` | 必須 | 呼出の一意識別子（他ブロックからの参照先） |
| `capability` / `operation` | 必須 | `vision` / `text`、`analyze_image` / `draft` / `paraphrase` |
| `request_ref` / `response_ref` | 必須 | 要求・応答エンベロープ実体の ref（保存応答再生の入力、AC-04） |
| `provenance` | 必須 | `model_id` / `prompt_ref` / `request_hash` / `token_usage` / `retry_count` / `route` / `created_at` |
| `status` | 必須 | `ok` / `failed`（失敗も履歴として保持） |

### 11. `edits`（作者編集履歴、FR-14 / NFR-03）

| 項目 | 区分 | 意味 |
| --- | --- | --- |
| `edit_id` / `at` | 必須 | 編集の識別子と時刻（追記のみ、既存エントリを書き換えない） |
| `target` | 必須 | 編集対象（ブロックと位置） |
| `change` | 必須 | 変更内容（前後の値または差分参照） |
| `invalidated` | 必須 | 無効化された後段工程（部分再生成の根拠、[architecture.md](../architecture.md)） |

### 12. `evaluation` と `outputs`（評価・出力、FR-12 / AC-01〜AC-07）

| 項目 | 区分 | 意味 |
| --- | --- | --- |
| `evaluation.metrics` | 条件付き必須 | MAE / SSIM / エッジ一致率の値と計算条件（[evaluation-metrics.md](../environment/evaluation-metrics.md) の仕様版を含む） |
| `evaluation.cell_check` | 条件付き必須 | 表示文字数とセル数の一致検証結果（AC-01） |
| `outputs.png_ref` / `outputs.txt_ref` | 条件付き必須 | 最終 PNG・UTF-8 TXT の ref（`hash` が再生一致判定の基準、AC-04） |
| `outputs.render_metadata` | 条件付き必須 | 出力時の描画条件（`fonts.render_settings` と一致すること、NFR-02） |
| `outputs.style` | 条件付き必須 | 出力時の見た目（字間・行間・文字色・背景色・二値化・反転、FR-12 / P1-041）。1 セルの画素を変えないため I-03 の一致対象から外し、`render_metadata` と分けて持つ |

## 不変条件（読込時に検証する）

- **I-01 スキーマ版整合**: `manifest.schema_version` が既知メジャー版であること。未知メジャーは明示エラーとし、暗黙解釈・部分読込をしない。
- **I-02 参照健全性**: すべての ref の `path` が存在し `hash` が一致すること。不一致は破損として報告し、暗黙に再生成しない。
- **I-03 描画一貫性**: `fonts.render_settings` と `outputs.render_metadata` が一致すること（NFR-02）。
- **I-04 セル整合**: `outputs.txt_ref` の表示文字数が `grid.cols × grid.rows` と一致すること（FR-10 / AC-01）。
- **I-05 内部参照解決**: `semantic_design.source_call` 等が指す `call_id` が `ai_calls` に存在すること。
- **I-06 秘密情報不在**: 秘密情報らしき値が manifest とその参照先に存在しないこと（[P0-043](../roadmap/phase-0.md) のスキーマテストで機械検証）。
- **I-07 相対パス**: `path` が絶対パス・端末固有パス・親ディレクトリ脱出を含まないこと。

## スキーマ版規則

- `manifest.schema_version` は `MAJOR.MINOR` とし、**manifest 全体の構造**にのみ責任を持つ。AI 要求・応答エンベロープの `schema_version`（[ai-adapter-contract.md](ai-adapter-contract.md)）、密度辞書・評価仕様の版は独立軸で、それぞれの実体側に保持する。
- **MINOR**: 後方互換な追加（任意項目の追加、列挙値の追加）。旧読取側は未知の任意項目を保持したまま無視できる。
- **MAJOR**: 破壊的変更（必須項目の削除・改名、型変更、意味変更、不変条件の強化）。
- **読取規則**: 読取側は「同一 MAJOR かつ MINOR が自身以下」を通常読込、「同一 MAJOR で MINOR が自身より新しい」は**読取専用オープン**（未知項目を保持して上書き保存しない）、「異なる MAJOR」は明示エラーとする。読取専用オープンの UI 挙動と移行手順は [P0-044](../roadmap/phase-0.md)。
- **未知項目の保持**: 読取専用オープン時は未知項目を破棄せず保持する。破棄する保存は MAJOR 変更時の移行処理でのみ許す。
- MVP 出荷時の初期版を `1.0` とし、Phase 1 実装中の変更は `1.x` の MINOR で扱う。実装で必須項目の削除・意味変更が必要になった場合のみ `2.0` へ上げ、[change-management.md](change-management.md) の手順で要件・テスト・ロードマップを同時更新する。

## 突合（要件との整合）

| 要件 | 本書での担保 |
| --- | --- |
| FR-17 プロジェクト保存 | 12 ブロックで入力ハッシュ・前処理・辞書識別子・AI 入出力・モデル識別子・設定・シード・編集履歴・評価・出力を必須化 |
| FR-14 再生成と編集 | `pins` / `edits.invalidated` で固定と影響範囲を保存し、部分再生成を可能にする |
| NFR-01 再現・再生 | `optimization.seed` と `ai_calls.request_ref` / `response_ref` で決定的再生の入力を保存 |
| NFR-02 描画一貫性 | `fonts.font_files`（ハッシュ）＋`render_settings` を辞書と出力で共有し I-03 で検証 |
| NFR-06 保存性 | ref 健全性（I-02）と編集履歴の追記保持で再読込後の同一性を保証 |
| NFR-08 可観測性 | `token_usage` / `retry_count` を保持し、秘密情報は I-06 で排除 |
| AC-04 再生 | `outputs.txt_ref` / `png_ref` のハッシュを再生結果と突合 |
| AC-05 保存 | 設定・`pins`・中間生成物 ref・`evaluation.metrics` を必須化し再読込で一致検証 |

## 未確定・次工程へ委譲

- **物理配置・ディレクトリ構成・キャッシュキー・ハッシュアルゴリズム**: [P0-041](../roadmap/phase-0.md)。本書は ref の論理形のみ固定。
- **`provenance` 詳細・プロンプト本文の保存方法・作者編集の来歴粒度**: [P0-042](../roadmap/phase-0.md)。
- **秘密情報検出規則とスキーマテスト実装**: [P0-043](../roadmap/phase-0.md)。
- **原子的保存（一時ファイル書込み後の置換）・読取専用オープンの UI 挙動・MAJOR 移行手順**: [P0-044](../roadmap/phase-0.md)。
- **各ブロックの値スキーマ（型・単位・列挙値）と JSON 表現**: Phase 1 実装で確定。本書は項目と必須区分を確定する。
- **SQLite 索引との役割分担**: manifest（正規情報源）と索引・履歴 DB の同期方針は Phase 1 実装で確定（[architecture.md](../architecture.md)）。

## 再確認事項（実装時に更新）

- 2,000〜5,000 セル作品で manifest 実体サイズが実用範囲に収まるか（候補列・探索履歴を ref へ出す境界の妥当性）。
- I-02 参照健全性検証が保存・再読込時間（NFR-04）へ与える影響。**実装状況**: [P1-003](../roadmap/phase-1.md) で検証を実装し、[P1-004](../roadmap/phase-1.md) の保存手順 A-04 で全 ref を照合している。時間影響は未実測（`bytes` によるサイズ先行判定のみ入れてある）。
- `text.final_ref` と `outputs.txt_ref` の hash 一致要求により、同一内容の実体が 2 パスに置かれる。`outputs/artwork.txt` は固定名で内容アドレスではないため重複自体は成立するが、どちらを正としてエクスポートするか、片方を欠いた状態を許すかは未確定。
- 読取専用オープン時の未知項目保持が、実際の `1.x` 追加で機能するかの往復テスト。
- `dictionary_id` の構成要素が [font-and-license.md](../environment/font-and-license.md) 確定後のフォント差し替えを正しく識別するか。

## 更新履歴

| 日付 | 変更点 |
| --- | --- |
| 2026-07-25 | 初版。ref の共通形、必須 12 ブロックと必須／条件付き必須項目、読込時の不変条件 I-01〜I-07、スキーマ版規則（MAJOR/MINOR、読取専用オープン、未知項目保持、初期版 1.0）を確定。物理配置は P0-041、来歴詳細は P0-042、秘密情報テストは P0-043、原子的保存・移行は P0-044 へ委譲。 |
| 2026-07-26 | 再確認事項に I-02 の実装状況と、`final_ref` / `txt_ref` の同一内容重複についての未確定点を追記（[P1-003](../roadmap/phase-1.md) / [P1-004](../roadmap/phase-1.md) の実装で判明）。 |
