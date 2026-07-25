# 形態素解析器の候補比較と決定

**状態**: 検証済み（2026-07-25 実測）
**目的**: 草稿を文・文節・形態素へ分解する処理（[P2-023](../roadmap/phase-2.md) / [requirements.md](../requirements.md) の言い換え候補生成）に用いる日本語形態素解析器を、参照 PC の Python 3.14 上で候補比較し、辞書の配布条件と未知語（OOV）挙動を実測で確認して選定する。
**対象タスク**: [P0-016](../roadmap/phase-0.md)
**関連**: [python-and-libraries.md](python-and-libraries.md)（P0-011 の版検証）、[reference-pc.md](reference-pc.md)、[architecture.md](../architecture.md)（技術構成案）、[requirements.md](../requirements.md)、[phase-2.md](../roadmap/phase-2.md)（P2-023）、[phase-3.md](../roadmap/phase-3.md)（P3-027 多粒度切断）

本書は 3 候補（SudachiPy / fugashi(MeCab) / Janome）を実際に導入して分割・未知語挙動を比較した記録である。スパイクのコードは [`spikes/p0-016-morphology/`](../../spikes/p0-016-morphology/) に置く。

## 用途と要件

本プロジェクトでは、LLM が生成した草稿を **文 → 文節 → 形態素** へ分解し、位置を保持したまま言い換え候補を作る（[P2-023](../roadmap/phase-2.md)）。将来は文字・形態素・任意長による切断も実験する（[P3-027](../roadmap/phase-3.md)）。したがって解析器には次を要求する。

1. **境界の安定性**: 詩的・造語的な入力でも、未知語が後続の形態素を飲み込まず、文節境界を保つこと。
2. **配布条件の明確さ**: 辞書を含めて再配布・同梱可能なライセンスであること（本ツールは参照 PC 上のローカル動作）。
3. **参照 PC への導入容易さ**: Python 3.14 / win_amd64 で、可能なら C コンパイラ不要で導入できること（[python-and-libraries.md](python-and-libraries.md)）。
4. **粒度制御**: 語の分割単位を選べると多粒度切断（P3-027）に有利。

## 検証環境

| 項目 | 値 | 出典 |
| --- | --- | --- |
| Python | 3.14.3 / win_amd64 | [reference-pc.md](reference-pc.md) / [python-and-libraries.md](python-and-libraries.md) |
| SudachiPy / SudachiDict-core | 0.6.11 / 20260723 | 本スパイク実測 |
| fugashi / unidic-lite | 1.5.2 / 1.0.8 | 本スパイク実測 |
| Janome | 0.5.0（ipadic 同梱） | 本スパイク実測 |

導入は隔離 venv で行った（再現手順は本書末尾）。3 候補いずれも Python 3.14.3 に導入できた。ただし **fugashi は cp314 wheel が無く sdist からビルド**（C コンパイラ必須）、SudachiPy・Janome は wheel のみで導入できた。

## 検証方法

共通の 2 文を各解析器に通す（コードは [`morphology_spike.py`](../../spikes/p0-016-morphology/morphology_spike.py)）。

- **通常文**: `私は東京都に住んでいる。`
- **未知語文**: `ヴェゾルグ現象がフワモコに作用し、ぴえん超えてぱおんになった。`（造語・新語・混在を含む）

各トークンの表層・品詞・OOV フラグを取得し、OOV 件数と境界の壊れ方を比較する。SudachiPy は分割モード A/B/C も併記する。

## 結果（実測: 2026-07-25）

### 通常文の分割

| 解析器 | 分割結果 |
| --- | --- |
| SudachiPy (C) | 私 / は / **東京都** / に / 住ん / で / いる / 。 |
| fugashi(unidic-lite) | 私 / は / 東京 / 都 / に / 住ん / で / いる / 。 |
| Janome(ipadic) | 私 / は / 東京 / 都 / に / 住ん / で / いる / 。 |

SudachiPy は既定の C モードで `東京都` を 1 語に保つ。unidic-lite / ipadic は短単位で `東京 / 都` に割る。

### 未知語文の挙動（★=OOV 判定）

| 解析器 | トークン数 | OOV | 境界の保持 |
| ---: | ---: | ---: | --- |
| SudachiPy (A/B/C) | 19 | 2（`ヴェゾルグ`★ / `フワモコ`★） | **良好**。未知語を 1 語に収め、後続 `現象`『に』等を独立に保つ。 |
| fugashi(unidic-lite) | 19 | 2（`ヴェゾルグ`★ / `フワモコ`★） | **良好**。`is_unk` で未知語を明示。細部の品詞は異なる（`ぱ/おん`→記号）。 |
| Janome(ipadic) | 13 | 4 | **不良**。`ぱおんになった` を 1 名詞に**連結**し、後続の動詞＋助動詞を飲み込む。 |

- **SudachiPy**: 未知語をカタカナ単位でまとまりよく切り、`is_oov()` で明示。3 モードとも本文では同結果。
- **fugashi(MeCab)**: MeCab の未知語ノードを `is_unk` で取得。境界は保つが、細粒度化で記号扱いになる箇所がある。
- **Janome**: ipadic の未知語連結により、造語混じりの並びで **文節境界が壊れる**（`ぱおんになった` が 1 トークン）。要件 1 に反する。

### SudachiPy 分割モード（多粒度）

`選挙管理委員会` を例に、A/B/C で粒度を選べる。

| モード | 結果 |
| --- | --- |
| A | 選挙 / 管理 / 委員 / 会 |
| B | 選挙 / 管理 / 委員会 |
| C | 選挙管理委員会 |

同一エンジンで粒度を切り替えられるため、P3-027 の多粒度切断に直接使える。

## 決定

**主候補: SudachiPy + SudachiDict-core を採用する。**

| 観点 | SudachiPy | fugashi(MeCab) | Janome |
| --- | --- | --- | --- |
| 境界の安定性(要件1) | ◎ | ○ | ×（未知語連結） |
| ライセンス明確さ(要件2) | ◎ Apache-2.0/Apache-2.0 | △ MeCab は GPL/LGPL/BSD 三択 | ○ Apache-2.0＋ipadic |
| 参照PC導入(要件3) | ◎ cp314 wheel のみ | △ sdist ビルド(要C compiler) | ○ pure-python |
| 粒度制御(要件4) | ◎ A/B/C | ○ 単一 | △ 単一 |

- **採用理由**: (1) エンジン・辞書とも Apache-2.0 で再配布条件が最も明確、(2) cp314 wheel と辞書 wheel だけで参照 PC に導入でき C コンパイラ不要、(3) 未知語で境界が壊れず OOV を `is_oov()` で明示できる、(4) A/B/C の分割モードが多粒度切断に直結する。
- **フォールバック**: 言語的な細粒度・品詞情報が必要になった場合は fugashi + unidic-lite を併用候補とする（導入時は C コンパイラ前提）。
- **不採用**: Janome は導入が最も容易だが、未知語連結により文節境界が壊れ、詩的・造語的入力を扱う本ツールの中核要件（P2-023）に適さない。

## 辞書の配布条件

| 解析器 | エンジン ライセンス | 辞書 | 辞書ライセンス | 同梱/再配布 |
| --- | --- | --- | --- | --- |
| SudachiPy | Apache-2.0 | SudachiDict-core | Apache-2.0 | 可。pip wheel（約 72 MB）を依存として同梱可。 |
| fugashi(MeCab) | MeCab: GPL/LGPL/BSD 三択, fugashi: MIT | unidic-lite | BSD-3-Clause 相当（UniDic） | 可だが MeCab 側ライセンス選択の明示が必要。 |
| Janome | Apache-2.0 | mecab-ipadic-2.7.0（同梱） | 修正BSD/GPL/LGPL 選択可 | 同梱済み。追加辞書不要。 |

採用する SudachiDict-core は Apache-2.0 単一で、本ツールへの同梱・再配布に追加条件が発生しない。

## 未確定・次工程へ委譲

- **版固定**: 本書は候補確定まで。requirements/lock への SudachiPy 0.6.11 / SudachiDict-core 20260723 の固定は依存確定タスクで行う（[python-and-libraries.md](python-and-libraries.md) の方針に従う）。
- **辞書の選択**: core / small / full の使い分けは、実際の草稿分解精度を見て Phase 2 実装時に確定する。本書は core で検証。
- **ユーザー辞書**: 作品固有の造語を登録するユーザー辞書運用は、必要になった時点で別途検討する（SudachiPy はユーザー辞書に対応）。
- **性能**: 本書は分割品質・ライセンス・導入性を対象とする。処理速度・メモリは草稿長が確定する Phase 2 実装時に実測する。

## 再現手順

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install sudachipy sudachidict-core fugashi unidic-lite janome
.\.venv\Scripts\python.exe spikes\p0-016-morphology\morphology_spike.py        # 人間可読
.\.venv\Scripts\python.exe spikes\p0-016-morphology\morphology_spike.py --json  # 生データ
```

## 更新履歴

| 日付 | 変更点 |
| --- | --- |
| 2026-07-25 | 初版。SudachiPy / fugashi(MeCab) / Janome を Python 3.14.3 で実測比較。未知語連結を理由に Janome を不採用とし、Apache-2.0・cp314 wheel・A/B/C 分割モードを理由に SudachiPy + SudachiDict-core を主候補に決定。 |
