"""project manifest の読込・検証・保存（P1-002）。"""

from optpoet.manifest.invariants import MANUAL_SOURCE, check_invariants
from optpoet.manifest.store import LoadedManifest, load_manifest, save_manifest
from optpoet.manifest.validate import validate_manifest
from optpoet.manifest.version import APP_SCHEMA_VERSION, SchemaVersion, is_read_only

__all__ = [
    "APP_SCHEMA_VERSION",
    "MANUAL_SOURCE",
    "LoadedManifest",
    "SchemaVersion",
    "check_invariants",
    "is_read_only",
    "load_manifest",
    "save_manifest",
    "validate_manifest",
]
