"""キャッシュキーの導出と、キー由来の配置・再利用の検証。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from optpoet.errors import ArtifactCorruptedError, StorageError
from optpoet.hashing import hash_bytes, short_id
from optpoet.storage import ArtifactCache, ProjectLayout, Stage, cache_key

_INPUT = hash_bytes(b"normalized")
_OTHER = hash_bytes(b"preprocessed")


@pytest.fixture
def cache(tmp_path: Path) -> ArtifactCache:
    layout = ProjectLayout(tmp_path)
    layout.create()
    return ArtifactCache(layout)


_PARAMS: dict[str, Any] = {"method": "mean_luminance", "gamma": 1.0}


def _key(
    *,
    stage: Stage = Stage.DENSITY_MAP,
    stage_version: int = 1,
    inputs: Sequence[str] = (_INPUT,),
    params: Mapping[str, Any] | None = None,
) -> str:
    return cache_key(
        stage,
        stage_version=stage_version,
        inputs=inputs,
        params=_PARAMS if params is None else params,
    )


def test_cache_key_is_stable() -> None:
    assert _key() == _key()


def test_cache_key_param_order_does_not_matter() -> None:
    assert _key(params={"gamma": 1.0, "method": "mean_luminance"}) == _key()


@pytest.mark.parametrize(
    "overrides",
    [
        {"stage": Stage.EDGE_MAP},
        {"stage_version": 2},
        {"inputs": [_OTHER]},
        {"inputs": [_INPUT, _OTHER]},
        {"params": {"method": "mean_luminance", "gamma": 1.2}},
    ],
)
def test_cache_key_changes_with_inputs(overrides: dict[str, Any]) -> None:
    """前段・工程版・パラメータが変われば別キーになる（無効化の伝播）。"""
    assert _key(**overrides) != _key()


def test_cache_key_keeps_input_order() -> None:
    assert _key(inputs=[_OTHER, _INPUT]) != _key(inputs=[_INPUT, _OTHER])


def test_cache_key_rejects_bad_stage_version() -> None:
    with pytest.raises(StorageError, match="stage_version は 1 以上"):
        _key(stage_version=0)


def test_cache_key_rejects_non_hash_input() -> None:
    with pytest.raises(StorageError, match="内容ハッシュ"):
        _key(inputs=["9f2c4ab1"])


def test_path_for_uses_short_id(cache: ArtifactCache) -> None:
    key = _key()
    path = cache.path_for(Stage.DENSITY_MAP, key, "npy")
    assert path == cache.layout.density_dir / f"{short_id(key)}.npy"


def test_path_for_accepts_dotted_extension(cache: ArtifactCache) -> None:
    key = _key()
    assert cache.path_for(Stage.DENSITY_MAP, key, ".npy").suffix == ".npy"


@pytest.mark.parametrize("extension", ["NPY", "np y", "npy/", "", "n*y"])
def test_path_for_rejects_bad_extension(cache: ArtifactCache, extension: str) -> None:
    with pytest.raises(StorageError, match="拡張子"):
        cache.path_for(Stage.DENSITY_MAP, _key(), extension)


@pytest.mark.parametrize(
    ("stage", "expected"),
    [
        (Stage.NORMALIZE, "derived/normalized"),
        (Stage.PREPROCESS, "derived/preprocessed"),
        (Stage.DENSITY_MAP, "derived/density"),
        (Stage.EDGE_MAP, "derived/density"),
        (Stage.DICTIONARY, "derived/dictionary"),
        (Stage.OPTIMIZE, "trace"),
    ],
)
def test_stage_dir(cache: ArtifactCache, stage: Stage, expected: str) -> None:
    assert cache.layout.relative(cache.stage_dir(stage)) == expected


def test_render_has_no_cache_dir(cache: ArtifactCache) -> None:
    """出力は固定名で、manifest の hash で追跡する。"""
    with pytest.raises(StorageError, match="固定名"):
        cache.stage_dir(Stage.RENDER)


def test_store_writes_and_reports_ref(cache: ArtifactCache) -> None:
    key = _key()
    entry = cache.store(Stage.DENSITY_MAP, key, "npy", b"density")
    assert entry.path.read_bytes() == b"density"
    assert entry.relative_path == f"derived/density/{short_id(key)}.npy"
    assert entry.hash == hash_bytes(b"density")


def test_lookup_returns_none_when_absent(cache: ArtifactCache) -> None:
    assert cache.lookup(Stage.DENSITY_MAP, _key(), "npy") is None


def test_lookup_reuses_existing(cache: ArtifactCache) -> None:
    key = _key()
    stored = cache.store(Stage.DENSITY_MAP, key, "npy", b"density")
    found = cache.lookup(Stage.DENSITY_MAP, key, "npy", expected_hash=stored.hash)
    assert found == stored


def test_lookup_reports_corruption(cache: ArtifactCache) -> None:
    """実体はあるが hash が合わない場合は破損として報告し、再生成しない（I-02）。"""
    key = _key()
    stored = cache.store(Stage.DENSITY_MAP, key, "npy", b"density")
    stored.path.write_bytes(b"tampered")
    with pytest.raises(ArtifactCorruptedError, match="記録と一致しない"):
        cache.lookup(Stage.DENSITY_MAP, key, "npy", expected_hash=stored.hash)


def test_store_does_not_overwrite_same_content(cache: ArtifactCache) -> None:
    key = _key()
    first = cache.store(Stage.DENSITY_MAP, key, "npy", b"density")
    second = cache.store(Stage.DENSITY_MAP, key, "npy", b"density")
    assert first == second


def test_store_rejects_same_key_with_other_content(cache: ArtifactCache) -> None:
    """同一キーで内容が違うのは衝突か stage_version の上げ忘れ。"""
    key = _key()
    cache.store(Stage.DENSITY_MAP, key, "npy", b"density")
    with pytest.raises(ArtifactCorruptedError, match="内容が異なる"):
        cache.store(Stage.DENSITY_MAP, key, "npy", b"other")


def test_store_creates_missing_dir(tmp_path: Path) -> None:
    cache = ArtifactCache(ProjectLayout(tmp_path))
    entry = cache.store(Stage.DICTIONARY, _key(), "json", b"{}")
    assert entry.path.is_file()


def test_request_and_response_paths(cache: ArtifactCache) -> None:
    request_hash = hash_bytes(b"request")
    stem = short_id(request_hash)
    assert cache.request_path(request_hash).name == f"{stem}.req.json"
    assert cache.response_path(request_hash, 1).name == f"{stem}.a1.res.json"
    assert cache.response_path(request_hash, 2).name == f"{stem}.a2.res.json"


def test_response_path_requires_attempt(cache: ArtifactCache) -> None:
    with pytest.raises(StorageError, match="試行連番"):
        cache.response_path(hash_bytes(b"request"), 0)
