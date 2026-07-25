"""optpoet — 光学的韻律を持つ画像詩生成システム。"""

from optpoet.config import AppConfig, load_config
from optpoet.errors import (
    ArtifactCorruptedError,
    ConfigError,
    ManifestError,
    OptpoetError,
    SaveAbortedError,
    StorageError,
)
from optpoet.hashing import canonical_json, hash_bytes, hash_file, hash_json
from optpoet.manifest import LoadedManifest, load_manifest, save_manifest, validate_manifest
from optpoet.project import OpenedProject, OpenMode, SaveResult, open_project, save_project
from optpoet.storage import ArtifactCache, CacheEntry, ProjectLayout, Stage, cache_key, verify_refs

__version__ = "0.1.0"

__all__ = [
    "AppConfig",
    "ArtifactCache",
    "ArtifactCorruptedError",
    "CacheEntry",
    "ConfigError",
    "LoadedManifest",
    "ManifestError",
    "OpenMode",
    "OpenedProject",
    "OptpoetError",
    "ProjectLayout",
    "SaveAbortedError",
    "SaveResult",
    "Stage",
    "StorageError",
    "__version__",
    "cache_key",
    "canonical_json",
    "hash_bytes",
    "hash_file",
    "hash_json",
    "load_config",
    "load_manifest",
    "open_project",
    "save_manifest",
    "save_project",
    "validate_manifest",
    "verify_refs",
]
