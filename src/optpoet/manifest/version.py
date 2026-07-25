"""manifest スキーマ版と読取モードの判定。

規則は docs/decisions/project-manifest.md「スキーマ版規則」に従う。

- 同一 MAJOR かつ MINOR がアプリ以下: 通常読込
- 同一 MAJOR で MINOR がアプリより新しい: 読取専用オープン（未知項目を保持し保存しない）
- 異なる MAJOR: 明示エラー（I-01。暗黙解釈・部分読込をしない）
"""

from __future__ import annotations

from dataclasses import dataclass

from optpoet.errors import ManifestError, ManifestSchemaVersionError


@dataclass(frozen=True, slots=True, order=True)
class SchemaVersion:
    """`MAJOR.MINOR` 形式のスキーマ版。"""

    major: int
    minor: int

    @classmethod
    def parse(cls, value: object) -> SchemaVersion:
        if not isinstance(value, str):
            raise ManifestError(f"manifest.schema_version は文字列: {value!r}")
        parts = value.split(".")
        if len(parts) != 2 or not all(p.isascii() and p.isdigit() for p in parts):
            raise ManifestError(f"manifest.schema_version は MAJOR.MINOR 形式: {value!r}")
        return cls(int(parts[0]), int(parts[1]))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}"


# MVP 出荷時の初期版。Phase 1 中の追加は MINOR で上げる。
APP_SCHEMA_VERSION = SchemaVersion(1, 0)


def is_read_only(version: SchemaVersion) -> bool:
    """読取専用オープンが必要かを返す。未知 MAJOR は例外にする（I-01）。"""
    if version.major != APP_SCHEMA_VERSION.major:
        raise ManifestSchemaVersionError(
            f"未知のスキーマ MAJOR 版: {version}（対応: {APP_SCHEMA_VERSION}）"
        )
    return version.minor > APP_SCHEMA_VERSION.minor
