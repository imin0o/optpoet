"""プロジェクトディレクトリ構成と相対 POSIX パス。

docs/decisions/artifact-storage.md「ディレクトリ構成」「ファイル命名」に従う。
プロジェクトは 1 ディレクトリを単位とし、再読込・再生に必要な実体をすべてその中に置く。

原子的保存は `.tmp/` を経由して `manifest.json` を 1 回置換する（`optpoet.project.save`）。
本モジュールは `.tmp/` の位置、残留物の破棄、直前の有効版の退避先だけを決める。
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from optpoet.errors import StorageError

MANIFEST_NAME = "manifest.json"
MANIFEST_BACKUP_NAME = "manifest.bak.json"
INDEX_NAME = "index.sqlite"
OUTPUT_PNG_NAME = "artwork.png"
OUTPUT_TXT_NAME = "artwork.txt"

_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")


def relative_path_error(value: str) -> str | None:
    """相対 POSIX パス（manifest I-07）に反する理由を返す。問題なければ None。

    例外型は用途で異なる（manifest 検証は ManifestError、配置は StorageError）ため、
    ここでは理由の文字列だけを返す。
    """
    if not value:
        return "が空"
    if value.startswith(("/", "\\", "~")) or _DRIVE_PREFIX.match(value):
        return f"は相対パスである必要がある（I-07）: {value!r}"
    if "\\" in value:
        # 区切りは POSIX の `/` 固定。Windows でも `\` を保存しない。
        return f"の区切りは / である必要がある（I-07）: {value!r}"
    parts = value.split("/")
    if ".." in parts or "" in parts:
        return f"が不正な要素を含む（I-07）: {value!r}"
    return None


@dataclass(frozen=True, slots=True)
class ProjectLayout:
    """プロジェクトルートと配下の固定ディレクトリ。"""

    root: Path

    @property
    def manifest_path(self) -> Path:
        return self.root / MANIFEST_NAME

    @property
    def manifest_backup_path(self) -> Path:
        """直前の有効版の退避先。1 世代のみ保持する（A-07）。"""
        return self.root / MANIFEST_BACKUP_NAME

    @property
    def index_path(self) -> Path:
        """manifest から再構築できる派生。索引を正とみなさない。"""
        return self.root / INDEX_NAME

    @property
    def input_dir(self) -> Path:
        """原本画像の複製。外部パスへ依存しないため原本を取り込む。"""
        return self.root / "input"

    @property
    def normalized_dir(self) -> Path:
        return self.root / "derived" / "normalized"

    @property
    def preprocessed_dir(self) -> Path:
        return self.root / "derived" / "preprocessed"

    @property
    def density_dir(self) -> Path:
        return self.root / "derived" / "density"

    @property
    def dictionary_dir(self) -> Path:
        """文字密度辞書の正本。共有キャッシュはこの複製にすぎない。"""
        return self.root / "derived" / "dictionary"

    @property
    def requests_dir(self) -> Path:
        return self.root / "ai" / "requests"

    @property
    def responses_dir(self) -> Path:
        return self.root / "ai" / "responses"

    @property
    def prompts_dir(self) -> Path:
        return self.root / "ai" / "prompts"

    @property
    def text_dir(self) -> Path:
        return self.root / "text"

    @property
    def trace_dir(self) -> Path:
        return self.root / "trace"

    @property
    def outputs_dir(self) -> Path:
        return self.root / "outputs"

    @property
    def tmp_dir(self) -> Path:
        """書込み中の一時ファイル置き場。同一ボリュームに置く（P1-004）。"""
        return self.root / ".tmp"

    @property
    def output_png_path(self) -> Path:
        return self.outputs_dir / OUTPUT_PNG_NAME

    @property
    def output_txt_path(self) -> Path:
        return self.outputs_dir / OUTPUT_TXT_NAME

    def all_dirs(self) -> tuple[Path, ...]:
        return (
            self.input_dir,
            self.normalized_dir,
            self.preprocessed_dir,
            self.density_dir,
            self.dictionary_dir,
            self.requests_dir,
            self.responses_dir,
            self.prompts_dir,
            self.text_dir,
            self.trace_dir,
            self.outputs_dir,
            self.tmp_dir,
        )

    def create(self) -> None:
        """構成ディレクトリを作る。既存なら何もしない。"""
        for directory in self.all_dirs():
            directory.mkdir(parents=True, exist_ok=True)

    def clear_tmp(self) -> None:
        """`.tmp/` の残留物を破棄する。対象は `.tmp/` 直下に限る。"""
        if not self.tmp_dir.is_dir():
            return
        for entry in self.tmp_dir.iterdir():
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()

    def relative(self, path: Path) -> str:
        """manifest へ書ける相対 POSIX パスへ変換する。ルート外は拒否する。"""
        target = path if path.is_absolute() else self.root / path
        try:
            relative = target.resolve().relative_to(self.root.resolve())
        except ValueError as exc:
            raise StorageError(f"プロジェクトルート外の実体は参照できない: {path}") from exc
        text = relative.as_posix()
        if text == ".":
            raise StorageError("プロジェクトルート自体は ref にできない")
        reason = relative_path_error(text)
        if reason is not None:
            raise StorageError(f"相対パス {reason}")
        return text

    def resolve(self, relative: str) -> Path:
        """manifest の相対 POSIX パスを実パスへ戻す。"""
        reason = relative_path_error(relative)
        if reason is not None:
            raise StorageError(f"manifest の path {reason}")
        return self.root.joinpath(*relative.split("/"))
