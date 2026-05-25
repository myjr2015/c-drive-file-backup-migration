from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backup_core import BackupService, load_user_settings
from project_config import APP_TITLE, build_backup_items


def main() -> int:
    parser = argparse.ArgumentParser(description=f"{APP_TITLE}命令行入口")
    sub = parser.add_subparsers(dest="command", required=True)

    backup = sub.add_parser("backup", help="创建备份快照")
    backup.add_argument("--backup-root", required=True)
    backup.add_argument("--items", required=True, help="用逗号分隔的备份项目名称")
    backup.add_argument("--settings", default=str(Path(__file__).with_name("data") / "user-settings.json"), help="用户配置文件路径，用于读取自定义备份项目")

    scheduled = sub.add_parser("scheduled-backup", help="按 data/schedule.json 创建备份快照")
    scheduled.add_argument("--config", default=str(Path(__file__).with_name("data") / "schedule.json"))

    args = parser.parse_args()
    if args.command == "backup":
        backup_root = Path(args.backup_root)
        selected_names = {name.strip() for name in args.items.split(",") if name.strip()}
        return run_backup(backup_root, selected_names, settings_path=Path(args.settings))
    if args.command == "scheduled-backup":
        config_path = Path(args.config)
        if not config_path.exists():
            safe_print(f"计划配置不存在：{config_path}")
            return 2
        config = json.loads(config_path.read_text(encoding="utf-8"))
        return run_backup(Path(config["backup_root"]), set(config["items"]), config.get("custom_items", []))
    return 1


def run_backup(
    backup_root: Path,
    selected_names: set[str],
    custom_items: list[dict] | None = None,
    settings_path: Path | None = None,
) -> int:
    if custom_items is None and settings_path is not None:
        custom_items = load_user_settings(settings_path).get("custom_items", [])
    items = [item for item in build_backup_items(Path.home(), custom_items) if item.name in selected_names and item.source.exists()]
    if not items:
        safe_print("没有可备份的项目")
        return 2
    service = BackupService(backup_root)
    result = service.create_snapshot(items)
    safe_print(f"备份完成：{result.path}")
    return 0


def safe_print(message: str) -> None:
    try:
        print(message)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        safe_message = message.encode(encoding, errors="backslashreplace").decode(encoding, errors="replace")
        print(safe_message)


if __name__ == "__main__":
    raise SystemExit(main())
