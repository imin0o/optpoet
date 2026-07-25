# project manifest・保存応答サンプルのレビュー記録

**状態**: レビュー済み（2026-07-25）
**目的**: [project-manifest.md](project-manifest.md)・[artifact-storage.md](artifact-storage.md)・[provenance-format.md](provenance-format.md)・[ai-adapter-contract.md](ai-adapter-contract.md) が定義した論理構造に対し、**具体値を入れたサンプル**を作成して定義の穴・矛盾を洗い出し、完了ゲート [P0-G05](../roadmap/phase-0.md) の判定根拠にする。
**対象タスク**: [P0-G05](../roadmap/phase-0.md)
**関連**: [secret-exclusion-test.md](secret-exclusion-test.md)（I-06）、[save-and-migration.md](save-and-migration.md)（スキーマ版）、[rendering-engine.md](../environment/rendering-engine.md)（描画設定）

## サンプル一式

| ファイル | 内容 |
| --- | --- |
| [manifest.sample.json](../samples/manifest.sample.json) | 必須 12 ブロックをすべて埋めた manifest（60×40=2,400 セル、記述モード、AI 呼出 3・編集 3） |
| [ai-request.sample.json](../samples/ai-request.sample.json) | 要求エンベロープ（`vision` / `analyze_image`） |
| [ai-response-ok.sample.json](../samples/ai-response-ok.sample.json) | 応答エンベロープ（`status=ok`） |
| [ai-response-failed.sample.json](../samples/ai-response-failed.sample.json) | 応答エンベロープ（`status=failed` / F-SERVICE、失敗フィクスチャと同形式） |
| [ai-response-replay.sample.json](../samples/ai-response-replay.sample.json) | 保存応答の再生時に返る実体（生成時 `provenance` を変更しないことを示す） |
| [prompt.sample.json](../samples/prompt.sample.json) | プロンプト記録（`rendered` を正本、画像は ref で参照） |

- ハッシュ値は書式のみ実物と同じ体裁の**説明用ダミー**（`sha256:` 前置・64 桁小文字 16 進）。実測値ではない。
- サンプルは正規情報源ではない。定義の正は各決定記録側にあり、サンプルは定義の**実例と検証材**である。

## 機械検証（実施: 2026-07-25）

検証スクリプトは `verify-samples.ps1`（スクラッチ実行、成果物として保持しない）。**結果: FAIL 0 件。**

| ID | 検証内容 | 結果 |
| --- | --- | --- |
| V-01 | 6 ファイルすべてが JSON として解釈可能 | PASS |
| V-02 | 全 ref（21 件）の `hash` が `sha256:<64 桁小文字 16 進>` | PASS |
| V-03 | I-07: `path` が相対 POSIX、`\`・ドライブレター・`..` を含まない | PASS |
| V-04 | 内容アドレス配下（`derived/` `text/` `trace/` `ai/`）のファイル名先頭 16 桁が `hash` 先頭 16 桁と一致 | PASS |
| V-05 | I-03: `fonts.render_settings` と `outputs.render_metadata` が完全一致 | PASS |
| V-06 | I-04: `grid.cols × rows` = `cell_check.expected_cells` = `displayed_chars` = 2,400、かつ MVP 範囲 2,000〜5,000 内 | PASS |
| V-07 | I-05: `semantic_design.source_call` と `superseded_by` が `ai_calls.call_id` に解決 | PASS |
| V-08 | I-06: 秘密情報らしきキー名（`api_key` / `authorization` / `bearer` / `secret` / `access_token` / `credential`）が不在 | PASS |
| V-09 | `seq` が `ai_calls` と `edits` で共有され単調増加・重複なし（1〜6） | PASS |
| V-10 | `request_hash` が要求・応答・manifest・`request_ref.hash` で一致 | PASS |
| V-11 | 再生用実体の `provenance.route` が `live` のまま（再生事実は manifest 側に記録） | PASS |
| V-12 | 失敗応答の `token_usage` が `null`（0 で埋めない） | PASS |
| V-13 | AC-02: `missing_glyphs` が空配列で明示 | PASS |

## レビュー指摘と反映

| ID | 指摘 | 影響 | 対応 |
| --- | --- | --- | --- |
| R-01 | **応答ファイル名が衝突する**。命名が `<request_hash 先頭 16 桁>.res.json` のみだと、同一要求が失敗（F-SERVICE）→ 再試行で成功した場合に、成功応答が失敗応答を同名で上書きする。失敗も履歴として保持する方針と矛盾する | 失敗履歴の喪失（NFR-06 / FR-17） | **反映済み**。応答に試行連番を付与し `<request_hash 先頭 16 桁>.a<連番>.res.json` とした（[artifact-storage.md](artifact-storage.md) 命名表・注記、[provenance-format.md](provenance-format.md) `response_ref` 行と重複排除の記述を修正） |
| R-02 | `text.final_ref` と `outputs.txt_ref` の内容同一性が本文の記述のみで、読込時の不変条件（I-01〜I-07）に含まれていない | 再生時の不一致を検出できない可能性（AC-04） | **未反映（提案）**。サンプルでは両者の `hash` を同値にした。不変条件 I-08 として追加するかは Phase 1 実装時に判断する |
| R-03 | `fonts.dictionary_id` の**表記形**が未定義（構成要素のみ定義） | 実装ごとに表記が割れる | **未反映（Phase 1 で確定）**。サンプルでは `dict:sha256:<64 桁>` を暫定採用した |
| R-04 | `preprocess` の「未適用は無変換値を明示」が、`crop` では原寸と同値の矩形になる | なし（定義どおり動作） | 対応不要。サンプルで実例化 |
| R-05 | `route=replay` の応答実体は生成時応答と**同一内容**になるため、内容アドレス上は 1 実体に集約される | なし（定義どおり） | 対応不要。再生サンプルは説明用に別ファイルとして置き、`_note` で実体には含めない旨を明記 |

## 未確定・次工程へ委譲

- `payload` / `result` / `variables` の能力別スキーマ、`text/` 配下の草稿・候補 JSON の内部構造: Phase 1 実装。
- `dictionary_id` の表記形（R-03）と不変条件 I-08 の要否（R-02）: Phase 1 実装。
- 密度マップの保存形式・拡張子（サンプルでは `.npy` を仮置き）: Phase 1 実装。
- サンプルの**実測値化**: 実装後に実データで再生成し、ダミーハッシュを実ハッシュへ差し替える。

## 更新履歴

| 日付 | 変更点 |
| --- | --- |
| 2026-07-25 | 初版。manifest・要求・応答（成功／失敗／再生）・プロンプトのサンプル 6 件を作成し、V-01〜V-13 を機械検証（FAIL 0）。R-01（応答ファイル名衝突）を artifact-storage.md / provenance-format.md へ反映。R-02・R-03 を Phase 1 へ委譲。 |
