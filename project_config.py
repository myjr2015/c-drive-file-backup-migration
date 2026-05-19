from __future__ import annotations

import json
from pathlib import Path

from backup_core import BackupItem


APP_TITLE = "AI配置备份助手"
SCHEDULE_TASK_NAME = "AI配置备份助手-定时备份"
DEFAULT_BACKUP_ROOT = Path(r"D:\code\DaiMa\#全局备份\AI会话备份")


def load_config(config_path: Path | None = None) -> dict:
    path = config_path or Path(__file__).with_name("config.json")
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def get_backup_root(config: dict) -> Path:
    return Path(config.get("backup_root") or config.get("默认备份目录") or DEFAULT_BACKUP_ROOT)


def default_items(home: Path) -> list[BackupItem]:
    roaming = home / "AppData" / "Roaming"
    return [
        BackupItem(".happy", home / ".happy"),
        BackupItem(".codex", home / ".codex"),
        BackupItem(".claude", home / ".claude"),
        BackupItem(".ssh", home / ".ssh"),
        BackupItem(".gitconfig", home / ".gitconfig"),
        BackupItem("AppData/Roaming/npm", roaming / "npm", sensitive=False),
        BackupItem("AppData/Roaming/npm-cache", roaming / "npm-cache", sensitive=False),
    ]


def sensitive_item_names(items: list[BackupItem]) -> list[str]:
    return [item.name for item in items if item.sensitive]


def build_sensitive_backup_warning(items: list[BackupItem]) -> str:
    names = sensitive_item_names(items)
    if not names:
        return ""
    return (
        "注意：以下项目会按原目录明文备份，可能包含 token、SSH 私钥或 AI 会话认证信息：\n"
        f"{', '.join(names)}\n\n"
        "请确认备份目录位于可信磁盘，不要把快照目录直接上传到公开位置。"
    )
