# 検証用データセット（12枚選定）

**状態**: P0-030 選定完了 / P0-031 原本ハッシュ確定 / P0-032 カバレッジ実測検証完了  
**目的**: MVP 判定用の固定検証画像 12 枚を、権利が明確な素材から選定して固定する。  
**関連**: [quality-and-operations.md](../quality-and-operations.md) 6章、[requirements.md](../requirements.md)、[open-issues.md](../decisions/open-issues.md) OI-002

本書は [quality-and-operations.md](../quality-and-operations.md) 6章「検証用データセット」の要件
（人物・風景・建築・静物を各 3 枚、権利確認済み、難易度カバレッジを含む）を満たす固定 12 枚の
正規記録である。第三者が同一データで受入判定を再現できることを目的とする（完了ゲート P0-G03）。

## 1. 出所とライセンス方針

- 出所は権利状態が明確な **CC0 1.0 / Public Domain** の公開素材のみとする。CC BY 等の帰属要求
  ライセンスは、来歴・出力表示の負担を避けるため採用しない。
- 主たる出所は Wikimedia Commons とし、各ファイルのライセンステンプレートを MediaWiki API
  （`imageinfo` の extmetadata と `revisions` の wikitext）で実データから確認した。
- 選定日: 2026-07-25。全 12 枚が実在確認済み。ライセンス内訳は CC0-1.0 が 5 枚、Public Domain が 7 枚。

## 2. カテゴリ × 難易度カバレッジ

難易度 5 種（高コントラスト / 低コントラスト / 細かい輪郭 / 広い平坦部 / 逆光）を 12 枚全体で網羅する。

| 難易度 | 該当 slot |
| --- | --- |
| 高コントラスト | portrait-3, architecture-1, architecture-2, still-life-1, still-life-2, still-life-3 |
| 低コントラスト | portrait-2, landscape-2, landscape-3 |
| 細かい輪郭 | portrait-1, portrait-3, landscape-1, architecture-1, architecture-2, architecture-3, still-life-2, still-life-3 |
| 広い平坦部 | portrait-1, portrait-2, portrait-3, landscape-1, landscape-2, landscape-3, architecture-3, still-life-1, still-life-3 |
| 逆光 | landscape-1（低斜光）, landscape-3（霧越し逆光シルエット）, architecture-2（奥の明窓） |

## 3. 選定 12 枚

各 slot は category を明示し、file_page_url を一次参照とする。原本ハッシュは P0-031 で本表へ追記する。

### 人物（portrait）

| slot | ファイル / 出典 | ライセンス | 作者 | 難易度 | 主要構図 |
| --- | --- | --- | --- | --- | --- |
| portrait-1 | [Boy Face from Venezuela.jpg](https://commons.wikimedia.org/wiki/File:Boy_Face_from_Venezuela.jpg) | CC0-1.0 | Wilfredor | 細かい輪郭 / 広い平坦部 | 濡れ髪と睫毛が細密な少年の超クローズアップ、右背景は緑のボケで平坦 |
| portrait-2 | [My niece Julia full face, by Julia Margaret Cameron.jpg](https://commons.wikimedia.org/wiki/File:My_niece_Julia_full_face,_by_Julia_Margaret_Cameron.jpg) | Public domain（PD-Scan / PD-old, 1867 撮影） | Julia Margaret Cameron | 低コントラスト / 広い平坦部 | ソフトフォーカスの正面顔、暗く平坦な背景に沈む軟調な階調 |
| portrait-3 | [David R. Allen, DOE Oak Ridge Office (9364899021).jpg](https://commons.wikimedia.org/wiki/File:David_R._Allen_Assistant_Manager_for_Safety_and_Technical_Services_Department_of_Energy_Oak_Ridge_Office_(9364899021).jpg) | Public domain（PD-USGov-DOE） | U.S. DOE Oak Ridge Office | 高コントラスト / 広い平坦部 / 細かい輪郭 | 濃紺スーツ×明るいグレー背景のスタジオ証明写真、ネクタイ柄が細部 |

### 風景（landscape）

| slot | ファイル / 出典 | ライセンス | 作者 | 難易度 | 主要構図 |
| --- | --- | --- | --- | --- | --- |
| landscape-1 | [Utah Dunes Landscape - West Desert District.jpg](https://commons.wikimedia.org/wiki/File:Utah_Dunes_Landscape_-_West_Desert_District.jpg) | Public domain（PD-USGov-BLM） | BLM Utah / Bob Wick | 細かい輪郭 / 広い平坦部 / 逆光 | 低い斜光で稜線が浮く砂丘の風紋、空と砂の平坦部＋朝焼けの山 |
| landscape-2 | [Foggy landscape in Myťa, Hvožďany, Central Bohemia (51867697891).jpg](https://commons.wikimedia.org/wiki/File:Foggy_landscape_in_My%C5%A5a,_Hvo%C5%BE%C4%8Fany,_Central_Bohemia_(51867697891).jpg) | CC0-1.0 | Ted Moravec | 低コントラスト / 広い平坦部 | 霧に沈む層状の丘陵、極めて軟調で平坦な大気遠近 |
| landscape-3 | [Foggy sunrise (53068259930).jpg](https://commons.wikimedia.org/wiki/File:Foggy_sunrise_(53068259930).jpg) | Public domain（PD-USGov-FWS） | U.S. Fish and Wildlife Service (Midwest) | 逆光 / 低コントラスト / 広い平坦部 | 霧越しの太陽と逆光シルエットの並木、地表に低い霧の帯 |

### 建築（architecture）

| slot | ファイル / 出典 | ライセンス | 作者 | 難易度 | 主要構図 |
| --- | --- | --- | --- | --- | --- |
| architecture-1 | [Canterbury Cathedral Tower Ceiling.jpg](https://commons.wikimedia.org/wiki/File:Canterbury_Cathedral_Tower_Ceiling.jpg) | CC0-1.0 | Michael D Beckwith | 細かい輪郭 / 高コントラスト | 見上げた扇状ヴォールト天井、放射状の細密トレーサリーが対称 |
| architecture-2 | [St Marys Cathedral Nave Edinburgh.jpg](https://commons.wikimedia.org/wiki/File:St_Marys_Cathedral_Nave_Edinburgh.jpg) | CC0-1.0 | Michael D Beckwith | 高コントラスト / 逆光 / 細かい輪郭 | 身廊の一点透視、暗い列柱と奥の明るい祭壇・窓の輝度差 |
| architecture-3 | [Brick Wall Building.jpg](https://commons.wikimedia.org/wiki/File:Brick_Wall_Building.jpg) | CC0-1.0 | Bango Textures (iso republic) | 広い平坦部 / 細かい輪郭 | 風化したレンガと目地の全面テクスチャ、平坦だが微細な輪郭が密 |

### 静物（still-life）

| slot | ファイル / 出典 | ライセンス | 作者 | 難易度 | 主要構図 |
| --- | --- | --- | --- | --- | --- |
| still-life-1 | [Gorgonzola and a pear.jpg](https://commons.wikimedia.org/wiki/File:Gorgonzola_and_a_pear.jpg) | Public domain（PD-author / PDphoto.org） | Jon Sullivan | 高コントラスト / 広い平坦部 | 黒トレイ・黒背景にチーズと洋梨、明暗差の強い低照度の暗部が広い |
| still-life-2 | [Apples garlic cloves still life.jpg](https://commons.wikimedia.org/wiki/File:Apples_garlic_cloves_still_life.jpg) | Public domain（PD-author） | Jon Sullivan | 高コントラスト / 細かい輪郭 | 石タイル上のリンゴとニンニク、硬い木漏れ日で濃い影と皮の細部 |
| still-life-3 | [Still life fruit.jpg](https://commons.wikimedia.org/wiki/File:Still_life_fruit.jpg) | Public domain（PD-author） | Jon Sullivan | 高コントラスト / 広い平坦部 / 細かい輪郭 | 銅ザルの果実を暗背景の低照度で、光沢のハイライトと穴の細部 |

## 4. 原本ハッシュ（P0-031）

第三者が同一バイトを取得して受入判定を再現できるよう（完了ゲート P0-G03）、各 slot の原本 SHA-256 と
バイト長を固定する。ハッシュ対象は下表の原寸 URL（upload.wikimedia.org の原寸直リンク）が返すバイト。

- 取得日: 2026-07-25。取得方法: `curl -sL`（識別子付き User-Agent、レート制限回避のため連続取得は間隔を空ける）。
- 全 12 枚が JPEG（先頭マジックバイト `ff d8 ff`）であることを取得後に確認済み。
- 権利状態（ライセンス）・主要構図・難易度は 3 章の各表に記載し、Public Domain の根拠は 5 章に補足する。

| slot | bytes | SHA-256（原本） |
| --- | --- | --- |
| portrait-1 | 10,864,429 | `e11be19f72949f9fe445b32077a63911ca065c09097477318ab9c75600ffd321` |
| portrait-2 | 3,680,047 | `1a28914be1038939c2018274df3883f40ca4e68dbb05db5ea8ee2064972f8849` |
| portrait-3 | 982,789 | `9388025bfe04a1fa359ef4838880715669c01a2b9f96f6d1a21d8b5e2f89a3c7` |
| landscape-1 | 5,356,067 | `08786cf02088576bf95df9c7b941c8a358c6843e1702d3fe37c19597328ad589` |
| landscape-2 | 1,344,244 | `f6fa73b7b0e8de6e891d954f44770e485b412c398b7a52cbc26cb0a7937a688a` |
| landscape-3 | 19,378,010 | `10e874dcffe302c3c094e937cbb49ace69169dfe4c48c618656b5631b7476c26` |
| architecture-1 | 22,095,050 | `2fa5572b9f06aac9363e3320e7dd6108104923906291979bf520bacd20fbe7cc` |
| architecture-2 | 35,110,649 | `3f604c97fedfb30399327842dc86ecbdc937ef209806fb888b019931197debac` |
| architecture-3 | 33,219,917 | `56828f87c71df6e872b65d1bb8a950e7ab8393104f657b095dcfe24647a463ff` |
| still-life-1 | 156,957 | `8a8f5fa4793bb73f2ab86dbe5b2fb0317e99a4e09f81d351234babff6a4bde51` |
| still-life-2 | 193,271 | `80e57776f3db2789ea79c0f30ce88e14aa8357e353a389290525ab4c6b847b2e` |
| still-life-3 | 111,552 | `c247ba0261482698ffc33decfe80958ce75e824610e915d7cce2ef48d9dbe7eb` |

### 4.1 原寸ダウンロード URL

| slot | 原寸 URL |
| --- | --- |
| portrait-1 | <https://upload.wikimedia.org/wikipedia/commons/e/e7/Boy_Face_from_Venezuela.jpg> |
| portrait-2 | <https://upload.wikimedia.org/wikipedia/commons/3/31/My_niece_Julia_full_face%2C_by_Julia_Margaret_Cameron.jpg> |
| portrait-3 | <https://upload.wikimedia.org/wikipedia/commons/6/6b/David_R._Allen_Assistant_Manager_for_Safety_and_Technical_Services_Department_of_Energy_Oak_Ridge_Office_%289364899021%29.jpg> |
| landscape-1 | <https://upload.wikimedia.org/wikipedia/commons/c/cb/Utah_Dunes_Landscape_-_West_Desert_District.jpg> |
| landscape-2 | <https://upload.wikimedia.org/wikipedia/commons/f/fb/Foggy_landscape_in_My%C5%A5a%2C_Hvo%C5%BE%C4%8Fany%2C_Central_Bohemia_%2851867697891%29.jpg> |
| landscape-3 | <https://upload.wikimedia.org/wikipedia/commons/0/04/Foggy_sunrise_%2853068259930%29.jpg> |
| architecture-1 | <https://upload.wikimedia.org/wikipedia/commons/2/23/Canterbury_Cathedral_Tower_Ceiling.jpg> |
| architecture-2 | <https://upload.wikimedia.org/wikipedia/commons/f/f6/St_Marys_Cathedral_Nave_Edinburgh.jpg> |
| architecture-3 | <https://upload.wikimedia.org/wikipedia/commons/8/83/Brick_Wall_Building.jpg> |
| still-life-1 | <https://upload.wikimedia.org/wikipedia/commons/1/1e/Gorgonzola_and_a_pear.jpg> |
| still-life-2 | <https://upload.wikimedia.org/wikipedia/commons/f/ff/Apples_garlic_cloves_still_life.jpg> |
| still-life-3 | <https://upload.wikimedia.org/wikipedia/commons/9/93/Still_life_fruit.jpg> |

## 5. 補足

- portrait-2 は Julia Margaret Cameron（1815–1879）の 1867 年撮影。Commons のテンプレートは `PD-Scan`
  （原著作物が PD-old のためスキャンも PD）。帰属要求なし。
- architecture-3 の author 表記 "Bango Textures" は iso republic 由来の CC0 献納で、Commons 上は `cc-zero`。
- 外部 AI へ送信する際は [quality-and-operations.md](../quality-and-operations.md) 3章に従い不要な EXIF を除去する。

## 6. カバレッジ実測検証（P0-032）

2章の難易度割当は目視によるため、原本画像の輝度統計で裏付けを取り、5 難易度すべてに代表画像が
実在すること（カバレッジ充足）を確認する。

- 測定日: 2026-07-25。対象は 4.1 の原寸を長辺 1024px へ縮小しグレースケール化した画像。
- 指標: **RMS**=輝度標準偏差、**レンジ**=第98−第2百分位、**暗部%**=輝度<0.15 画素率、
  **明部%**=輝度>0.85 画素率、**細線%**=Sobel 勾配>0.12 画素率、**平坦%**=8×8 ブロック標準偏差<0.03 率。
  閾値は 12 枚の相対比較用の便宜値であり、絶対的な難易度基準ではない。

| slot | 平均 | RMS | レンジ | 暗部% | 明部% | 細線% | 平坦% |
| --- | --- | --- | --- | --- | --- | --- | --- |
| portrait-1 | 0.54 | 0.22 | 0.86 | 5.9 | 11.2 | 3.3 | 82.0 |
| portrait-2 | 0.20 | 0.19 | 0.83 | 64.5 | 2.6 | 1.6 | 83.0 |
| portrait-3 | 0.36 | 0.21 | 0.59 | 33.5 | 0.0 | 2.4 | 85.7 |
| landscape-1 | 0.56 | 0.20 | 0.74 | 0.5 | 7.2 | 8.2 | 59.4 |
| landscape-2 | 0.61 | 0.22 | 0.74 | 0.0 | 12.5 | 3.8 | 76.6 |
| landscape-3 | 0.41 | 0.25 | 0.67 | 29.3 | 0.3 | 4.0 | 88.2 |
| architecture-1 | 0.58 | 0.20 | 0.78 | 2.5 | 6.2 | 32.1 | 17.4 |
| architecture-2 | 0.32 | 0.15 | 0.58 | 15.7 | 0.2 | 22.5 | 24.8 |
| architecture-3 | 0.53 | 0.16 | 0.74 | 3.8 | 0.3 | 34.2 | 8.9 |
| still-life-1 | 0.19 | 0.26 | 0.78 | 65.0 | 0.5 | 4.0 | 73.4 |
| still-life-2 | 0.39 | 0.23 | 0.92 | 19.6 | 3.5 | 13.9 | 44.7 |
| still-life-3 | 0.17 | 0.18 | 0.76 | 63.4 | 1.4 | 5.9 | 77.1 |

### 6.1 難易度別の充足判定

- **高コントラスト**: still-life-2（レンジ 0.92 最大）、still-life-1（RMS 0.26 最大・暗部 65%＋明部側 p98 0.78）、
  architecture-1（レンジ 0.78＋強エッジ）。明暗差の大きい画像が複数実在。**充足**。
- **低コントラスト**: architecture-2（RMS 0.15 最小・レンジ 0.58 最狭）、portrait-2（軟調・ソフトフォーカス）。
  レンジの狭い軟調画像が実在。**充足**。
- **細かい輪郭（細線）**: architecture-3（細線 34.2%）、architecture-1（32.1%）、architecture-2（22.5%）、
  still-life-2（13.9%）。細部密度の高い画像が明瞭に上位。**充足**。
- **広い平坦部**: landscape-3（88.2%）、portrait-3（85.7%）、portrait-2（83.0%）、portrait-1（82.0%）。
  平坦率が高く、architecture 系（8.9〜24.8%）と明確に対照。**充足**。
- **逆光**: landscape-3（暗部 29.3% のシルエット）、architecture-2（暗い内部＋奥の明窓）、
  landscape-1（低斜光）。**充足**（下記の測定上の限界に留意）。

### 6.2 測定上の注意

- **逆光**は主要被写体の暗部と背後光源の明部が併存する局所現象で、全画素統計（暗部%・明部%）には
  弱くしか現れない。難易度としては構図（landscape-3 の逆光シルエット、architecture-2 の明窓）で担保し、
  実測は補助指標とする。landscape-3 が暗部シルエット最明瞭。
- **landscape-2** の霧の軟調さは大気遠近による局所コントラスト低下で、全体 RMS（0.22）には出にくい。
  低コントラストの代表的裏付けは architecture-2・portrait-2 のレンジ狭のほうが明瞭。2章の landscape-2 の
  低コントラスト割当は構図的性質として維持する。

判定: 5 難易度すべてに実データで裏付く代表画像が存在し、2章の割当と整合。カバレッジは充足。

## 7. 次工程

- **P0-031（完了）**: 原本ハッシュ（SHA-256）は 4 章、権利状態（ライセンス）・主要構図・難易度は 3 章に確定記録した。
- **P0-032（完了）**: 高低コントラスト・細線・平坦部・逆光のカバレッジ充足を原本の輝度統計で確認した（6章）。
