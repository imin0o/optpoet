# 候補モデルの送信条件・保持・規約・地域制約

**状態**: 確認済み（2026-07-25）。本書は事実確認と暫定推奨であり、最終選定は費用（[P0-022](../roadmap/phase-0.md)）と合わせて確定する。
**目的**: [ai-capabilities.md](ai-capabilities.md) で固定した能力語彙（C-VISION / C-TEXT、横断要件 X-01〜X-06）を満たしうるクラウド API とローカルモデルについて、**画像送信条件・データ保持設定・利用規約・地域制約**の 4 軸を公式情報で確認する。以降の費用上限（[P0-022](../roadmap/phase-0.md)）、失敗応答（[P0-023](../roadmap/phase-0.md)）、アダプター契約（[P0-024](../roadmap/phase-0.md)）が同じ前提を共有できるようにする。
**対象タスク**: [P0-021](../roadmap/phase-0.md)
**関連**: [ai-capabilities.md](ai-capabilities.md)（能力定義）、[requirements.md](../requirements.md)（FR-01 EXIF 除去 / FR-05 身元非推定 / FR-18 明示送信、NFR）、[quality-and-operations.md](../quality-and-operations.md)（プライバシー要件）、[architecture.md](../architecture.md)（アダプター境界）、[open-issues.md](open-issues.md)

本書は特定 API へのロックインを決めるものではない。プロバイダー固有処理はアダプター内に閉じ込める方針（X-01）を前提に、**外部送信が発生する場合に本ツールのプライバシー要件を破らない条件**を各社について記録する。

## 評価対象

クラウド候補は、日本語のマルチモーダル（画像＋テキスト）解析と日本語文章生成の双方を公開 API で提供する主要 3 社とする。

| 記号 | プロバイダー | 対象 API | C-VISION | C-TEXT |
| --- | --- | --- | --- | --- |
| P-ANT | Anthropic | Claude API | ○ | ○ |
| P-OAI | OpenAI | OpenAI API | ○ | ○ |
| P-GGL | Google | Gemini API | ○ | ○ |

ローカル/自ホスト候補には、2026-07-25 時点で公開・非ゲートの次のモデルを加える。配布形式、容量、実行系が異なるため、クラウド候補と同一順位にはせず、参照 PC での実測を経て採否を決める。

| 記号 | モデル | 形式・実行系 | C-VISION | C-TEXT | 配布容量・主な条件 |
| --- | --- | --- | --- | --- | --- |
| L-HUI | [Huihui-ThinkingCap-Qwen3.6-27B-abliterated-NVFP4](https://huggingface.co/sakamakismile/Huihui-ThinkingCap-Qwen3.6-27B-abliterated-NVFP4) | NVFP4 / vLLM 0.21+ | ○ | ○ | 約 20.6 GB。日本語タグあり。Vision tower と MTP head は bf16 |
| L-HAU | [Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive](https://huggingface.co/HauhauCS/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive) | GGUF / llama.cpp 系 | ○ | ○ | 本体約 11〜44 GB + vision 用 mmproj 約 0.9 GB。多言語、MoE（約 3B active） |
| L-BON | [Ternary-Bonsai-27B-Abliterated-LowDeg-GGUF](https://huggingface.co/Hikari07jp/Ternary-Bonsai-27B-Abliterated-LowDeg-GGUF) | Q2_0 GGUF / PrismML llama.cpp fork | **不可** | ○ | 約 7.2 GB。text GGUF のみで vision mmproj なし |
| L-Q4H | [Qwen3.5-4B-Uncensored-HauhauCS-Aggressive](https://huggingface.co/HauhauCS/Qwen3.5-4B-Uncensored-HauhauCS-Aggressive) | GGUF / llama.cpp 系 | ○ | ○ | Q4_K_M 約 2.7 GB + mmproj 約 0.68 GB。16 GB VRAM の低メモリ基準候補 |
| L-Q9L | [Qwen3.5-9B-abliterated-GGUF](https://huggingface.co/lukey03/Qwen3.5-9B-abliterated-GGUF) | GGUF / llama.cpp・Ollama | ○ | ○ | vision Q4_K_M 約 6.6 GB。日本語タグあり。text-only 版は約 5.6 GB |
| L-Q9H | [Qwen3.5-9B-Uncensored-HauhauCS-Aggressive](https://huggingface.co/HauhauCS/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive) | GGUF / llama.cpp 系 | ○ | ○ | Q4/Q6/Q8 約 5.6/7.4/9.5 GB + mmproj 約 0.92 GB。201 言語 |
| L-Q14R | [Qwen3-14B-Abliterated-GGUF](https://huggingface.co/RootMonsteR/Qwen3-14B-Abliterated-GGUF) | GGUF / llama.cpp・Ollama | **不可** | ○ | Q5_K_M 約 10.5 GB、Q4_K_M 約 9.0 GB。JSON/形式保持は Q5 推奨 |

ローカル候補はいずれもモデルカード上 Apache-2.0 で、abliterated / uncensored 派生である。拒否抑制は品質・安全性の保証ではないため、FR-05 の禁止推定、出力スキーマ、作者レビューをクラウド候補以上にアプリ側で強制する。

## 4 軸の確認結果

確認日はいずれも 2026-07-25。クラウドの規約・保持設定とローカルモデルの配布内容は変動しうるため、選定確定時（[P0-022](../roadmap/phase-0.md)）に再確認する（下記「再確認事項」参照）。

### 1. 画像送信条件（C-VISION 入力）

| 項目 | P-ANT | P-OAI | P-GGL |
| --- | --- | --- | --- |
| マルチモーダル入力 | 可（画像＋テキスト指示） | 可 | 可 |
| 送信単位の上限例 | リクエスト最大 32MB／最大 600 画像。大量時は Files API で `file_id` 参照可 | 画像・ファイル入力に個別上限あり（詳細は要確認） | 画像・ファイル入力に個別上限あり（詳細は要確認） |
| 前処理前提 | 作者が EXIF 除去・トリミング済み（FR-01）を送る前提は共通。送信前に本ツール側で確定する | 同左 | 同左 |

- 本ツールは 1 枚の静止画のみ送信し（[ai-capabilities.md](ai-capabilities.md) C-VISION 要求）、送信有無・対象を作者へ提示する（X-05 / FR-18）。画像を暗黙送信しない設計は 3 社共通で成立する。
- 各社の厳密なサイズ・解像度・枚数上限はアダプター実装（[P0-024](../roadmap/phase-0.md)）で吸収する。P-ANT の 32MB/600 枚は上限の一例であり、本ツールは 1 枚運用のため実用上の制約にならない。

### 2. データ保持設定（保存・削除・訓練利用）

| 項目 | P-ANT | P-OAI | P-GGL |
| --- | --- | --- | --- |
| 既定でモデル訓練に使用 | しない（商用 API）。フィードバック送信分は例外（最大 5 年保持） | しない（2023-03-01 以降、明示 opt-in を除く） | **有料枠: しない** ／ **無料枠: する** |
| 標準保持 | 入出力を受領・生成から 30 日以内に自動削除 | `/chat/completions`・`/responses` は不正利用監視 30 日、アプリ状態は既定なし（`store` 時 30 日〜） | 有料枠: 違反検出目的で限定期間ログ（DPA で Google は処理者）。任意国で一時保存/キャッシュされうる |
| 違反フラグ時の延長 | 入出力を最大 2 年、trust & safety 分類スコアを最大 7 年 | 不正利用監視ログに保持（人間レビューは法令要求時等） | 違反検出・法令目的で保持 |
| ゼロデータ保持（ZDR） | 契約により対象 API・商用組織 API キー利用製品で受信データを保存しない | ZDR / Modified Abuse Monitoring 適格エンドポイントあり | 標準の ZDR 枠組みなし（有料枠 + DPA が基準） |

- **P-GGL の無料枠は本ツールに不適**。無料枠（AI Studio・Gemini API 無料クォータ）は送信内容と応答を Google の製品改善・ML 開発に使用し、人間レビュアーが読む/注釈する。規約は「機微・秘密・個人情報を送信するな」と明記する。写真を送る本ツールでは、P-GGL 採用時は**有料枠（課金プロジェクト）必須**。
- P-ANT / P-OAI は既定で非訓練・短期保持であり、本ツールのプライバシー要件（[quality-and-operations.md](../quality-and-operations.md)）と整合しやすい。ZDR/Modified Abuse Monitoring は将来の強化オプション。
- いずれも「保存応答からの再生」（X-02）はプロバイダー側保持とは独立に、本ツールが manifest へ応答を保存して実現する（[architecture.md](../architecture.md) 第4方針、FR-17）。プロバイダーの保持設定に依存しない。

### 3. 利用規約（送信内容・禁止事項）

| 項目 | P-ANT | P-OAI | P-GGL |
| --- | --- | --- | --- |
| 主な規約 | Commercial Terms + Usage Policy（AUP） | Business/Services Terms + Usage Policies | Gemini API Additional Terms + Prohibited Use Policy |
| 身元・センシティブ属性推定 | 指示側で抑制を明示（[ai-capabilities.md](ai-capabilities.md) C-VISION 必須挙動 1、FR-05）。各社 AUP も個人監視/プロファイリング等を制限 | 同左 | 同左 |
| データ処理者/管理者 | 商用は処理者寄り（BAA・DPA 提供） | Business 向け DPA 提供 | 有料枠は Google が処理者（DPA） |

- FR-05 の「身元・センシティブ属性を推定しない」は、規約依存ではなく**指示（プロンプト）と出力スキーマで本ツールが強制**する（X-05・[ai-capabilities.md](ai-capabilities.md)）。規約はこれを補強する下限であり、上限側の制御は本ツール責務。

### 4. 地域制約

| 項目 | P-ANT | P-OAI | P-GGL |
| --- | --- | --- | --- |
| 日本からの API 利用 | 提供国一覧に日本を明記 | 提供国一覧に日本を含む | 提供地域一覧に日本を含む |
| 参照 | [supported-countries](https://www.anthropic.com/supported-countries) | [supported-countries](https://platform.openai.com/docs/supported-countries) | [available-regions](https://ai.google.dev/gemini-api/docs/available-regions) |

- 参照 PC は Windows 11 x64・日本国内運用想定（[reference-pc.md](../environment/reference-pc.md)）。3 社とも日本から利用可能で、地域制約は候補除外要因にならない。

### ローカル/自ホスト候補への適用

| 軸 | ローカル候補の扱い |
| --- | --- |
| 画像送信条件 | 推論サーバーを loopback のみに固定する限り、入力画像・文章の外部送信は発生しない。モデル取得時の通信と推論入力を分離する |
| データ保持 | プロバイダー保持はない。プロジェクト保存、ランタイムのログ、キャッシュ、一時ファイルを本ツール側の保持方針で管理する |
| 利用規約 | 3 件ともモデルカード上 Apache-2.0。採用時はモデル ID、revision、ファイルハッシュ、上流モデル、NOTICE/帰属を固定して再確認する |
| 地域制約 | 推論 API の提供地域制約はない。Hugging Face からの取得可否とライセンス改定は採用時に再確認する |

- **L-HUI** は C-VISION / C-TEXT の両方を担えるが、配布容量だけで参照 PC の VRAM 16 GB を超える。NVFP4 の GPU 互換性、CPU offload、vision 使用時の実メモリと速度を実測するまで採用保留。
- **L-HAU** は vision 用 `mmproj` を併用すれば C-VISION / C-TEXT の両方を担える。低量子化版は参照 PC に載る可能性がある一方、推奨 128K context の KV cache と品質を含めた実測が必要。日本語は「multilingual」表記のみのため品質評価を必須とする。
- **L-BON** は容量面で最も軽いが C-TEXT 専用で、stock llama.cpp ではなく PrismML fork が必要。日本語対応の明記もないため、文章生成の補助候補としてのみ評価する。
- **16 GB VRAM の一次判定**は、モデル本体と mmproj の合計を約 12 GB 以下、batch 1、context 8K〜16K から開始し、KV cache・compute bufferを含む実測使用量が 16 GB 未満であることとする。モデルの最大 context が動くことは一次条件に含めない。
- **L-Q4H** は重みと mmproj の合計が約 3.4 GB で、16 GB VRAM の動作確認用ベースラインにする。品質が不足する場合に上位候補へ切り替える。
- **L-Q9L** は vision 対応 Q4 が約 6.6 GB で日本語タグもあり、16 GB VRAM の C-VISION / C-TEXT 統合本命とする。
- **L-Q9H** は量子化を Q4〜Q8 から選べる。まず Q6 + mmproj（合計約 8.3 GB）で評価し、モデルカードが推奨する長い context と実用的な短い context の品質差を測る。
- **L-Q14R** は text-only だが Q5 が約 10.5 GB で、カード上も 12 GB 以上の VRAM/RAM を推奨する。C-TEXT の構造化出力・日本語品質を9B候補と比較する。
- 候補はすべてコミュニティ派生モデルであり、カード記載だけで本ツール要件への適合を確定しない。モデル revision とハッシュを固定し、C-VISION / C-TEXT の受入データ、禁止推定、構造化出力、再現用設定を実機で検証する。

## プライバシー要件との突合

本ツール固有の要件（[requirements.md](../requirements.md) / [quality-and-operations.md](../quality-and-operations.md)）を送信面で満たせるか。

| 要件 | 満たし方 | プロバイダー依存か |
| --- | --- | --- |
| FR-01 EXIF 除去 | 送信前に本ツールで除去・確定 | 非依存（本ツール責務） |
| FR-05 身元非推定 | 指示＋出力スキーマで抑制 | 非依存（X-05） |
| FR-18 明示送信 | 送信有無・対象を作者へ提示、暗黙送信禁止 | 非依存（X-05） |
| 短期保持・非訓練 | P-ANT/P-OAI は既定で充足。P-GGL は有料枠必須 | **依存**（保持設定） |
| X-02 保存応答再生 | manifest に応答保存、ネットワークなしで再生 | 非依存 |

結論として、クラウド候補で送信・保持面の除外要因になるのは **P-GGL 無料枠の学習利用**である。ローカル候補は外部送信・プロバイダー保持を避けられる一方、loopback 固定、ローカルログ管理、実行互換性、実機性能、モデル由来の安全性を本ツール側で担保する必要がある。

## 暫定推奨

- **第一候補: P-ANT / P-OAI**。既定で非訓練・30 日以内削除・ZDR/Modified Abuse Monitoring 選択肢あり。プライバシー要件との整合が最も単純。
- **P-GGL は有料枠限定で候補維持**。無料枠は学習・人間レビューのため採用不可。有料枠採用時は課金プロジェクト構成を必須条件とする。
- **ローカル 7 モデルを条件付き候補として維持**。16 GB VRAM では L-Q4H を低メモリ基準、L-Q9L / L-Q9H を C-VISION / C-TEXT 本命、L-Q14R / L-BON を C-TEXT 比較対象とする。L-HUI / L-HAU はメモリ境界候補として残す。速度・メモリ・日本語品質・構造化出力・禁止推定を測定し、クラウド候補と同じ受入基準で判定する。
- 最終候補（またはアダプター初期実装対象）の選定は、費用・ローカル実行資源の上限（[P0-022](../roadmap/phase-0.md)）と併せて [open-issues.md](open-issues.md) に決定エントリを追加して確定する。X-01（交換可能性）により、初期実装後も差し替え可能。

## 再確認事項（選定確定時に更新）

- 各社の画像入力の厳密上限（サイズ・解像度・枚数）→ [P0-024](../roadmap/phase-0.md) アダプター契約で確定。
- P-OAI / P-GGL の日本を含む提供国一覧の最新版（本書は一覧記載を確認、個別行の抜粋は割愛）。
- ZDR / Modified Abuse Monitoring の適用条件と対象エンドポイントの最新版。
- 規約改定の有無（確認日 2026-07-25 基準）。
- ローカル 7 モデルの revision / ハッシュ、ランタイム版、参照 PC での VRAM・RAM・処理時間・日本語品質。
- L-HUI の NVFP4 GPU 互換性、L-HAU の量子化別品質と vision `mmproj`、L-BON の PrismML fork 依存。
- L-Q4H / L-Q9L / L-Q9H の vision 入力と短縮 context、L-Q14R Q5 の日本語・JSON 形式保持。

## 更新履歴

| 日付 | 変更点 |
| --- | --- |
| 2026-07-25 | VRAM 16 GB 向けの無検閲派生 4 モデル（L-Q4H / L-Q9L / L-Q9H / L-Q14R）を追加。実ファイル容量、vision 対応、推奨量子化、実測条件を記載。 |
| 2026-07-25 | ローカル/自ホスト 3 モデル（L-HUI / L-HAU / L-BON）を条件付き候補へ追加。外部送信なしという特性、能力差、ライセンス、参照 PC での実測条件を記載。 |
| 2026-07-25 | 初版。P-ANT / P-OAI / P-GGL の画像送信条件・データ保持・利用規約・地域制約を公式情報で確認。P-GGL 無料枠の学習利用を除外要因として特定し、暫定推奨（第一候補 P-ANT/P-OAI、P-GGL は有料枠限定）を記載。最終選定は P0-022 と併せて確定。 |
