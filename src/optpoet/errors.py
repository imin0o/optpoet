"""例外の基底定義。

工程別の構造化エラーは P1-005 で本モジュールを拡張する。
"""

from __future__ import annotations


class OptpoetError(Exception):
    """optpoet が発生させる例外の基底。"""


class ConfigError(OptpoetError):
    """設定値が不正、または設定ファイルを読めない。"""


class ManifestError(OptpoetError):
    """project manifest の構造、または不変条件が不正。"""


class ManifestSchemaVersionError(ManifestError):
    """project manifest のスキーマ版を扱えない（未知 MAJOR）。"""


class StorageError(OptpoetError):
    """成果物の配置、内容ハッシュ、キャッシュキーが不正。"""


class ArtifactCorruptedError(StorageError):
    """実体があるが内容ハッシュが一致しない。暗黙に再生成しない（I-02）。"""


class SaveAbortedError(StorageError):
    """保存を中止した。書きかけの新版ではなく直前の有効版が残る。"""
