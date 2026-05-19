from __future__ import annotations

import argparse
import json
from pathlib import Path

from backup_core import BackupService
from project_config import default_items


def main() -> int:
    parser = argparse.ArgumentParser(description="AI配置备份助手命令行入口")
    sub = parser.add_subparsers(dest="command", required=True)

    backup = sub.add_parser("backup", help="创建备份快照")
    backup.add_argument("--backup-root", required=True)
    backup.add_argument("--items", required=True, help="用逗号分隔的备份项目名称")

    scheduled = sub.add_parser("scheduled-backup", help="按 data/schedule.json 创建备份快照")
    scheduled.add_argument("--config", default=str(Path(__file__).with_name("data") / "schedule.json"))

    args = parser.parse_args()
    if args.command == "backup":
        backup_root = Path(args.backup_root)
        selected_names = {name.strip() for name in args.items.split(",") if name.strip()}
        return run_backup(backup_root, selected_names)
    if args.command == "scheduled-backup":
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"计划配置不存在：{config_path}")
            return 2
        config = json.loads(config_path.read_text(encoding="utf-8"))
        return run_backup(Path(config["backup_root"]), set(config["items"]))
    return 1


def run_backup(backup_root: Path, selected_names: set[str]) -> int:
    items = [item for item in default_items(Path.home()) if item.name in selected_names and item.source.exists()]
    if not items:
        print("没有可备份的项目")
        return 2
    service = BackupService(backup_root)
    result = service.create_snapshot(items)
    print(f"备份完成：{result.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
