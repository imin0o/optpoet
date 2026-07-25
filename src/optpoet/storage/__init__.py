"""成果物の配置、内容ハッシュによる ID、キャッシュ領域。

docs/decisions/artifact-storage.md の実装。
"""

from optpoet.storage.atomic import atomic_write, replace, sync_dir, write_and_sync
from optpoet.storage.cache import ArtifactCache, CacheEntry, Stage, cache_key
from optpoet.storage.layout import (
    INDEX_NAME,
    MANIFEST_BACKUP_NAME,
    MANIFEST_NAME,
    OUTPUT_PNG_NAME,
    OUTPUT_TXT_NAME,
    ProjectLayout,
    relative_path_error,
)
from optpoet.storage.refs import iter_refs, verify_ref, verify_refs

__all__ = [
    "INDEX_NAME",
    "MANIFEST_BACKUP_NAME",
    "MANIFEST_NAME",
    "OUTPUT_PNG_NAME",
    "OUTPUT_TXT_NAME",
    "ArtifactCache",
    "CacheEntry",
    "ProjectLayout",
    "Stage",
    "atomic_write",
    "cache_key",
    "iter_refs",
    "relative_path_error",
    "replace",
    "sync_dir",
    "verify_ref",
    "verify_refs",
    "write_and_sync",
]
