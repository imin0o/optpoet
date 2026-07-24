# 参照 PC 構成

**状態**: 記録済み（2026-07-25 実測）
**目的**: 性能ベースライン（P0-015）、描画整合スパイク（P0-014）、再現性検証を行う基準ハードウェア・OS 構成を固定する。
**対象タスク**: [P0-010](../roadmap/phase-0.md)
**関連**: [requirements.md](../requirements.md)、[quality-and-operations.md](../quality-and-operations.md)、[ROADMAP](../roadmap/phase-0.md)

本書は optpoet の測定・スパイク結果が「どの環境で得られたか」を明示するための正規記録である。測定値を引用する文書は、環境差を判断できるよう本書の版を参照する。

## 記録方針

- 参照 PC は開発兼検証機を 1 台固定し、その実測構成を記録する。
- 数値は取得日時点の実測とし、更新時は日付と変更点を「更新履歴」に残す。
- 本書はハードウェア・OS の基準を記録する。Python・ライブラリの版は [P0-011](../roadmap/phase-0.md)、フォントは [P0-012](../roadmap/phase-0.md)、描画エンジンは [P0-013](../roadmap/phase-0.md) で別途決定・記録する。

## 参照構成（実測: 2026-07-25）

| 項目 | 値 | 備考 |
| --- | --- | --- |
| OS | Windows 11 Pro | 64bit |
| OS バージョン | 10.0.26200（Build 26200） | — |
| CPU | AMD Ryzen 9 7900X3D | 12 コア / 24 スレッド |
| メモリ | 64 GB（実測 63.1 GB 認識） | — |
| GPU（dGPU） | NVIDIA GeForce RTX 4070 Ti SUPER | VRAM 16 GB（16376 MiB）、Driver 610.62 |
| GPU（iGPU） | AMD Radeon Graphics（Ryzen 内蔵） | — |
| ロケール | ja-JP | — |
| タイムゾーン | Tokyo Standard Time (JST, UTC+9) | — |

### 参考: 現状インストール済みツールチェーン

版の決定は P0-011 で行う。以下は取得時点のスナップショットであり、参照構成の基準値ではない。

| 項目 | 値 | 備考 |
| --- | --- | --- |
| Python | 3.14.3 | `C:\Python314\python.exe`、`py` ランチャー併用 |

## 測定時の注意

- WMI（`Win32_VideoController.AdapterRAM`）は 32bit DWORD 上限により VRAM を 4 GB と誤報告する。VRAM は `nvidia-smi` の実測値（16 GB）を正とする。
- dGPU / iGPU が併存するため、描画エンジンやライブラリが使用する GPU を測定ごとに固定・記録する（P0-013 / P0-014 / P0-015 で明示）。
- ストレージは複数ドライブ構成のため、生成物・キャッシュの配置ドライブを [P0-041](../roadmap/phase-0.md) の定義に従い測定時に記録する。

## 更新履歴

| 日付 | 変更点 |
| --- | --- |
| 2026-07-25 | 初版。参照 PC 構成を実測記録。 |
