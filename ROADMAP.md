# ROADMAP

本ファイルは全体進捗の索引である。実作業は各 Phase ファイルのチェックボックスで管理する。
機能境界は [docs/requirements.md](docs/requirements.md)、合格基準は
[docs/quality-and-operations.md](docs/quality-and-operations.md) を正とする。

## チェックボックス運用

- `[ ]`: 未完了。着手中は行末に `（進行中）` を付ける。
- `[x]`: 成果物と検証結果が残り、Phase の完了条件を満たした。
- タスクを追加・分割しても ID は再利用しない。
- Phase の完了チェックは、各ファイル末尾の完了ゲートがすべて `[x]` になった後に更新する。
- 要件変更が必要な場合は、実装より先に正規文書を更新する。

## 全体進捗

- [ ] [Phase 0: 要件と検証基盤](docs/roadmap/phase-0.md)
- [ ] [Phase 1: 文字による画像再現](docs/roadmap/phase-1.md)
- [ ] [Phase 2: 写真説明文と散文詩](docs/roadmap/phase-2.md)
- [ ] [Phase 3: 光学的韻律と簡易カットアップ](docs/roadmap/phase-3.md)
- [ ] **MVP リリース判定** — Phase 0〜2 と Phase 3 の MVP 範囲を完了
- [ ] [Phase 4: 領域と意味の対応](docs/roadmap/phase-4.md)
- [ ] [Phase 5: 展示システム](docs/roadmap/phase-5.md)

## 依存関係

```text
Phase 0
  └─ Phase 1
       └─ Phase 2
            └─ Phase 3 ── MVP
                 └─ Phase 4
                      └─ Phase 5
```

Phase 1 の画像・フォント・描画基盤を固定してから AI 生成を接続する。Phase 2 では自然な記述と散文詩を
成立させ、Phase 3 で意図的な破綻と書体リズムを追加する。Phase 4、5 は MVP 後である。

## MVP リリース条件

- [ ] Phase 0〜2 の完了ゲートがすべて通過している。
- [ ] Phase 3 の「MVP 必須」タスクと対応ゲートが完了している。
- [ ] 固定 12 画像で AC-01〜AC-07 の検証記録がある。
- [ ] 記述、散文詩、簡易カットアップの人間評価が暫定基準を満たす。
- [ ] 重大な権利、プライバシー、秘密情報漏えい、データ消失の既知問題が 0 件である。
- [ ] 既知の制限、参照環境、外部 AI 条件、再生方法が README から辿れる。
