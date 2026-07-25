"""プロジェクト単位の保存とオープン。

docs/decisions/save-and-migration.md の実装。低レベルの配置は `optpoet.storage`、manifest
の構造検証は `optpoet.manifest` が担い、本パッケージは両者を手順として組み立てる。
"""

from optpoet.project.load import OpenedProject, OpenMode, open_project
from optpoet.project.save import SaveResult, save_project

__all__ = [
    "OpenMode",
    "OpenedProject",
    "SaveResult",
    "open_project",
    "save_project",
]
