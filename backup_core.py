from __future__ import annotations

import fnmatch
import json
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


VOLATILE_DIR_NAMES = {".tmp", "tmp", "__pycache__"}
VOLATILE_FILE_PATTERNS = ["*.sqlite-shm", "*.db-shm", "*.lock"]
INTERNAL_BACKUP_DIR_NAMES = {"restore-backups", "link-store", "link-migration-backups"}


def load_user_settings(config_path: Path) -> dict:
    config_path = Path(config_path)
    if not config_path.exists():
        return {"settings_exists": False, "selected_items": []}
    data = json.loads(config_path.read_text(encoding="utf-8"))
    selected = data.get("selected_items", [])
    if not isinstance(selected, list):
        selected = []
    return {"settings_exists": True, "selected_items": [str(item) for item in selected]}


def write_user_settings(config_path: Path, selected_items: Iterable[str]) -> None:
    config_path = Path(config_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "selected_items": list(selected_items),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


@dataclass(frozen=True)
class BackupItem:
    name: str
    source: Path
    sensitive: bool = True


@dataclass(frozen=True)
class ScannedItem:
    item: BackupItem
    exists: bool
    size_bytes: int
    last_write_time: datetime | None


@dataclass(frozen=True)
class SnapshotResult:
    path: Path
    copied_items: list[str]
    skipped_items: list[str]


@dataclass(frozen=True)
class RestoreResult:
    restored_items: list[str]
    skipped_items: list[str]
    pre_restore_backup_dir: Path


@dataclass(frozen=True)
class LinkMigrationResult:
    link_path: Path
    store_path: Path
    pre_migration_backup_dir: Path


@dataclass(frozen=True)
class SnapshotItem:
    name: str
    source: Path
    sensitive: bool = True
    sensitive_plaintext: bool = True


@dataclass(frozen=True)
class SnapshotDetail:
    path: Path
    created_at: str
    items: list[SnapshotItem]
    available_selected_names: list[str]
    missing_selected_names: list[str]
    error: str = ""


class BackupService:
    def __init__(self, backup_root: Path):
        self.backup_root = Path(backup_root)

    def scan_items(self, items: Iterable[BackupItem]) -> list[ScannedItem]:
        scanned: list[ScannedItem] = []
        for item in items:
            source = Path(item.source)
            exists = source.exists()
            size = self._path_size(source) if exists else 0
            last_write = self._last_write_time(source) if exists else None
            scanned.append(ScannedItem(item, exists, size, last_write))
        return scanned

    def create_snapshot(self, items: Iterable[BackupItem], name: str | None = None) -> SnapshotResult:
        snapshot_name = name or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        snapshot_dir = self._unique_child_path(self.backup_root, snapshot_name)
        snapshot_dir.mkdir(parents=True, exist_ok=False)

        copied: list[str] = []
        skipped: list[str] = []
        manifest_items = []

        try:
            for item in items:
                source = Path(item.source)
                if not source.exists():
                    skipped.append(item.name)
                    continue

                destination = snapshot_dir / item.name
                self._copy_path(source, destination)
                copied.append(item.name)
                manifest_items.append(
                    {
                        "name": item.name,
                        "source": str(source),
                        "sensitive": item.sensitive,
                        "sensitive_plaintext": item.sensitive,
                    }
                )

            manifest = {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "contains_sensitive_plaintext": any(item["sensitive_plaintext"] for item in manifest_items),
                "items": manifest_items,
            }
            (snapshot_dir / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            if snapshot_dir.exists():
                shutil.rmtree(snapshot_dir, ignore_errors=True)
            raise
        return SnapshotResult(snapshot_dir, copied, skipped)

    def restore_snapshot(self, snapshot_dir: Path, target_home: Path, item_names: Iterable[str]) -> RestoreResult:
        snapshot_dir = Path(snapshot_dir)
        target_home = Path(target_home)
        pre_restore_dir = self.backup_root / "restore-backups" / datetime.now().strftime("%Y-%m-%d-%H%M%S")
        pre_restore_dir.mkdir(parents=True, exist_ok=True)

        restored: list[str] = []
        skipped: list[str] = []

        for name in item_names:
            source = snapshot_dir / name
            target = target_home / name
            if not source.exists():
                skipped.append(name)
                continue

            if target.exists():
                self._copy_path(target, pre_restore_dir / name)
                self._remove_path(target)

            self._copy_path(source, target)
            restored.append(name)

        return RestoreResult(restored, skipped, pre_restore_dir)

    def prepare_link_migration(self, item: BackupItem, link_store_root: Path) -> LinkMigrationResult:
        source = Path(item.source)
        if not source.exists():
            raise FileNotFoundError(f"迁移源不存在：{source}")

        link_store_root = Path(link_store_root)
        store_path = link_store_root / item.name
        if store_path.exists():
            raise FileExistsError(f"链接存储目录已存在：{store_path}")

        pre_migration_dir = self.backup_root / "link-migration-backups" / datetime.now().strftime("%Y-%m-%d-%H%M%S")
        pre_migration_dir.mkdir(parents=True, exist_ok=True)
        self._copy_path(source, pre_migration_dir / item.name)

        try:
            store_path.parent.mkdir(parents=True, exist_ok=True)
            self._move_path(source, store_path)
        except Exception:
            if store_path.exists():
                self._remove_path(store_path)
            if not source.exists() and (pre_migration_dir / item.name).exists():
                self._copy_path(pre_migration_dir / item.name, source)
            raise
        return LinkMigrationResult(source, store_path, pre_migration_dir)

    def create_junction(self, link_path: Path, store_path: Path) -> None:
        link_path = Path(link_path)
        store_path = Path(store_path)
        if link_path.exists():
            raise FileExistsError(f"链接位置已存在：{link_path}")
        if not store_path.exists():
            raise FileNotFoundError(f"链接目标不存在：{store_path}")
        import subprocess

        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link_path), str(store_path)],
            check=True,
            capture_output=True,
            text=True,
        )

    def create_scheduled_backup_command(self, launcher: Path, items: Iterable[str], backup_root: Path) -> str:
        item_arg = ",".join(items)
        parts = [
            "python",
            str(launcher),
            "backup",
            "--backup-root",
            str(backup_root),
            "--items",
            item_arg,
        ]
        return " ".join(shlex.quote(part) for part in parts)

    def write_schedule_config(self, config_path: Path, backup_root: Path, items: Iterable[str]) -> None:
        config_path = Path(config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "backup_root": str(backup_root),
            "items": list(items),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_snapshots(self) -> list[Path]:
        if not self.backup_root.exists():
            return []
        return sorted(
            [p for p in self.backup_root.iterdir() if p.is_dir() and p.name not in INTERNAL_BACKUP_DIR_NAMES],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

    def read_snapshot_detail(self, snapshot_dir: Path, selected_names: Iterable[str]) -> SnapshotDetail:
        snapshot_dir = Path(snapshot_dir)
        manifest_path = snapshot_dir / "manifest.json"
        selected = list(selected_names)
        if not manifest_path.exists():
            return SnapshotDetail(snapshot_dir, "", [], [], selected, "manifest.json 不存在")

        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return SnapshotDetail(snapshot_dir, "", [], [], selected, f"manifest.json 读取失败：{exc}")

        items: list[SnapshotItem] = []
        for raw_item in data.get("items", []):
            if not isinstance(raw_item, dict):
                continue
            name = str(raw_item.get("name", "")).strip()
            if not name:
                continue
            items.append(
                SnapshotItem(
                    name=name,
                    source=Path(str(raw_item.get("source", ""))),
                    sensitive=bool(raw_item.get("sensitive", True)),
                    sensitive_plaintext=bool(raw_item.get("sensitive_plaintext", raw_item.get("sensitive", True))),
                )
            )

        snapshot_names = {item.name for item in items}
        available = [name for name in selected if name in snapshot_names]
        missing = [name for name in selected if name not in snapshot_names]
        return SnapshotDetail(snapshot_dir, str(data.get("created_at", "")), items, available, missing)

    def _unique_child_path(self, parent: Path, base_name: str) -> Path:
        candidate = parent / base_name
        if not candidate.exists():
            return candidate
        index = 1
        while True:
            candidate = parent / f"{base_name}-{index:02d}"
            if not candidate.exists():
                return candidate
            index += 1

    def _copy_path(self, source: Path, destination: Path) -> None:
        if source.is_dir():
            if os.name == "nt":
                self._robocopy_directory(source, destination)
            else:
                shutil.copytree(source, destination, ignore=self._ignore_volatile)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    def _robocopy_directory(self, source: Path, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        excluded_dirs = sorted(VOLATILE_DIR_NAMES)
        excluded_files = sorted(VOLATILE_FILE_PATTERNS)
        command = [
            "robocopy",
            str(source),
            str(destination),
            "/E",
            "/R:1",
            "/W:1",
            "/NFL",
            "/NDL",
            "/NJH",
            "/NJS",
            "/NP",
        ]
        if excluded_dirs:
            command.extend(["/XD", *excluded_dirs])
        if excluded_files:
            command.extend(["/XF", *excluded_files])
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode >= 8:
            raise OSError(f"robocopy 失败，退出码 {result.returncode}：{result.stderr or result.stdout}")

    def _ignore_volatile(self, directory: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        for name in names:
            path = Path(directory) / name
            if path.is_dir() and name in VOLATILE_DIR_NAMES:
                ignored.add(name)
                continue
            if any(fnmatch.fnmatch(name, pattern) for pattern in VOLATILE_FILE_PATTERNS):
                ignored.add(name)
        return ignored

    def _remove_path(self, path: Path) -> None:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

    def _move_path(self, source: Path, destination: Path) -> None:
        shutil.move(str(source), str(destination))

    def _path_size(self, path: Path) -> int:
        if path.is_file():
            return path.stat().st_size
        total = 0
        for child in path.rglob("*"):
            if child.is_file() and not self._is_volatile_path(child):
                total += child.stat().st_size
        return total

    def _last_write_time(self, path: Path) -> datetime:
        if path.is_file():
            return datetime.fromtimestamp(path.stat().st_mtime)
        latest = path.stat().st_mtime
        for child in path.rglob("*"):
            try:
                latest = max(latest, child.stat().st_mtime)
            except OSError:
                continue
        return datetime.fromtimestamp(latest)

    def _is_volatile_path(self, path: Path) -> bool:
        if any(part in VOLATILE_DIR_NAMES for part in path.parts):
            return True
        return any(fnmatch.fnmatch(path.name, pattern) for pattern in VOLATILE_FILE_PATTERNS)
