# Python と主要ライブラリの対応バージョン候補

**状態**: 検証済み（2026-07-25 実測）
**目的**: コア処理（画像・描画・評価）に用いる Python と主要ライブラリの対応バージョン候補を、参照 PC 上で実測検証し、後工程の環境固定（依存ロック）と技術スパイクの基準にする。
**対象タスク**: [P0-011](../roadmap/phase-0.md)
**関連**: [reference-pc.md](reference-pc.md)、[architecture.md](../architecture.md)（技術構成案）、[ROADMAP](../roadmap/phase-0.md)

本書は「どの Python・ライブラリ版なら参照 PC で動くか」を実測で確定するための検証記録である。版の最終確定（ロックファイル生成）と、形態素解析器・描画エンジン・フォントの選定は別タスクへ委ねる。

## 記録方針

- 検証は [reference-pc.md](reference-pc.md) の参照 PC（Windows 11 x64, win_amd64）で行う。
- 各ライブラリは cp314 wheel の有無と、実際の `import` 成否を確認する。
- 本書は「対応バージョン候補」を確定する。厳密な版固定（requirements/lock）は依存確定タスクで別途行う。
- 個別領域の最終決定は各タスクへ委譲する: 形態素解析器 → [P0-016](../roadmap/phase-0.md)、描画エンジン → [P0-013](../roadmap/phase-0.md)、フォント → [P0-012](../roadmap/phase-0.md)。

## Python バージョン候補

参照 PC には複数の CPython が併存する（`py -0p` 実測）。

| 版 | パス | 位置づけ |
| --- | --- | --- |
| 3.14.3 | `C:\Python314\python.exe`（既定） | **主候補**。コア一式の cp314 wheel が整備済みで import 実測成功。 |
| 3.13 | `C:\Python313\python.exe` | フォールバック候補。 |
| 3.12 | `C:\python3.12\python.exe` / uv 管理 3.12.13 | フォールバック候補。wheel 網羅が最も広く、互換性リスク最小。 |
| 3.11 / 3.10 | ユーザー領域 | 旧版。積極採用しない。 |

主候補を 3.14.3 とする。cp314 の wheel 未整備ライブラリが後で判明した場合は 3.12/3.13 へ退避できる。

## 主要ライブラリ検証結果（実測: 2026-07-25 / Python 3.14.3 / win_amd64）

| ライブラリ | 用途（architecture.md） | 検証版 | cp314 wheel | 状態 |
| --- | --- | --- | --- | --- |
| Pillow | 画像処理・文字描画 | 11.3.0 | 有 | `import` 成功 |
| opencv-python | 前処理・エッジ検出 | 4.13.0.92 | 有 | `import cv2` 成功 |
| NumPy | 密度マップ | 2.4.2 | 有 | `import` 成功 |
| scikit-image | SSIM 等の評価 | 0.26.0 | 有 | `import skimage` 成功 |
| SciPy | 数値処理（scikit-image 依存） | 1.17.1 | 有 | `import` 成功 |
| Transformers | 文章生成（ローカル/補助） | 4.57.6 | 有（pure-python） | 導入確認 |
| SudachiPy | 日本語形態素解析（候補） | 0.6.11 | 有（`sudachipy-0.6.11-cp314-cp314-win_amd64.whl`） | wheel 取得確認。採否は P0-016。 |
| OR-Tools | 制約探索（任意） | 9.15.6755 | 有（該当版のみ） | wheel 有。MVP では任意。 |
| Gradio | 初期 UI（候補） | 6.11.0 | 有（pure-python） | 導入確認。UI 決定は P0-017。 |
| FastAPI | 作品用 Web（将来） | 0.135.1 | 有（pure-python） | 導入確認。 |

### 検証で確認できたこと

- コア画像処理スタック（Pillow / OpenCV / NumPy / scikit-image / SciPy）は Python 3.14.3 で cp314 wheel が揃い、同時 `import` に成功する。
- NumPy は 2.x 系（2.4.2）。OpenCV 4.13・scikit-image 0.26 が同一環境で共存・import できるため、NumPy 2.x ABI に対する主要ライブラリの追従は確認済み。
- OR-Tools は cp314 対応が 9.15.6755 のみ（旧版に cp314 wheel 無し）。採用時はこの版に固定する。

## 未確定・注意

- **形態素解析器**: どの Python 版にも未導入。SudachiPy 0.6.11 の cp314 wheel は確認済みだが、MeCab 系との比較・辞書配布条件・未知語挙動は [P0-016](../roadmap/phase-0.md) で決定する。本書は「3.14 で導入可能」までを保証する。
- **外部 LLM API クライアント**: 文章・画像解析は外部 AI 前提（P0-020〜P0-024）。SDK 版は provider 決定後に本書へ追記する。
- **版固定**: 本書は候補確定まで。requirements/lock の生成は依存確定時に行い、その版と本書の差分は「更新履歴」に残す。
- 検証は win_amd64 単一環境。他 OS 対応は MVP 対象外（[reference-pc.md](reference-pc.md) 準拠）。

## 更新履歴

| 日付 | 変更点 |
| --- | --- |
| 2026-07-25 | 初版。Python 3.14.3 を主候補とし、コア主要ライブラリの cp314 対応を実測検証。 |
