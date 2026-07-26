"""optpoet — 光学的韻律を持つ画像詩生成システム。"""

from optpoet.config import AppConfig, load_config
from optpoet.errors import (
    ArtifactCorruptedError,
    ConfigError,
    ErrorKind,
    FailureClass,
    ManifestError,
    OptpoetError,
    SaveAbortedError,
    StageCancelledError,
    StageError,
    StorageError,
    error_kind,
)
from optpoet.hashing import canonical_json, hash_bytes, hash_file, hash_json
from optpoet.manifest import LoadedManifest, load_manifest, save_manifest, validate_manifest
from optpoet.pipeline import (
    CancelToken,
    ProgressEvent,
    ProgressSink,
    StageProgress,
    StageStatus,
    run_stage,
)
from optpoet.project import OpenedProject, OpenMode, SaveResult, open_project, save_project
from optpoet.storage import ArtifactCache, CacheEntry, ProjectLayout, Stage, cache_key, verify_refs

__version__ = "0.1.0"

__all__ = [
    "AppConfig",
    "ArtifactCache",
    "ArtifactCorruptedError",
    "CacheEntry",
    "CancelToken",
    "ConfigError",
    "ErrorKind",
    "FailureClass",
    "LoadedManifest",
    "ManifestError",
    "OpenMode",
    "OpenedProject",
    "OptpoetError",
    "ProgressEvent",
    "ProgressSink",
    "ProjectLayout",
    "SaveAbortedError",
    "SaveResult",
    "Stage",
    "StageCancelledError",
    "StageError",
    "StageProgress",
    "StageStatus",
    "StorageError",
    "__version__",
    "cache_key",
    "canonical_json",
    "error_kind",
    "hash_bytes",
    "hash_file",
    "hash_json",
    "load_config",
    "load_manifest",
    "open_project",
    "run_stage",
    "save_manifest",
    "save_project",
    "validate_manifest",
    "verify_refs",
]
