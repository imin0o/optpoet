"""P1 完了ゲートの固定資産を取得し、ハッシュで同一バイトを確認する。

実行: `python gates/p1/fetch_assets.py`

取得物は `gates/p1/assets/` へ置き、リポジトリへは含めない（原本の再配布を避けるため）。
既に同じハッシュのファイルがあれば再取得しない。
"""

from __future__ import annotations

import hashlib
import io
import re
import sys
import time
import unicodedata
import urllib.request
import zipfile

from dataset import (
    IMAGE_DIR,
    IMAGES,
    OVERSIZED,
    TEXT,
    TEXT_BODY_SHA256,
    TEXT_DIR,
    USER_AGENT,
    ImageAsset,
)

_RUBY = re.compile(r"《[^》]*》")
_ANNOTATION = re.compile(r"［＃[^］]*］")
_SEPARATOR = re.compile(r"^-{10,}$")
_COLOPHON = "底本："


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(url: str, *, attempts: int = 5) -> bytes:
    """固定 https URL を取得する。429 / 5xx は待って再試行する。"""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    wait = 5.0
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                data: bytes = response.read()
            return data
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == attempts:
                raise
            print(f"    HTTP {exc.code}: {wait:.0f} 秒待って再試行 ({attempt}/{attempts})")
            time.sleep(wait)
            wait *= 2
    raise SystemExit(f"取得に失敗: {url}")


def fetch_image(asset: ImageAsset) -> str:
    """画像を取得（または再利用）し、実測ハッシュを返す。"""
    if asset.path.is_file():
        digest = sha256_of(asset.path.read_bytes())
        if digest == asset.sha256:
            return "reuse"
        print(f"  既存ファイルのハッシュ不一致のため再取得: {digest}")
    data = download(asset.url)
    digest = sha256_of(data)
    if digest != asset.sha256 or len(data) != asset.size:
        raise SystemExit(
            f"{asset.slot}: 原本と不一致。"
            f"期待 {asset.sha256} / {asset.size}B、実測 {digest} / {len(data)}B"
        )
    asset.path.write_bytes(data)
    return "fetch"


def clean_aozora(raw: str) -> str:
    """青空文庫テキストから本文だけを取り出す。

    ヘッダ（凡例ブロック）と底本以降を落とし、ルビ `《…》`、ルビ開始記号 `｜`、
    注記 `［＃…］` を除く。改行は LF へ揃え、NFC 正規化する。
    """
    lines = raw.replace("\r\n", "\n").split("\n")
    separators = [i for i, line in enumerate(lines) if _SEPARATOR.match(line.strip())]
    start = separators[1] + 1 if len(separators) >= 2 else 1
    end = len(lines)
    for i in range(start, len(lines)):
        if lines[i].startswith(_COLOPHON):
            end = i
            break
    body = "\n".join(lines[start:end])
    body = _RUBY.sub("", body)
    body = _ANNOTATION.sub("", body)
    body = body.replace("｜", "")
    return unicodedata.normalize("NFC", body).strip() + "\n"


def fetch_text() -> tuple[str, str]:
    """入力文を取得（または再利用）し、(zip ハッシュ, 本文ハッシュ) を返す。"""
    if TEXT.archive.is_file():
        archive = TEXT.archive.read_bytes()
    else:
        archive = download(TEXT.url)
        TEXT.archive.write_bytes(archive)
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".txt")]
        if len(names) != 1:
            raise SystemExit(f"zip 内の txt が 1 件ではない: {names}")
        raw = zf.read(names[0]).decode("cp932")
    archive_hash = sha256_of(archive)
    if TEXT.sha256 and archive_hash != TEXT.sha256:
        raise SystemExit(f"入力文の zip が原本と不一致: 期待 {TEXT.sha256}、実測 {archive_hash}")
    body = clean_aozora(raw)
    TEXT.path.write_text(body, encoding="utf-8", newline="\n")
    body_hash = sha256_of(body.encode("utf-8"))
    if TEXT_BODY_SHA256 and body_hash != TEXT_BODY_SHA256:
        raise SystemExit(f"整形後の本文が記録と不一致: 期待 {TEXT_BODY_SHA256}、実測 {body_hash}")
    return archive_hash, body_hash


def main() -> int:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"画像 {len(IMAGES)} 枚")
    for index, asset in enumerate(IMAGES, start=1):
        action = fetch_image(asset)
        print(f"  [{index:2d}/{len(IMAGES)}] {asset.slot:<15} {action} {asset.size:>10,}B")
        if action == "fetch" and index < len(IMAGES):
            time.sleep(5.0)  # 連続取得の間隔（validation-dataset.md 4 章）

    action = fetch_image(OVERSIZED)
    print(f"  [上限超過] {OVERSIZED.slot:<15} {action} {OVERSIZED.size:>10,}B")

    archive_hash, body_hash = fetch_text()
    body = TEXT.path.read_text(encoding="utf-8")
    print(f"入力文 {TEXT.author}『{TEXT.title}』")
    print(f"  zip sha256 : {archive_hash}")
    print(f"  本文 sha256: {body_hash}")
    print(f"  本文文字数 : {len(body):,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
