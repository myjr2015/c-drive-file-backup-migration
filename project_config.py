from __future__ import annotations

import json
from pathlib import Path

from backup_core import BackupItem


APP_TITLE = "Ai会话备份"
APP_VERSION = "1.1.0"
APP_ICON_PATH = Path("assets/app.ico")
GITHUB_REPOSITORY = "myjr2015/ai-session-backup"
SCHEDULE_TASK_NAME = "Ai会话备份-定时备份"
DEFAULT_BACKUP_ROOT = Path(r"D:\code\backup")
FALLBACK_DOT_FOLDER_NAMES = [".claude", ".codex", ".happy", ".ssh"]
LEGACY_FIXED_DEFAULT_ITEM_NAMES = {
    ".happy",
    ".codex",
    ".claude",
    ".ssh",
    ".gitconfig",
    "AppData/Roaming/npm",
    "AppData/Roaming/npm-cache",
}


def load_config(config_path: Path | None = None) -> dict:
    path = config_path or Path(__file__).with_name("config.json")
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def get_backup_root(config: dict, user_settings: dict | None = None) -> Path:
    settings = user_settings or {}
    return Path(settings.get("backup_root") or config.get("backup_root") or config.get("默认备份目录") or DEFAULT_BACKUP_ROOT)


def default_items(home: Path) -> list[BackupItem]:
    return _dot_folder_items(home)


def _dot_folder_items(home: Path) -> list[BackupItem]:
    try:
        folders = sorted(
            path
            for path in home.iterdir()
            if path.is_dir() and path.name.startswith(".")
        )
    except OSError:
        folders = []
    if not folders:
        folders = [home / name for name in FALLBACK_DOT_FOLDER_NAMES]
    return [BackupItem(path.name, path) for path in folders]


def build_backup_items(home: Path, custom_items: list[dict] | None = None) -> list[BackupItem]:
    items = default_items(home)
    existing_names = {item.name for item in items}
    for raw_item in custom_items or []:
        item = build_custom_item(raw_item, existing_names)
        if item is None:
            continue
        existing_names.add(item.name)
        items.append(item)
    return items


def is_legacy_fixed_default_selection(selected_names: set[str]) -> bool:
    return (
        bool(selected_names)
        and selected_names <= LEGACY_FIXED_DEFAULT_ITEM_NAMES
        and bool(selected_names & {".gitconfig", "AppData/Roaming/npm", "AppData/Roaming/npm-cache"})
    )


def build_custom_item(raw_item: dict, existing_names: set[str] | None = None) -> BackupItem | None:
    path_text = str(raw_item.get("path", "")).strip()
    if not path_text:
        return None
    source = Path(path_text)
    display_name = str(raw_item.get("name", "")).strip() or source.name or "自定义项目"
    safe_name = _safe_custom_name(display_name)
    name = f"自定义/{safe_name}"
    if existing_names and name in existing_names:
        index = 2
        while f"{name}-{index}" in existing_names:
            index += 1
        name = f"{name}-{index}"
    return BackupItem(
        name=name,
        source=source,
        sensitive=bool(raw_item.get("sensitive", True)),
        restore_target=source,
    )


def custom_item_payload(item: BackupItem) -> dict:
    display_name = item.name.split("/", 1)[1] if item.name.startswith("自定义/") else item.name
    return {
        "name": display_name,
        "path": str(item.restore_target or item.source),
        "sensitive": item.sensitive,
    }


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


def _safe_custom_name(name: str) -> str:
    forbidden = '<>:"\\|?*'
    cleaned = "".join("_" if char in forbidden else char for char in name).strip().strip(".")
    return cleaned or "自定义项目"
