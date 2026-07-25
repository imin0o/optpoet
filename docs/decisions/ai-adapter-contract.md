# 外部 AI アダプター契約（保存応答・ネットワークなし再生）

**状態**: 定義済み（2026-07-25）。アダプター境界の入出力エンベロープ・保存応答モード・来歴フィールドを固定する。フィールドの意味と構造を確定し、言語バインディング上の具体型（Python の dataclass 等）と manifest 物理配置は実装（Phase 1）および [P0-040](../roadmap/phase-0.md)〜[P0-042](../roadmap/phase-0.md) で確定する。
**目的**: C-VISION / C-TEXT の両アダプターが満たす**外向き契約**を固定する。提供者固有処理をアダプター内へ閉じ込め（X-01）、保存済み応答からネットワークなしで決定的に再生でき（X-02）、モックで受入テストを安定実行でき（X-03）、プロンプト・モデル識別子・入出力を manifest へ保存できる（X-06）基準を与える。前 4 文書（[P0-020](../roadmap/phase-0.md)〜[P0-023](../roadmap/phase-0.md)）が本書へ委譲した「キー名・型・エンベロープ構造」を確定する。
**対象タスク**: [P0-024](../roadmap/phase-0.md)
**関連**: [ai-capabilities.md](ai-capabilities.md)（C-VISION / C-TEXT 能力、横断要件 X-01〜X-06）、[ai-failure-responses.md](ai-failure-responses.md)（失敗クラス・フィクスチャ）、[ai-cost-budget.md](ai-cost-budget.md)（呼出構造・上限）、[ai-provider-candidates.md](ai-provider-candidates.md)、[requirements.md](../requirements.md)（FR-17 保存 / FR-18 明示送信）、[architecture.md](../architecture.md)（アダプター境界・再生保証・manifest）、[open-issues.md](open-issues.md)

本書はアダプター**境界の契約**であり、提供者固有の HTTP 実装ではない。アダプターは 3 つの経路（実呼出 / モック / 保存応答再生）を同一エンベロープで扱い、上位（Optimizer・UI）は経路を区別しない（[architecture.md](../architecture.md): 再生成より再生を保証）。キー名は本書で確定するが、値の内部型は実装言語へ委譲する。

## アダプター操作（論理インターフェース）

C-VISION / C-TEXT は次の論理操作のみを外部へ公開する（[ai-capabilities.md](ai-capabilities.md)）。各操作は 1 リクエスト → 1 レスポンスの純関数的境界とし、副作用（保存・課金計上）は上位が行う。

| アダプター | 操作 | 入力（意味） | 出力（意味） | 対応 FR |
| --- | --- | --- | --- | --- |
| Vision | `analyze_image` | 画像参照＋観点指示 | 構造化意味設計（事実／解釈分離） | FR-05 |
| Text | `draft` | 意味設計＋目標文字数＋文章モード | 草稿 1 本＋素材複数 | FR-09-1 / FR-15 |
| Text | `paraphrase` | 文節列＋言い換え要求 | 文節単位の複数候補（位置保持） | FR-09-2 |

- 操作は[ai-cost-budget.md](ai-cost-budget.md)の呼出構造（C-VISION 1〜3 / C-TEXT 草稿素材 2〜4 / 言い換え 3〜8、合計上限 15）に一致する。密度探索・測定・描画は非公開（ローカル）。

## 共通エンベロープ

全操作の要求・応答を共通エンベロープで包む。経路（実呼出／モック／保存応答）に依らず同一構造とする。

### 要求エンベロープ（`request`）

| フィールド | 意味 |
| --- | --- |
| `schema_version` | 本エンベロープのスキーマ版（後述の版付け規則） |
| `capability` | `vision` / `text` |
| `operation` | `analyze_image` / `draft` / `paraphrase` |
| `payload` | 操作固有の入力（意味設計・文節列・指示など。能力別スキーマは実装で確定） |
| `params` | 生成パラメータ（目標文字数・文章モード・候補数・シード） |
| `request_hash` | `payload`＋`params`＋`model_id` の内容ハッシュ。保存応答の照合キー（後述） |

### 応答エンベロープ（`response`）

| フィールド | 意味 |
| --- | --- |
| `schema_version` | 応答スキーマ版 |
| `status` | `ok` / `failed`（失敗時は下記失敗フィールド、[ai-failure-responses.md](ai-failure-responses.md)） |
| `result` | 成功時の操作固有出力（構造化意味設計・草稿・候補列） |
| `failure` | 失敗時の正規化失敗クラス（F-TIMEOUT/F-RATELIMIT/F-AUTH/F-SERVICE ほか、[ai-failure-responses.md](ai-failure-responses.md) の意味フィールド） |
| `provenance` | 来歴（次節、X-06） |

- 失敗フィクスチャ（[P0-023](../roadmap/phase-0.md)）は `status=failed` の応答エンベロープそのものであり、別形式を持たない。モックと保存応答は失敗も成功も同じ経路で再生する。

## 来歴フィールド（`provenance`、X-06）

manifest へ保存し FR-17 の再生・監査を可能にする。API キー・PII を含めない（保存前にマスク、[ai-failure-responses.md](ai-failure-responses.md) / [quality-and-operations.md](../quality-and-operations.md)）。

| フィールド | 意味 |
| --- | --- |
| `model_id` | プロバイダー・モデル識別子（例: 提供者名＋モデル名＋版） |
| `prompt_ref` | 送信プロンプトの参照（本文は中間生成物として別保存、[P0-042](../roadmap/phase-0.md)） |
| `request_hash` | 要求内容ハッシュ（保存応答照合キーと同一） |
| `token_usage` | 入力／出力トークン実測（費用・キャップ突合、[ai-cost-budget.md](ai-cost-budget.md)） |
| `retry_count` | 再試行回数・総待機（[ai-failure-responses.md](ai-failure-responses.md) の再試行記録） |
| `route` | 生成経路（`live` / `mock` / `replay`）。再生時は元 `route` を保持し再生である旨を別途記録 |
| `created_at` | 生成時刻（保存時にアプリが付与） |

## 保存応答モード（X-02、ネットワークなし再生）

保存済み応答から**決定的に同じ結果を再生**する（[architecture.md](../architecture.md): 同一応答を仮定せず再生を保証）。再生成ではない。

- **照合キー**: `request_hash`（`payload`＋`params`＋`model_id` のハッシュ）。同一要求は同一保存応答へ確定的に対応する。
- **再生手順**: アダプターは `route=replay` で、ネットワークへ出ず保存済み `response` を返す。`request_hash` 不一致（保存なし）は再生失敗として明示し、暗黙に実呼出へフォールバックしない（X-05 暗黙送信禁止）。
- **決定性**: 再生は入力に対し常に同じ `result` を返す。乱数・時刻・ネットワーク状態に依存しない。`params.seed` は要求ハッシュに含み、再生対象を一意化する。
- **保存形式**: `response` エンベロープをそのまま保存する。フィクスチャ（[P0-023](../roadmap/phase-0.md)）・実応答・モック応答は同一形式で相互交換可能。物理配置・キャッシュキーは [P0-041](../roadmap/phase-0.md) / [P0-042](../roadmap/phase-0.md)。

## モックアダプター（X-03）

- モックは `capability`／`operation`／`request_hash` を受け、事前登録した `response` エンベロープを返す実装であり、保存応答モードと同一機構。差は応答の出所（テスト固定データ）のみ。
- 受入テストは 4 失敗クラス＋成功応答を能力別に注入し、実 API なしで安定実行する（[ai-failure-responses.md](ai-failure-responses.md)）。

## スキーマ版付け規則

- `schema_version` は要求・応答それぞれに持たせ、manifest の全体スキーマ版（FR-17、[P0-040](../roadmap/phase-0.md)）とは別軸で管理する。
- 後方互換な追加（任意フィールド追加）はマイナー、破壊的変更（キー削除・型変更・意味変更）はメジャーとする。読取側は既知メジャー版のみ受理し、未知メジャーは明示エラー（暗黙解釈しない）。
- 保存済み応答は生成時の `schema_version` を保持する。移行方針（読取専用オープン・将来移行）は [P0-044](../roadmap/phase-0.md)。

## 突合（要件との整合）

| 要件 | 本書での担保 |
| --- | --- |
| X-01 交換可能性 | 提供者固有処理をアダプター内へ閉じ込め、境界を共通エンベロープで固定 |
| X-02 保存応答モード | `request_hash` 照合で保存応答を決定的に再生。実呼出への暗黙フォールバック禁止 |
| X-03 モック可能性 | モックは保存応答と同一機構。成功・4 失敗クラスを能力別に注入 |
| X-06 来歴保存 | `provenance` に model_id・prompt_ref・token_usage・retry を秘匿化して保存 |
| FR-17 プロジェクト保存 | 応答エンベロープと来歴を manifest へスキーマ版付きで保存し再生可能に |
| FR-18 / X-05 明示送信 | `route` を保持し、保存なし時に暗黙実呼出しない |

## 未確定・次工程へ委譲

- **`payload` / `result` の能力別スキーマ**: 意味設計・草稿・候補列の具体キーは実装（Phase 1）で確定。本書はエンベロープと来歴を固定。
- **manifest 物理配置・キャッシュキー・prompt 本文保存**: [P0-040](../roadmap/phase-0.md)〜[P0-042](../roadmap/phase-0.md)。
- **ハッシュ関数・正規化規則**: `request_hash` の対象正規化（順序・空白・浮動小数）とアルゴリズムは実装で確定し再現性を検証する。
- **プロバイダー別エラーコード→失敗クラス写像**: [ai-failure-responses.md](ai-failure-responses.md) / アダプター実装（候補確定後）。
- **スキーマ移行**: 読取専用オープン・将来移行は [P0-044](../roadmap/phase-0.md)。

## 再確認事項（実装時に更新）

- `request_hash` の正規化が実応答・モック・保存応答で完全一致することの実機検証。
- `schema_version` メジャー跨ぎ時の読取側エラー挙動のテスト。
- `provenance` マスク処理が API キー・PII を確実に除去することの検証（[P0-043](../roadmap/phase-0.md) スキーマテストと連動）。

## 更新履歴

| 日付 | 変更点 |
| --- | --- |
| 2026-07-25 | 初版。アダプター論理操作（analyze_image / draft / paraphrase）、共通要求・応答エンベロープ、来歴フィールド（X-06）、保存応答モード（request_hash 照合による決定的再生、暗黙フォールバック禁止、X-02）、モックアダプター（X-03）、スキーマ版付け規則を確定。能力別 payload/result スキーマと manifest 物理配置は Phase 1 / P0-040〜042 へ委譲。 |
