# 来歴形式（AI 応答・プロンプト・モデル識別子・作者編集）

**状態**: 定義済み（2026-07-25）。AI 呼出来歴・プロンプト保存・モデル識別子の構成・作者編集履歴の粒度と形式を確定する。秘密情報の検出規則と機械検証は [P0-043](../roadmap/phase-0.md)、原子的保存と移行は [P0-044](../roadmap/phase-0.md)、値の JSON 型・列挙値は Phase 1 実装で確定する。
**目的**: [project-manifest.md](project-manifest.md) が項目名のみ確定した `ai_calls` / `edits` と、[ai-adapter-contract.md](ai-adapter-contract.md) の `provenance` に**詳細形式**を与える。FR-17 の「AI 入出力・モデル識別子・編集履歴を保存し再生可能にする」を、AC-04（保存応答からの再生で TXT バイト一致・PNG 一致）・AC-05（再読込後に固定箇所と中間生成物が一致）・NFR-03（変更の影響範囲提示）・NFR-08（API キーと不要本文を記録しない）が満たせる粒度まで固定する。
**対象タスク**: [P0-042](../roadmap/phase-0.md)
**関連**: [project-manifest.md](project-manifest.md)（`ai_calls` / `edits` / `semantic_design.source_call`）、[artifact-storage.md](artifact-storage.md)（物理配置・ハッシュ・正規化）、[ai-adapter-contract.md](ai-adapter-contract.md)（要求・応答エンベロープ、`provenance`、`request_hash`）、[ai-failure-responses.md](ai-failure-responses.md)（失敗クラス・再試行記録）、[ai-cost-budget.md](ai-cost-budget.md)（`token_usage`）、[requirements.md](../requirements.md)（FR-05 / FR-09 / FR-14 / FR-15 / FR-17）、[quality-and-operations.md](../quality-and-operations.md)（NFR-03 / NFR-06 / NFR-08、AC-04 / AC-05）

## 原則

- **来歴は追記のみ**。既存エントリを書き換えない。訂正・取消も新しいエントリとして記録する。
- **再生に必要な実体は ref で持ち、manifest には識別子と要約だけを置く**（[artifact-storage.md](artifact-storage.md)）。
- **要求と応答は分けて保存する**。要求は再生の照合キー、応答は再生の出力。
- **記録した値から結果を説明できること**。どの文が、どの呼出・どの素材・どの編集に由来するかを追える（FR-09-5 / FR-15）。
- **秘密情報を来歴へ書かない**。API キー・トークン・資格情報は要求・応答・プロンプト・ログのいずれにも残さない（NFR-08、[P0-043](../roadmap/phase-0.md) で機械検証）。

## 1. AI 呼出来歴（`ai_calls` エントリ）

`ai_calls` は呼出順に並ぶ配列とし、成功・失敗を区別せずすべて記録する（失敗も費用と挙動の説明に必要、[ai-failure-responses.md](ai-failure-responses.md)）。

| 項目 | 区分 | 形式 |
| --- | --- | --- |
| `call_id` | 必須 | `call-<4 桁連番>`（プロジェクト内で単調増加、再採番しない） |
| `seq` | 必須 | 呼出順序の整数（時刻に依存せず順序を確定する） |
| `capability` / `operation` | 必須 | `vision` / `text`、`analyze_image` / `draft` / `paraphrase` |
| `request_ref` | 必須 | 要求エンベロープの ref（`ai/requests/<request_hash 先頭 16 桁>.req.json`） |
| `response_ref` | 必須 | 応答エンベロープの ref（`ai/responses/<request_hash 先頭 16 桁>.a<試行連番>.res.json`、[artifact-storage.md](artifact-storage.md)） |
| `provenance` | 必須 | 次節の展開形 |
| `status` | 必須 | `ok` / `failed` |
| `failure_class` | 条件付き必須 | `status=failed` のとき失敗クラス（F-TIMEOUT / F-RATELIMIT / F-AUTH / F-SERVICE ほか） |
| `superseded_by` | 任意 | 再試行・再生成で置き換えられた場合の後続 `call_id`（旧エントリは削除しない） |

- 同一 `request_hash` の呼出が複数回起きた場合、**エントリは呼出ごとに作る**。`request_ref` は同一実体を指す（内容アドレスで重複排除）。`response_ref` は、再生・モックで同一応答を返す場合は同一実体を指し、失敗後の再試行で**別の応答が返った場合は試行連番の別実体**を指す（既存応答を上書きしない、[artifact-storage.md](artifact-storage.md)）。
- `semantic_design.source_call` など他ブロックからの参照はすべて `call_id` を指す（I-05）。

### `provenance` の展開形

[ai-adapter-contract.md](ai-adapter-contract.md) の 7 フィールドを次の形で確定する。

| フィールド | 形式 |
| --- | --- |
| `model_id` | 解決済みモデル識別子（次節） |
| `prompt_ref` | プロンプト記録の ref（次々節） |
| `request_hash` | `sha256:<64 桁 16 進>`（[artifact-storage.md](artifact-storage.md) の表記に統一） |
| `token_usage` | `{input, output}` の実測整数。提供者が返さない場合は `null` とし 0 で埋めない |
| `retry_count` | `{attempts, total_wait_ms, classes}`（試行回数・総待機・発生した失敗クラス列） |
| `route` | `live` / `mock` / `replay` |
| `created_at` | 応答を保存した時刻（ISO 8601 拡張形式・UTC・ミリ秒まで） |

- **再生時の記録**: `replay` で保存応答を返した場合、保存済み `response` 実体の `provenance` は**生成時の値のまま変更しない**。再生した事実は当該実行の `ai_calls` エントリ側に `route=replay` と新しい `created_at` / `seq` で記録する。これにより「元の生成条件」と「再生の履歴」が混ざらない（X-02）。
- `token_usage` は `replay` / `mock` では元呼出の値を複写せず `null` とする（費用が発生していないため、[ai-cost-budget.md](ai-cost-budget.md) のキャップ集計と一致させる）。

## 2. モデル識別子（`model_id`）

| 要素 | 必須 | 意味 |
| --- | --- | --- |
| `provider` | 必須 | 提供者識別子 |
| `model` | 必須 | モデル名 |
| `version` | 必須 | **解決済み**の具体版・スナップショット識別子 |
| `requested` | 必須 | 要求時に作者・設定が指定した文字列（別名を含みうる） |

- 表記形は `provider:model@version`（例: `<provider>:<model>@<snapshot>`）とし、manifest には構造化した 4 要素と表記形の両方ではなく**構造化形のみ**を保存する（機械比較のため）。
- **別名を解決済み欄へ書かない**。`latest` のような可変別名は `requested` にのみ残し、`version` には応答が示した具体版を入れる。応答が具体版を返さない提供者では、`version` に取得できなかった旨を明示し（`unknown`）、再生の同一性は保存応答に依存する旨を記録する。
- `model_id` は `request_hash` の入力に含まれる（[ai-adapter-contract.md](ai-adapter-contract.md)）。したがって**モデル版が変われば別の保存応答になる**。同一 `request_hash` に異なる `model_id` が結び付くことはない。

## 3. プロンプト来歴（`prompt_ref` の実体）

送信プロンプト本文は manifest へ埋め込まず、`ai/prompts/` へ独立実体として保存する（[artifact-storage.md](artifact-storage.md)）。

- **配置と命名**: `ai/prompts/<prompt_hash 先頭 16 桁>.json`。`prompt_hash` は正規化 JSON 全体の SHA-256。
- **記録内容**:

| 項目 | 区分 | 意味 |
| --- | --- | --- |
| `template_id` / `template_version` | 必須 | プロンプトテンプレートの識別子と版（テンプレ改訂を区別する） |
| `variables` | 必須 | テンプレートへ差し込んだ値（作者設定・文字数・モード・意味設計の要約など） |
| `rendered` | 必須 | 実際に送信した本文（システム指示・利用者指示を役割ごとに分けた列） |
| `attachments` | 条件付き必須 | 送信した画像等の ref（**本体を埋め込まない**。`hash` で同一性を示す） |
| `locale` | 必須 | 生成指示の言語（MVP は `ja`） |

- **本文を必ず保存する**。テンプレート＋差込値だけでは、テンプレート実装が変わった後に同一本文を復元できないため、`rendered` を正本とし `template_id` / `variables` は説明用に併記する。
- 画像は `attachments` の ref で参照し、Base64 本体をプロンプト記録へ残さない（容量と NFR-08）。
- 同一本文は内容アドレスで 1 実体に集約され、複数の `call_id` から共有参照される。
- プロンプト記録は**ログではない**。工程ログには `prompt_hash` の先頭のみを出し、本文を出さない（NFR-08）。

## 4. 作者編集来歴（`edits` エントリ）

### 粒度

**作者が確定した 1 操作**を 1 エントリとする。キー入力単位・文字単位では記録しない。確定とは、UI 上で値を適用・保存・固定・採用したときを指す。

### 形式

| 項目 | 区分 | 形式 |
| --- | --- | --- |
| `edit_id` | 必須 | `edit-<4 桁連番>`（単調増加、再採番しない） |
| `seq` | 必須 | 編集順序の整数（`ai_calls.seq` と同じ単調増加列を共有し、AI 呼出と編集の前後関係を確定する） |
| `at` | 必須 | 確定時刻（ISO 8601 拡張形式・UTC） |
| `kind` | 必須 | 編集種別（下表） |
| `target` | 必須 | 対象位置（manifest ブロック名からのパス。例: `text.final`、`semantic_design.interpreted[2]`、`optimization.weights.visual_similarity`） |
| `change` | 必須 | `{before, after}`。いずれかが大きい場合は値の代わりに ref を置く（下記） |
| `invalidated` | 必須 | 無効化した工程 ID の列（[artifact-storage.md](artifact-storage.md) の `stage` と同一語彙。無効化なしは空列を明示） |
| `note` | 任意 | 作者メモ |

### 編集種別（`kind`）

| `kind` | 例 | 典型的な `invalidated` |
| --- | --- | --- |
| `setting` | 前処理値・グリッド・重み・許容差・シードの変更 | 変更箇所以降の工程（`density_map` 以降、`optimize` 以降 等） |
| `semantic_edit` | 画像解釈の観察・解釈項目の修正・手入力（FR-05） | `optimize` 以降 |
| `text_edit` | 最終文章の直接編集（FR-14） | `render`（加えて文字数・欠落グリフ・視覚誤差の再検証） |
| `candidate_select` | 言い換え候補の採否（FR-09） | `render` |
| `pin_change` | 領域・語句・段階の固定／解除（FR-14） | なし（次回探索の制約が変わるのみ） |
| `material_add` | カットアップ素材の追加と出典・権利状態・言語の登録（FR-15） | `optimize` 以降 |

- `text_edit` は編集後の再検証結果（表示文字数・欠落グリフ件数・視覚誤差）を当該エントリに併記し、検証未了の状態を保存しない（AC-01 / AC-02）。
- `pin_change` も履歴に残す。固定は結果に影響するため、AC-05 の「固定箇所が再読込後に一致」を履歴側からも説明できる必要がある。

### 大きな変更の扱い

`before` / `after` の合計が閾値（実装で決定、目安 4 KiB）を超える場合、値そのものではなく `text/` 配下の実体 ref を置く。差分ではなく**変更前後の全文**を保存する（差分適用の失敗で復元不能になる状態を作らない）。

### 取消・やり直し

取消は既存エントリの削除ではなく、**逆操作の新エントリ**（`kind` は元と同じ、`change` は前後を入れ替えた値、`note` に取消である旨）として追記する。履歴は常に単調増加し、過去の状態は履歴の再生で得る。

## 5. 来歴の連結（追跡可能性）

最終文章の各断片について、由来を次の連結で辿れることを要件とする（FR-09-5 / FR-15）。

```
outputs.txt_ref
  └ text.final_ref … 断片ごとに
       ├ origin_call   → ai_calls[call_id]   → provenance.prompt_ref / model_id / response_ref
       ├ origin_material → text.materials[id]  → 出典・権利状態・言語
       └ origin_edits  → edits[edit_id] の列（採用・直接編集・固定）
```

- 断片は文節単位（MVP のカットアップ粒度、FR-15）を最小単位とする。
- `origin_call` / `origin_material` / `origin_edits` はいずれも空でありうるが、**三つとも空の断片は許さない**（由来不明の文字列を出力へ入れない）。

## 6. 時刻・順序・ハッシュの関係

- `seq` は `ai_calls` と `edits` で共有する単調増加整数とし、**順序判定は時刻ではなく `seq` で行う**（時計変更・タイムゾーンに依存しない）。
- `at` / `created_at` は表示・監査用であり、[artifact-storage.md](artifact-storage.md) の規則どおり**実体のハッシュ対象へ含めない**。したがって同一入力の再実行で時刻が変わっても実体ハッシュは一致し、AC-04 のバイト一致を壊さない。
- 来歴は manifest 内（`ai_calls` / `edits`）に置き、`index.sqlite` へは検索用に複写する。SQLite は派生であり、破損時は manifest から再構築する。

## 7. 秘密情報とマスク

- 要求・応答・プロンプトの保存前に、認証ヘッダ・API キー・トークン・資格情報に相当する値を**保存対象から除外**する（マスク済み文字列に置換するのではなく、フィールドごと保存しない）。
- 提供者が応答内へ内部識別子を含める場合も、`provenance` に必要な `model_id` / `token_usage` 以外は保存しない。
- 工程ログには `call_id` / `seq` / 工程 ID / 所要時間 / 失敗クラス / ハッシュ先頭のみを出す。プロンプト本文・生成文章本文・画像を出さない（NFR-08、[architecture.md](../architecture.md)）。
- 検出規則と機械検証は [P0-043](../roadmap/phase-0.md)。本書は「何を保存しないか」を定義する。

## 突合（要件との整合）

| 要件 | 本書での担保 |
| --- | --- |
| FR-05 画像解釈 | `semantic_edit` で作者修正・手入力を履歴化し、`source_call` で由来 AI 呼出へ連結 |
| FR-09 文章生成 | 断片ごとの `origin_call` / `origin_edits` で草稿・候補・採否を追跡 |
| FR-14 再生成と編集 | `edits.invalidated` に工程 ID を必須化し、影響範囲だけの再生成を可能にする |
| FR-15 カットアップ | `origin_material` と `material_add` で素材の出典・権利状態・言語を追跡 |
| FR-17 プロジェクト保存 | AI 入出力 ref・`model_id`・プロンプト実体・編集履歴を必須項目として確定 |
| NFR-03 編集可能性 | `kind` ごとの `invalidated` 既定で影響範囲を作者へ提示できる |
| NFR-06 保存性 | 追記のみ・取消も追記とし、再読込後に履歴と固定箇所が失われない |
| NFR-08 可観測性 | 秘密情報をフィールドごと非保存、ログは識別子と評価値に限定 |
| AC-04 再生 | `request_ref` / `response_ref` と `route=replay` の分離記録で決定的再生を保証 |
| AC-05 保存 | `pin_change` を含む全編集を履歴化し、再読込後の固定箇所一致を検証可能にする |

## 未確定・次工程へ委譲

- **秘密情報の検出規則・スキーマテスト実装**: [P0-043](../roadmap/phase-0.md)。
- **原子的保存と履歴の追記単位（1 編集ごとの保存か、明示保存時にまとめるか）**: [P0-044](../roadmap/phase-0.md)。
- **`payload` / `result` / `variables` の能力別具体スキーマ**: Phase 1 実装（[ai-adapter-contract.md](ai-adapter-contract.md) の委譲を継承）。
- **`change` を ref へ逃がす閾値の実測値**: Phase 1（目安 4 KiB を初期値とし、manifest サイズ実測で調整）。
- **プロンプトテンプレート本体の管理場所と版付け**: Phase 1（`template_id` / `template_version` の語彙をここで確定するに留める）。
- **履歴 UI（表示・逆操作・比較）**: Phase 1 以降。

## 再確認事項（実装時に更新）

- `seq` 共有列が AI 呼出と編集の交錯した実操作で正しい前後関係を与えるか。
- 5,000 セル作品で `edits` の `before` / `after` を全文保存した場合の manifest サイズ（ref 逃がし閾値の妥当性）。
- `replay` 時に `token_usage=null` とする扱いが [ai-cost-budget.md](ai-cost-budget.md) のキャップ集計と矛盾しないか。
- 提供者が具体版を返さない場合の `version=unknown` が、AC-04 の再生一致に影響しないことの確認。
- 「三つとも空の断片を許さない」制約が、作者の完全手入力文章でも成立するか（手入力は `origin_edits` を持つため成立する想定）。

## 更新履歴

| 日付 | 変更点 |
| --- | --- |
| 2026-07-25 | 初版。`ai_calls` エントリ詳細形式と `provenance` 展開形、再生時の記録分離、`model_id` の 4 要素と別名非保存、プロンプト記録の内容と配置（`rendered` を正本）、`edits` の粒度・種別・`invalidated` 既定・取消の追記表現、断片の由来連結、`seq` による順序確定とハッシュ非対象の時刻、秘密情報の非保存方針を確定。検出規則は P0-043、保存単位は P0-044、具体スキーマは Phase 1 へ委譲。 |
