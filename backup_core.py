from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


VOLATILE_DIR_NAMES = {".tmp", "tmp", "__pycache__"}
VOLATILE_FILE_PATTERNS = ["*.sqlite-shm", "*.db-shm", "*.lock"]
RESTORE_BACKUP_DIR_NAME = "恢复前备份"
LINK_STORE_DIR_NAME = "迁移后的真实目录"
LINK_MIGRATION_BACKUP_DIR_NAME = "迁移前备份"
LINK_CANCEL_BACKUP_DIR_NAME = "取消迁移前备份"
ENVIRONMENT_PATH_DIR_NAME = "环境变量Path备份"
LEGACY_RESTORE_BACKUP_DIR_NAME = "restore-backups"
LEGACY_LINK_STORE_DIR_NAME = "link-store"
LEGACY_LINK_MIGRATION_BACKUP_DIR_NAME = "link-migration-backups"
LEGACY_ENVIRONMENT_PATH_DIR_NAME = "environment-path"
INTERNAL_BACKUP_DIR_NAMES = {
    RESTORE_BACKUP_DIR_NAME,
    LINK_STORE_DIR_NAME,
    LINK_MIGRATION_BACKUP_DIR_NAME,
    LINK_CANCEL_BACKUP_DIR_NAME,
    ENVIRONMENT_PATH_DIR_NAME,
    LEGACY_RESTORE_BACKUP_DIR_NAME,
    LEGACY_LINK_STORE_DIR_NAME,
    LEGACY_LINK_MIGRATION_BACKUP_DIR_NAME,
    LEGACY_ENVIRONMENT_PATH_DIR_NAME,
}
LEGACY_INTERNAL_BACKUP_DIR_MAPPINGS = (
    (LEGACY_RESTORE_BACKUP_DIR_NAME, RESTORE_BACKUP_DIR_NAME),
    (LEGACY_LINK_MIGRATION_BACKUP_DIR_NAME, LINK_MIGRATION_BACKUP_DIR_NAME),
    (LEGACY_ENVIRONMENT_PATH_DIR_NAME, ENVIRONMENT_PATH_DIR_NAME),
    (LEGACY_LINK_STORE_DIR_NAME, LINK_STORE_DIR_NAME),
)


def describe_migration_error(exc_or_text) -> str:
    text = str(exc_or_text)
    path = _extract_error_path(text)
    path_hint = f"：{Path(path).name}" if path else ""
    winerror = getattr(exc_or_text, "winerror", None)
    if winerror is None:
        winerror = _extract_winerror(text)
    errno_value = getattr(exc_or_text, "errno", None)

    if winerror == 32 or errno_value == 32 or "WinError 32" in text:
        return f"文件正在使用中{path_hint}。请先关闭正在使用这个目录的软件，再重试迁移。"
    if "程序正在运行" in text:
        process_match = re.search(r"程序正在运行：([^。\\n]+)", text)
        process_text = f"：{process_match.group(1)}" if process_match else ""
        return f"程序正在运行{process_text}。请先关闭相关软件和后台进程，再重试迁移。"
    if winerror == 5 or errno_value == 13 or "WinError 5" in text or "拒绝访问" in text or "Access is denied" in text:
        return f"权限不足或程序正在运行{path_hint}。请关闭相关软件，必要时以管理员身份重新打开本软件后重试。"
    if "迁移后的真实目录已存在" in text and "C 盘原位置不是 Junction" in text:
        return "D 盘迁移后的真实目录已经存在，但 C 盘原位置还不是链接。请先确认 C 盘和 D 盘哪边数据完整，再处理残留目录。"
    return text.splitlines()[0] if text.splitlines() else text


def _extract_winerror(text: str) -> int | None:
    match = re.search(r"WinError\s+(\d+)", text)
    if not match:
        return None
    return int(match.group(1))


def _extract_error_path(text: str) -> str:
    matches = re.findall(r"'([^']+)'", text)
    return matches[-1] if matches else ""


def empty_user_settings(settings_exists: bool = False) -> dict:
    return {
        "settings_exists": settings_exists,
        "selected_items": [],
        "custom_items": [],
        "backup_root": "",
        "schedule_time": "",
        "cloud_backup": {},
    }


def load_user_settings(config_path: Path) -> dict:
    config_path = Path(config_path)
    if not config_path.exists():
        return empty_user_settings(False)
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_user_settings(False)
    if not isinstance(data, dict):
        return empty_user_settings(False)
    selected = data.get("selected_items", [])
    if not isinstance(selected, list):
        selected = []
    custom_items = data.get("custom_items", [])
    if not isinstance(custom_items, list):
        custom_items = []
    normalized_custom = []
    for item in custom_items:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "")).strip()
        if not path:
            continue
        normalized_custom.append(
            {
                "name": str(item.get("name", "")).strip(),
                "path": path,
                "sensitive": bool(item.get("sensitive", True)),
            }
        )
    return {
        "settings_exists": True,
        "selected_items": [str(item) for item in selected],
        "custom_items": normalized_custom,
        "backup_root": str(data.get("backup_root", "")).strip(),
        "schedule_time": str(data.get("schedule_time", "")).strip(),
        "cloud_backup": data.get("cloud_backup", {}) if isinstance(data.get("cloud_backup", {}), dict) else {},
    }


def write_user_settings(
    config_path: Path,
    selected_items: Iterable[str],
    custom_items: Iterable[dict] | None = None,
    backup_root: Path | str | None = None,
    schedule_time: str | None = None,
) -> None:
    config_path = Path(config_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    previous = load_user_settings(config_path) if config_path.exists() else empty_user_settings(False)
    payload = {
        "selected_items": list(selected_items),
        "custom_items": list(custom_items) if custom_items is not None else previous["custom_items"],
        "backup_root": str(backup_root) if backup_root is not None else previous["backup_root"],
        "schedule_time": schedule_time if schedule_time is not None else previous["schedule_time"],
        "cloud_backup": previous.get("cloud_backup", {}),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


@dataclass(frozen=True)
class BackupItem:
    name: str
    source: Path
    sensitive: bool = True
    restore_target: Path | None = None


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
class EnvironmentPathBackupResult:
    path: Path
    json_path: Path
    text_path: Path


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
class LinkCancelResult:
    link_path: Path
    store_path: Path
    pre_cancel_backup_dir: Path


@dataclass(frozen=True)
class LinkMigrationStatus:
    state: str
    label: str
    detail: str
    link_path: Path
    store_path: Path
    can_migrate: bool
    can_cancel: bool
    problem: str = ""


@dataclass(frozen=True)
class SnapshotItem:
    name: str
    source: Path
    sensitive: bool = True
    sensitive_plaintext: bool = True
    restore_target: Path | None = None


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

    def normalize_internal_backup_directories(self, items: Iterable[BackupItem] | None = None) -> list[tuple[Path, Path]]:
        moved_paths: list[tuple[Path, Path]] = []
        if not self.backup_root.exists():
            return moved_paths

        link_repoints = self._legacy_link_repoints(items or [])
        for legacy_name, current_name in LEGACY_INTERNAL_BACKUP_DIR_MAPPINGS:
            legacy_dir = self.backup_root / legacy_name
            current_dir = self.backup_root / current_name
            if not legacy_dir.exists() or not legacy_dir.is_dir():
                continue

            link_destinations: dict[str, Path] = {}
            if legacy_name == LEGACY_LINK_STORE_DIR_NAME:
                for link_path, legacy_target in link_repoints:
                    if link_path.exists():
                        self._remove_path(link_path)
                    link_destinations[self._path_key(legacy_target)] = current_dir / self._relative_to_normalized(legacy_target, legacy_dir)

            current_dir.mkdir(parents=True, exist_ok=True)
            child_destinations: dict[str, Path] = {}
            for child in list(legacy_dir.iterdir()):
                destination = current_dir / child.name
                if destination.exists():
                    destination = self._unique_child_path(current_dir, child.name)
                self._move_path(child, destination)
                child_destinations[self._path_key(child)] = destination
                moved_paths.append((child, destination))

            if legacy_name == LEGACY_LINK_STORE_DIR_NAME:
                for link_path, legacy_target in link_repoints:
                    destination = self._new_link_destination_after_normalize(
                        legacy_dir,
                        legacy_target,
                        child_destinations,
                        link_destinations,
                    )
                    if destination.exists() and not link_path.exists():
                        self.create_junction(link_path, destination)

            try:
                legacy_dir.rmdir()
            except OSError:
                pass
        return moved_paths

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
                self._verify_copied_path(source, destination)
                copied.append(item.name)
                manifest_items.append(
                    {
                        "name": item.name,
                        "source": str(source),
                        "sensitive": item.sensitive,
                        "sensitive_plaintext": item.sensitive,
                        "restore_target": str(item.restore_target) if item.restore_target else "",
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

    def backup_environment_path(
        self,
        name: str | None = None,
        user_path: str | None = None,
        system_path: str | None = None,
        process_path: str | None = None,
    ) -> EnvironmentPathBackupResult:
        backup_name = name or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_dir = self._unique_child_path(self.backup_root / ENVIRONMENT_PATH_DIR_NAME, backup_name)
        backup_dir.mkdir(parents=True, exist_ok=False)

        user_value = os.environ.get("USER_PATH", "") if user_path is None else user_path
        system_value = os.environ.get("SYSTEM_PATH", "") if system_path is None else system_path
        process_value = os.environ.get("PATH", "") if process_path is None else process_path
        payload = {
            "kind": "environment_path",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "user_path": self._split_path_entries(user_value),
            "system_path": self._split_path_entries(system_value),
            "process_path": self._split_path_entries(process_value),
        }

        json_path = backup_dir / "path.json"
        text_path = backup_dir / "path.txt"
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        text_path.write_text(self._format_environment_path_text(payload), encoding="utf-8")
        return EnvironmentPathBackupResult(backup_dir, json_path, text_path)

    def restore_snapshot(self, snapshot_dir: Path, target_home: Path, item_names: Iterable[str]) -> RestoreResult:
        snapshot_dir = Path(snapshot_dir)
        target_home = Path(target_home)
        pre_restore_dir = self.backup_root / RESTORE_BACKUP_DIR_NAME / datetime.now().strftime("%Y-%m-%d-%H%M%S")
        pre_restore_dir.mkdir(parents=True, exist_ok=True)

        restored: list[str] = []
        skipped: list[str] = []

        for name in item_names:
            source = snapshot_dir / name
            if not source.exists():
                skipped.append(name)
                continue
            target = self._restore_target_for_name(snapshot_dir, target_home, name)

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

        running_processes = self._running_processes_under_path(source)
        if running_processes:
            process_text = "；".join(f"{name}(PID {pid})" for name, pid, _path in running_processes[:5])
            raise PermissionError(
                5,
                f"目录内有程序正在运行：{process_text}。请先关闭相关软件和后台进程，再重试迁移。",
                str(source),
            )

        link_store_root = Path(link_store_root)
        store_path = link_store_root / item.name
        if store_path.exists():
            raise FileExistsError(f"链接存储目录已存在：{store_path}")

        pre_migration_dir = self.backup_root / LINK_MIGRATION_BACKUP_DIR_NAME / datetime.now().strftime("%Y-%m-%d-%H%M%S")
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

    def default_link_store_root(self) -> Path:
        return self.backup_root / LINK_STORE_DIR_NAME

    def legacy_link_store_root(self) -> Path:
        return self.backup_root / LEGACY_LINK_STORE_DIR_NAME

    def link_store_candidates(self, item: BackupItem) -> list[Path]:
        source = Path(item.source)
        candidates: list[Path] = []
        if self._is_junction_path(source):
            target = self._junction_target(source)
            if target is not None:
                candidates.append(target)
        candidates.extend(
            [
                self.default_link_store_root() / item.name,
                self.legacy_link_store_root() / item.name,
            ]
        )
        unique: list[Path] = []
        seen = set()
        for candidate in candidates:
            marker = str(candidate).lower()
            if marker in seen:
                continue
            seen.add(marker)
            unique.append(candidate)
        return unique

    def link_store_path_for_item(self, item: BackupItem) -> Path:
        for candidate in self.link_store_candidates(item):
            if self._path_exists(candidate):
                return candidate
        return self.default_link_store_root() / item.name

    def get_link_migration_status(self, item: BackupItem) -> LinkMigrationStatus:
        link_path = Path(item.source)
        default_store_path = self.default_link_store_root() / item.name
        is_junction = self._is_junction_path(link_path)
        link_exists = self._path_exists(link_path)
        junction_target = self._junction_target(link_path) if is_junction else None
        existing_store_path = next(
            (candidate for candidate in self.link_store_candidates(item) if self._path_exists(candidate)),
            None,
        )

        if is_junction:
            store_path = junction_target or existing_store_path or default_store_path
            if junction_target is not None and self._path_exists(junction_target):
                return LinkMigrationStatus(
                    state="migrated",
                    label="已迁移",
                    detail=f"C 盘引用：{link_path}；D 盘真实目录：{store_path}",
                    link_path=link_path,
                    store_path=store_path,
                    can_migrate=False,
                    can_cancel=True,
                )
            problem = f"C 盘原位置是 Junction，但真实目录不存在：{store_path}"
            return LinkMigrationStatus(
                state="broken",
                label="异常",
                detail=f"C 盘引用：{link_path}；D 盘真实目录：{store_path}",
                link_path=link_path,
                store_path=store_path,
                can_migrate=False,
                can_cancel=False,
                problem=problem,
            )

        store_path = existing_store_path or default_store_path
        if existing_store_path is not None:
            if link_exists:
                problem = "迁移后的真实目录已存在，但 C 盘原位置不是 Junction。"
            else:
                problem = "迁移后的真实目录已存在，但 C 盘原位置不存在。"
            return LinkMigrationStatus(
                state="broken",
                label="异常",
                detail=f"C 盘原目录：{link_path}；D 盘真实目录：{store_path}",
                link_path=link_path,
                store_path=store_path,
                can_migrate=False,
                can_cancel=False,
                problem=problem,
            )

        if link_exists:
            return LinkMigrationStatus(
                state="normal",
                label="未迁移",
                detail=f"C 盘原目录：{link_path}；迁移后真实目录：{default_store_path}",
                link_path=link_path,
                store_path=default_store_path,
                can_migrate=True,
                can_cancel=False,
            )

        problem = "C 盘原目录不存在，无法迁移或取消迁移。"
        return LinkMigrationStatus(
            state="broken",
            label="异常",
            detail=f"C 盘原目录：{link_path}；迁移后真实目录：{default_store_path}",
            link_path=link_path,
            store_path=default_store_path,
            can_migrate=False,
            can_cancel=False,
            problem=problem,
        )

    def is_link_migrated(self, item: BackupItem) -> bool:
        return self.get_link_migration_status(item).state == "migrated"

    def cancel_link_migration(self, item: BackupItem) -> LinkCancelResult:
        link_path = Path(item.source)
        if not link_path.exists():
            raise FileNotFoundError(f"链接位置不存在：{link_path}")
        if not (hasattr(link_path, "is_junction") and link_path.is_junction()):
            raise FileNotFoundError(f"链接位置不是 Junction：{link_path}")

        store_path = self.link_store_path_for_item(item)
        if not store_path.exists():
            raise FileNotFoundError(f"链接真实目录不存在：{store_path}")

        pre_cancel_dir = self.backup_root / LINK_CANCEL_BACKUP_DIR_NAME / datetime.now().strftime("%Y-%m-%d-%H%M%S")
        pre_cancel_dir.mkdir(parents=True, exist_ok=True)
        self._copy_path(store_path, pre_cancel_dir / item.name)

        try:
            self._remove_path(link_path)
            self._move_path(store_path, link_path)
        except Exception:
            if not store_path.exists() and link_path.exists() and not self.is_link_migrated(item):
                self._move_path(link_path, store_path)
            if not link_path.exists() and store_path.exists():
                self.create_junction(link_path, store_path)
            raise
        return LinkCancelResult(link_path, store_path, pre_cancel_dir)

    def _legacy_link_repoints(self, items: Iterable[BackupItem]) -> list[tuple[Path, Path]]:
        repoints: list[tuple[Path, Path]] = []
        legacy_root = self.legacy_link_store_root()
        normalized_legacy_root = self._normalize_path(legacy_root)
        for item in items:
            source = Path(item.source)
            if not (hasattr(source, "is_junction") and source.exists() and source.is_junction()):
                continue
            try:
                target = self._normalize_path(Path(os.path.realpath(source)))
            except OSError:
                continue
            try:
                target.relative_to(normalized_legacy_root)
            except ValueError:
                continue
            repoints.append((source, target))
        return repoints

    def _new_link_destination_after_normalize(
        self,
        legacy_root: Path,
        legacy_target: Path,
        child_destinations: dict[str, Path],
        link_destinations: dict[str, Path],
    ) -> Path:
        key = self._path_key(legacy_target)
        if key in child_destinations:
            return child_destinations[key]
        try:
            relative_target = self._relative_to_normalized(legacy_target, legacy_root)
            first_child = relative_target.parts[0]
        except (ValueError, IndexError):
            return self.default_link_store_root() / legacy_target.name
        moved_child = child_destinations.get(self._path_key(legacy_root / first_child))
        if moved_child is None:
            return link_destinations.get(key, self.default_link_store_root() / first_child)
        relative_tail = Path(*relative_target.parts[1:])
        return moved_child / relative_tail

    def _path_key(self, path: Path) -> str:
        normalized = self._normalize_path(path)
        return str(normalized).lower() if os.name == "nt" else str(normalized)

    def _normalize_path(self, path: Path) -> Path:
        path = Path(path)
        if os.name != "nt":
            return path
        try:
            return path.resolve(strict=False)
        except OSError:
            return path

    def _relative_to_normalized(self, path: Path, parent: Path) -> Path:
        return self._normalize_path(path).relative_to(self._normalize_path(parent))

    def _path_exists(self, path: Path) -> bool:
        return Path(path).exists()

    def _is_junction_path(self, path: Path) -> bool:
        path = Path(path)
        if not hasattr(path, "is_junction"):
            return False
        try:
            return bool(path.is_junction())
        except OSError:
            return False

    def _junction_target(self, path: Path) -> Path | None:
        path = Path(path)
        if not self._is_junction_path(path):
            return None
        try:
            return Path(os.path.realpath(path))
        except OSError:
            return None

    def create_junction(self, link_path: Path, store_path: Path) -> None:
        link_path = Path(link_path)
        store_path = Path(store_path)
        if link_path.exists():
            raise FileExistsError(f"链接位置已存在：{link_path}")
        if not store_path.exists():
            raise FileNotFoundError(f"链接目标不存在：{store_path}")

        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link_path), str(store_path)],
            check=True,
            **self._hidden_subprocess_kwargs(),
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

    def write_schedule_config(
        self,
        config_path: Path,
        backup_root: Path,
        items: Iterable[str],
        custom_items: Iterable[dict] | None = None,
    ) -> None:
        config_path = Path(config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "backup_root": str(backup_root),
            "items": list(items),
            "custom_items": list(custom_items or []),
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
                    restore_target=Path(str(raw_item["restore_target"])) if raw_item.get("restore_target") else None,
                )
            )

        snapshot_names = {item.name for item in items}
        available = [name for name in selected if name in snapshot_names]
        missing = [name for name in selected if name not in snapshot_names]
        return SnapshotDetail(snapshot_dir, str(data.get("created_at", "")), items, available, missing)

    def _restore_target_for_name(self, snapshot_dir: Path, target_home: Path, name: str) -> Path:
        detail = self.read_snapshot_detail(snapshot_dir, [name])
        item = next((candidate for candidate in detail.items if candidate.name == name), None)
        if item and item.restore_target:
            return item.restore_target
        return target_home / name

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

    def _split_path_entries(self, value: str) -> list[str]:
        return [part.strip() for part in str(value or "").split(os.pathsep) if part.strip()]

    def _format_environment_path_text(self, payload: dict) -> str:
        sections = [
            ("用户 Path", payload.get("user_path", [])),
            ("系统 Path", payload.get("system_path", [])),
            ("当前进程 Path", payload.get("process_path", [])),
        ]
        lines = [
            "环境变量 Path 备份",
            f"创建时间：{payload.get('created_at', '')}",
            "",
        ]
        for title, entries in sections:
            lines.append(f"[{title}]")
            if entries:
                lines.extend(str(entry) for entry in entries)
            else:
                lines.append("(空)")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

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
        result = subprocess.run(command, **self._hidden_subprocess_kwargs())
        if result.returncode >= 8:
            raise OSError(f"robocopy 失败，退出码 {result.returncode}：{result.stderr or result.stdout}")

    def _hidden_subprocess_kwargs(self) -> dict:
        popen_kwargs = {"capture_output": True, "text": True}
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            popen_kwargs["startupinfo"] = startupinfo
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        return popen_kwargs

    def _verify_copied_path(self, source: Path, destination: Path) -> None:
        if not destination.exists():
            raise OSError(f"备份校验失败，目标不存在：{destination}")
        if source.is_file():
            if not destination.is_file() or source.stat().st_size != destination.stat().st_size:
                raise OSError(f"备份校验失败，文件不完整：{destination}")
            return
        for child in source.rglob("*"):
            if self._is_volatile_path(child):
                continue
            relative_path = child.relative_to(source)
            copied_child = destination / relative_path
            if child.is_dir():
                if not copied_child.is_dir():
                    raise OSError(f"备份校验失败，目录缺失：{copied_child}")
            elif child.is_file():
                if not copied_child.is_file() or child.stat().st_size != copied_child.stat().st_size:
                    raise OSError(f"备份校验失败，文件缺失或不完整：{copied_child}")

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
        if hasattr(path, "is_junction") and path.is_junction():
            path.rmdir()
            return
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

    def _move_path(self, source: Path, destination: Path) -> None:
        shutil.move(str(source), str(destination))

    def _running_processes_under_path(self, path: Path) -> list[tuple[str, int, Path]]:
        if os.name != "nt":
            return []
        root = self._normalize_path(Path(path))
        root_text = str(root).lower()
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-CimInstance Win32_Process | Select-Object ProcessId,Name,ExecutablePath,CommandLine | ConvertTo-Json -Compress",
                ],
                **self._hidden_subprocess_kwargs(),
            )
        except Exception:
            return []
        if result.returncode != 0 or not result.stdout.strip():
            return []
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return []
        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, list):
            return []
        matches: list[tuple[str, int, Path]] = []
        seen: set[int] = set()
        for process in payload:
            if not isinstance(process, dict):
                continue
            pid = int(process.get("ProcessId") or 0)
            if not pid or pid in seen:
                continue
            name = str(process.get("Name") or "")
            candidates = [str(process.get("ExecutablePath") or ""), str(process.get("CommandLine") or "")]
            matched_path = self._process_path_under_root(candidates, root_text)
            if matched_path is None:
                continue
            seen.add(pid)
            matches.append((name, pid, matched_path))
        return matches

    def _process_path_under_root(self, candidates: Iterable[str], root_text: str) -> Path | None:
        for candidate in candidates:
            if not candidate:
                continue
            normalized = candidate.replace("/", "\\").lower()
            index = normalized.find(root_text)
            if index < 0:
                continue
            tail = candidate[index:].strip().strip('"')
            return Path(tail.split('"')[0])
        return None

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
