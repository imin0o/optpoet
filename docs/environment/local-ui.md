# ローカル UI 候補の比較と決定

**状態**: 検証済み（2026-07-25 実測）
**目的**: authoring UI（設定・同意・比較・固定・再生成・書き出し / [architecture.md](../architecture.md) の Authoring UI、requirements [FR-18](../requirements.md) 進捗・中断・失敗）に用いるローカル UI フレームワークを、参照 PC の Python 3.14 上で候補比較し、(1) loopback 固定、(2) 実行中生成の取消、(3) 進捗表示 を実測で確認して選定する。
**対象タスク**: [P0-017](../roadmap/phase-0.md)
**関連**: [architecture.md](../architecture.md)（「UI は loopback のみに公開する」/「初期版: Gradio / Streamlit」）、[requirements.md](../requirements.md)（FR-18）、[python-and-libraries.md](python-and-libraries.md)（P0-011）、[reference-pc.md](reference-pc.md)

本書は 3 候補（Gradio / Streamlit / NiceGUI）を実際に起動し、待受アドレスを `netstat` で実測し、取消・進捗 API を確認した記録である。スパイクのコードは [`spikes/p0-017-ui/`](../../spikes/p0-017-ui/) に置く。

## 用途と要件

authoring UI は単一作者の端末で動作し、外部へ公開しない（[architecture.md](../architecture.md) ローカルファースト）。生成は外部 AI 呼出しを含む長時間処理であり、作者は進捗を見て中断でき、完了済み中間生成物を失わない（[FR-18](../requirements.md)）。したがって UI フレームワークに次を要求する。

1. **loopback 固定（要件1）**: 待受を `127.0.0.1` に限定でき、既定で LAN/全 IF へ露出しないこと。誤って全 IF 公開になる既定は減点。
2. **実行中生成の取消（要件2）**: 進行中の生成処理を、完了済み成果物を壊さずに中断できること（FR-18 の中核）。
3. **進捗表示（要件3）**: 各工程の進捗・処理量を逐次表示できること。
4. **参照 PC への導入容易さ（要件4）**: Python 3.14 / win_amd64 で、可能なら wheel のみ（C コンパイラ不要）で導入できること（[python-and-libraries.md](python-and-libraries.md)）。

## 検証環境

| 項目 | 値 | 出典 |
| --- | --- | --- |
| Python | 3.14.3 / win_amd64 | [reference-pc.md](reference-pc.md) / [python-and-libraries.md](python-and-libraries.md) |
| Gradio | 6.20.0 | 本スパイク実測 |
| Streamlit | 1.60.0 | 本スパイク実測 |
| NiceGUI | 3.15.0（FastAPI 0.140.0 / uvicorn 0.51.0 ベース） | 本スパイク実測 |

導入は隔離 venv で行った（再現手順は本書末尾）。**3 候補いずれも Python 3.14.3 に wheel のみで導入でき、C コンパイラは不要**だった。

## 検証方法

各フレームワークを実際にサブプロセスで起動し、待受ポートが LISTEN するまで待って `netstat -ano -p tcp` から待受アドレスを取得する（コードは [`ui_loopback_spike.py`](../../spikes/p0-017-ui/ui_loopback_spike.py)）。

- **既定起動**: 待受アドレスを指定せずに起動し、既定の bind を実測する。
- **loopback 固定**: 各フレームワークの固定パラメータ（Gradio `server_name`、Streamlit `--server.address`、NiceGUI `host`）に `127.0.0.1` を渡し、実際に loopback 限定になるか実測する。
- **取消・進捗**: 各フレームワークの取消・進捗 API を確認し、機構を記録する。

待受アドレスが `127.0.0.1` / `::1` のみなら loopback 限定、`0.0.0.0` / `::` を含めば全 IF 公開と判定する。

## 結果（実測: 2026-07-25）

### loopback 固定（netstat 実測）

| フレームワーク | 既定の待受 | `127.0.0.1` 固定時 |
| --- | --- | --- |
| Gradio | **`127.0.0.1`（loopback 既定）** | `127.0.0.1` ✓ |
| Streamlit | `0.0.0.0`（全 IF 公開） | `127.0.0.1` ✓ |
| NiceGUI | `0.0.0.0`（全 IF 公開） | `127.0.0.1` ✓ |

3 候補とも固定パラメータで loopback 限定にできる。ただし **Gradio だけが既定で `127.0.0.1`**、Streamlit・NiceGUI は**既定で全 IF に公開**され、明示設定を忘れると LAN へ露出する（要件1に対する既定の安全性で差）。

### 取消（実行中生成の中断）

| フレームワーク | 取消 | 機構 |
| --- | --- | --- |
| Gradio | ◎ | `queue()` + event の `cancels=[...]` で実行中イベントを中断。ジェネレータの `yield` 途中で停止可。 |
| NiceGUI | ◎ | async ネイティブ。生成を `asyncio.Task` として起動し `task.cancel()` で即中断。 |
| Streamlit | △ | スクリプト再実行モデル。実行中の python コールバックを直接中断できず、`session_state` フラグ + 再実行で疑似中断するのみ。長時間の同期処理はブロックする。 |

Streamlit の再実行モデルは、FR-18 の「作者は生成を中断でき、完了済み中間生成物を失わない」を素直に満たしにくい。

### 進捗表示

| フレームワーク | 進捗 | API |
| --- | --- | --- |
| Gradio | ○ | `gr.Progress` / ジェネレータ `yield` によるストリーミング更新 |
| Streamlit | ○ | `st.progress` / `st.status` / `st.spinner` |
| NiceGUI | ○ | `ui.linear_progress` / `ui.circular_progress`（async 更新） |

進捗表示は 3 候補とも備える。

## 決定

**主候補: Gradio を採用する。**

| 観点 | Gradio | NiceGUI | Streamlit |
| --- | --- | --- | --- |
| loopback（要件1） | ◎ 既定で `127.0.0.1` | ○ 固定可（既定は全 IF） | ○ 固定可（既定は全 IF） |
| 取消（要件2） | ◎ `cancels=` | ◎ asyncio cancel | △ 再実行モデル |
| 進捗（要件3） | ○ `gr.Progress` | ○ `ui.*_progress` | ○ `st.progress` |
| 導入（要件4） | ◎ cp314 wheel | ◎ cp314 wheel | ◎ cp314 wheel |

- **採用理由**: (1) 既定で `127.0.0.1` に束縛され、設定漏れによる LAN 露出が起きにくく「UI は loopback のみに公開する」方針に既定で合致、(2) `cancels=` と `gr.Progress` で FR-18 の進捗・中断を追加実装なしに満たせる、(3) 画像入力・比較・ダウンロードなど authoring UI 部品が標準で揃い、初期版の実装コストが低い、(4) cp314 wheel のみで参照 PC に導入できる。
- **フォールバック**: 作者操作が複雑化し細かな画面制御・並行処理が必要になった場合は NiceGUI を採用候補とする。async ネイティブで取消が最も素直で、将来の「作品用 Web 版」（[architecture.md](../architecture.md) FastAPI + React 系）への発展とも親和的。
- **不採用**: Streamlit は導入容易で進捗表示も持つが、(a) 既定で全 IF 公開、(b) 再実行モデルゆえ実行中生成の取消が構造的に困難で、FR-18 の中断要件に弱いため主候補としない。

## 未確定・次工程へ委譲

- **版固定**: 本書は候補確定まで。requirements/lock への Gradio 6.20.0 の固定は依存確定タスクで行う（[python-and-libraries.md](python-and-libraries.md) の方針に従う）。
- **画面設計**: authoring UI の情報設計・画面遷移（設定→比較→固定→書き出し）は UI/UX 方針として別途決める。本書はフレームワーク選定のみ。
- **作品用 Web 版**: 最終作品の Web 表示（Canvas / SVG）は authoring UI とは別系統（[architecture.md](../architecture.md)）。本書の対象外。
- **取消の実装契約**: 外部 AI 呼出しのタイムアウト・取消・再試行（[architecture.md](../architecture.md) 外部依存）と UI 取消の接続は、AI アダプター契約（[P0-024](../roadmap/phase-0.md)）確定後に実装で結線する。

## 再現手順

```powershell
py -3.14 -m venv spikes\p0-017-ui\.venv
.\spikes\p0-017-ui\.venv\Scripts\python.exe -m pip install gradio streamlit nicegui
.\spikes\p0-017-ui\.venv\Scripts\python.exe spikes\p0-017-ui\ui_loopback_spike.py        # 人間可読
.\spikes\p0-017-ui\.venv\Scripts\python.exe spikes\p0-017-ui\ui_loopback_spike.py --json  # 生データ
```

> Windows / 日本語ロケール前提。待受アドレスの取得に `netstat -ano -p tcp` を用いる。

## 更新履歴

| 日付 | 変更点 |
| --- | --- |
| 2026-07-25 | 初版。Gradio / Streamlit / NiceGUI を Python 3.14.3 で実測比較。netstat で待受を実測し、Gradio が loopback 既定・取消/進捗ネイティブである点を理由に主候補に決定。Streamlit は既定で全 IF 公開かつ再実行モデルで取消が困難なため不採用。 |
