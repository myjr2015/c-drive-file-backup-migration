import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backup_core import (
    ENVIRONMENT_PATH_DIR_NAME,
    LEGACY_ENVIRONMENT_PATH_DIR_NAME,
    LEGACY_LINK_MIGRATION_BACKUP_DIR_NAME,
    LEGACY_LINK_STORE_DIR_NAME,
    LEGACY_RESTORE_BACKUP_DIR_NAME,
    LINK_MIGRATION_BACKUP_DIR_NAME,
    LINK_STORE_DIR_NAME,
    RESTORE_BACKUP_DIR_NAME,
    BackupItem,
    BackupService,
    SnapshotItem,
    load_user_settings,
    write_user_settings,
)


class FakeLinkStatusBackupService(BackupService):
    def __init__(
        self,
        backup_root: Path,
        existing: set[Path | str],
        junctions: set[Path | str] | None = None,
        targets: dict[Path | str, Path | str] | None = None,
    ):
        super().__init__(backup_root)
        self.existing = {self._path_key(Path(path)) for path in existing}
        self.junctions = {self._path_key(Path(path)) for path in junctions or set()}
        self.targets = {self._path_key(Path(source)): Path(target) for source, target in (targets or {}).items()}

    def _path_exists(self, path: Path) -> bool:
        return self._path_key(path) in self.existing

    def _is_junction_path(self, path: Path) -> bool:
        return self._path_key(path) in self.junctions

    def _junction_target(self, path: Path) -> Path | None:
        return self.targets.get(self._path_key(path))


class BackupServiceTests(unittest.TestCase):
    def test_link_migration_status_marks_normal_directory_as_not_migrated(self):
        service = FakeLinkStatusBackupService(Path("D:/backup"), existing={"C:/Users/example/.happy"})
        item = BackupItem(".happy", Path("C:/Users/example/.happy"))

        status = service.get_link_migration_status(item)

        self.assertEqual(status.state, "normal")
        self.assertEqual(status.label, "未迁移")
        self.assertEqual(status.link_path, item.source)
        self.assertEqual(status.store_path, Path("D:/backup") / LINK_STORE_DIR_NAME / ".happy")
        self.assertTrue(status.can_migrate)
        self.assertFalse(status.can_cancel)
        self.assertIn("C 盘原目录", status.detail)

    def test_link_migration_status_marks_junction_with_store_as_migrated(self):
        store_path = Path("D:/backup") / LINK_STORE_DIR_NAME / ".vscode"
        item = BackupItem(".vscode", Path("C:/Users/example/.vscode"))
        service = FakeLinkStatusBackupService(
            Path("D:/backup"),
            existing={item.source, store_path},
            junctions={item.source},
            targets={item.source: store_path},
        )

        status = service.get_link_migration_status(item)

        self.assertEqual(status.state, "migrated")
        self.assertEqual(status.label, "已迁移")
        self.assertFalse(status.can_migrate)
        self.assertTrue(status.can_cancel)
        self.assertIn(str(store_path), status.detail)
        self.assertTrue(service.is_link_migrated(item))

    def test_link_migration_status_marks_store_without_junction_as_broken(self):
        store_path = Path("D:/backup") / LINK_STORE_DIR_NAME / ".codex"
        item = BackupItem(".codex", Path("C:/Users/example/.codex"))
        service = FakeLinkStatusBackupService(
            Path("D:/backup"),
            existing={item.source, store_path},
        )

        status = service.get_link_migration_status(item)

        self.assertEqual(status.state, "broken")
        self.assertEqual(status.label, "异常")
        self.assertFalse(status.can_migrate)
        self.assertFalse(status.can_cancel)
        self.assertIn("真实目录已存在", status.problem)

    def test_link_migration_status_marks_junction_without_store_as_broken(self):
        store_path = Path("D:/backup") / LINK_STORE_DIR_NAME / ".ssh"
        item = BackupItem(".ssh", Path("C:/Users/example/.ssh"))
        service = FakeLinkStatusBackupService(
            Path("D:/backup"),
            existing={item.source},
            junctions={item.source},
            targets={item.source: store_path},
        )

        status = service.get_link_migration_status(item)

        self.assertEqual(status.state, "broken")
        self.assertEqual(status.label, "异常")
        self.assertFalse(status.can_migrate)
        self.assertFalse(status.can_cancel)
        self.assertIn("真实目录不存在", status.problem)

    def test_scan_marks_existing_items_and_computes_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "home" / ".happy"
            source.mkdir(parents=True)
            (source / "sessions.json").write_text("abc", encoding="utf-8")

            service = BackupService(root / "backups")
            result = service.scan_items([BackupItem(".happy", source)])

            self.assertEqual(len(result), 1)
            self.assertTrue(result[0].exists)
            self.assertEqual(result[0].size_bytes, 3)

    def test_create_snapshot_copies_selected_items_and_skips_volatile_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "home" / ".codex"
            source.mkdir(parents=True)
            (source / "config.toml").write_text("config", encoding="utf-8")
            (source / "state_5.sqlite-shm").write_text("volatile", encoding="utf-8")
            tmp_dir = source / "tmp"
            tmp_dir.mkdir()
            (tmp_dir / "scratch.txt").write_text("skip", encoding="utf-8")

            service = BackupService(root / "backups")
            snapshot = service.create_snapshot([BackupItem(".codex", source)], name="test")

            self.assertTrue((snapshot.path / ".codex" / "config.toml").exists())
            self.assertFalse((snapshot.path / ".codex" / "state_5.sqlite-shm").exists())
            self.assertFalse((snapshot.path / ".codex" / "tmp").exists())
            self.assertTrue((snapshot.path / "manifest.json").exists())

    def test_create_snapshot_verifies_copied_files_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "home" / ".happy"
            source.mkdir(parents=True)
            (source / "sessions.json").write_text("data", encoding="utf-8")

            class BrokenVerifyBackupService(BackupService):
                def _copy_path(self, source_path, destination_path):
                    destination_path.mkdir(parents=True, exist_ok=True)

            service = BrokenVerifyBackupService(root / "backups")

            with self.assertRaises(OSError):
                service.create_snapshot([BackupItem(".happy", source)], name="broken-verify")

            self.assertFalse((root / "backups" / "broken-verify").exists())

    def test_robocopy_runs_without_console_window_on_windows(self):
        service = BackupService(Path("D:/backups"))

        with patch("backup_core.os.name", "nt"), patch("backup_core.subprocess.run") as run:
            run.return_value.returncode = 1
            service._robocopy_directory(Path("C:/source"), Path("D:/dest"))

        kwargs = run.call_args.kwargs
        self.assertTrue(kwargs["capture_output"])
        self.assertTrue(kwargs["text"])
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            self.assertEqual(kwargs["creationflags"], subprocess.CREATE_NO_WINDOW)
        self.assertIsNotNone(kwargs["startupinfo"])

    def test_create_snapshot_manifest_records_sensitive_plaintext_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ssh_source = root / "home" / ".ssh"
            cache_source = root / "home" / "npm-cache"
            ssh_source.mkdir(parents=True)
            cache_source.mkdir(parents=True)
            (ssh_source / "id_rsa").write_text("secret", encoding="utf-8")
            (cache_source / "package").write_text("cache", encoding="utf-8")

            service = BackupService(root / "backups")
            snapshot = service.create_snapshot(
                [
                    BackupItem(".ssh", ssh_source, sensitive=True),
                    BackupItem("AppData/Roaming/npm-cache", cache_source, sensitive=False),
                ],
                name="sensitive",
            )

            manifest = (snapshot.path / "manifest.json").read_text(encoding="utf-8")
            self.assertIn('"contains_sensitive_plaintext": true', manifest)
            self.assertIn('"sensitive_plaintext": true', manifest)
            self.assertIn('"sensitive_plaintext": false', manifest)

    def test_restore_backs_up_existing_target_before_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backup_root = root / "backups"
            snapshot_dir = backup_root / "2026-05-19-test"
            source = snapshot_dir / ".happy"
            source.mkdir(parents=True)
            (source / "sessions.json").write_text("new", encoding="utf-8")

            home = root / "home"
            current = home / ".happy"
            current.mkdir(parents=True)
            (current / "sessions.json").write_text("old", encoding="utf-8")

            service = BackupService(backup_root)
            result = service.restore_snapshot(snapshot_dir, home, [".happy"])

            self.assertEqual((current / "sessions.json").read_text(encoding="utf-8"), "new")
            self.assertTrue(result.pre_restore_backup_dir.exists())
            backups = list(result.pre_restore_backup_dir.rglob("sessions.json"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(encoding="utf-8"), "old")

    def test_migrate_to_link_moves_source_into_link_store_and_creates_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "home" / ".happy"
            source.mkdir(parents=True)
            (source / "sessions.json").write_text("data", encoding="utf-8")

            link_store = root / "link-store"
            service = BackupService(root / "backups")
            result = service.prepare_link_migration(BackupItem(".happy", source), link_store)

            self.assertEqual(result.link_path, source)
            self.assertEqual(result.store_path, link_store / ".happy")
            self.assertTrue((result.store_path / "sessions.json").exists())
            self.assertFalse(source.exists())

    @unittest.skipUnless(os.name == "nt", "Junction 取消迁移只在 Windows 上验证")
    def test_cancel_link_migration_restores_junction_to_normal_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            link_path = root / "home" / ".happy"
            store_path = root / LINK_STORE_DIR_NAME / ".happy"
            link_path.parent.mkdir(parents=True)
            store_path.mkdir(parents=True)
            (store_path / "sessions.json").write_text("data", encoding="utf-8")

            service = BackupService(root / "backups")
            service.create_junction(link_path, store_path)
            self.assertTrue(link_path.is_junction())

            result = service.cancel_link_migration(BackupItem(".happy", link_path))

            self.assertEqual(result.link_path, link_path)
            self.assertEqual(result.store_path, store_path)
            self.assertTrue((link_path / "sessions.json").exists())
            self.assertFalse(link_path.is_junction())
            self.assertFalse(store_path.exists())
            self.assertTrue((result.pre_cancel_backup_dir / ".happy" / "sessions.json").exists())

    def test_create_junction_runs_without_console_window_on_windows(self):
        service = BackupService(Path("D:/backups"))

        with patch("backup_core.os.name", "nt"), patch("backup_core.subprocess.run") as run:
            run.return_value.returncode = 0
            with patch.object(Path, "exists", side_effect=[False, True]):
                service.create_junction(Path("C:/source"), Path("D:/store/source"))

        kwargs = run.call_args.kwargs
        self.assertTrue(kwargs["capture_output"])
        self.assertTrue(kwargs["text"])
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            self.assertEqual(kwargs["creationflags"], subprocess.CREATE_NO_WINDOW)
        self.assertIsNotNone(kwargs["startupinfo"])

    def test_create_scheduled_backup_command_uses_selected_items_and_launcher(self):
        service = BackupService(Path("D:/backup"))
        command = service.create_scheduled_backup_command(
            launcher=Path("D:/tool/backup_cli.py"),
            items=[".happy", ".codex"],
            backup_root=Path("D:/backup"),
        )

        self.assertIn("backup_cli.py", command)
        self.assertIn("--items", command)
        self.assertIn(".happy,.codex", command)
        self.assertIn("D:/backup", command.replace("\\", "/"))

    def test_write_schedule_config_persists_backup_root_and_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = BackupService(root / "backups")
            config_path = root / "data" / "schedule.json"

            service.write_schedule_config(
                config_path,
                root / "backups",
                [".happy", ".codex", "自定义/资料"],
                [{"path": "D:/资料", "sensitive": False}],
            )

            text = config_path.read_text(encoding="utf-8")
            self.assertIn(".happy", text)
            self.assertIn(".codex", text)
            self.assertIn("自定义/资料", text)
            self.assertIn("D:/资料", text)
            self.assertIn("backups", text)

    def test_list_snapshots_excludes_internal_maintenance_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backup_root = root / "backups"
            for name in [
                "2026-05-19-010000",
                "restore-backups",
                "link-store",
                "link-migration-backups",
                RESTORE_BACKUP_DIR_NAME,
                LINK_STORE_DIR_NAME,
                LINK_MIGRATION_BACKUP_DIR_NAME,
                ENVIRONMENT_PATH_DIR_NAME,
            ]:
                (backup_root / name).mkdir(parents=True)

            service = BackupService(backup_root)
            snapshots = service.list_snapshots()

            self.assertEqual([p.name for p in snapshots], ["2026-05-19-010000"])

    def test_internal_maintenance_directory_defaults_are_chinese(self):
        self.assertEqual(RESTORE_BACKUP_DIR_NAME, "恢复前备份")
        self.assertEqual(LINK_STORE_DIR_NAME, "迁移后的真实目录")
        self.assertEqual(LINK_MIGRATION_BACKUP_DIR_NAME, "迁移前备份")
        self.assertEqual(ENVIRONMENT_PATH_DIR_NAME, "环境变量Path备份")

    def test_normalize_internal_backup_directories_moves_legacy_names_to_chinese(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backup_root = root / "backups"
            legacy_restore_file = backup_root / LEGACY_RESTORE_BACKUP_DIR_NAME / "old-restore" / "note.txt"
            legacy_migration_file = backup_root / LEGACY_LINK_MIGRATION_BACKUP_DIR_NAME / "old-migration" / "note.txt"
            legacy_environment_file = backup_root / LEGACY_ENVIRONMENT_PATH_DIR_NAME / "old-path" / "path.txt"
            legacy_store_file = backup_root / LEGACY_LINK_STORE_DIR_NAME / ".happy" / "sessions.json"
            for path in [legacy_restore_file, legacy_migration_file, legacy_environment_file, legacy_store_file]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(path.name, encoding="utf-8")

            service = BackupService(backup_root)
            service.normalize_internal_backup_directories()

            self.assertTrue((backup_root / RESTORE_BACKUP_DIR_NAME / "old-restore" / "note.txt").exists())
            self.assertTrue((backup_root / LINK_MIGRATION_BACKUP_DIR_NAME / "old-migration" / "note.txt").exists())
            self.assertTrue((backup_root / ENVIRONMENT_PATH_DIR_NAME / "old-path" / "path.txt").exists())
            self.assertTrue((backup_root / LINK_STORE_DIR_NAME / ".happy" / "sessions.json").exists())
            self.assertFalse((backup_root / LEGACY_RESTORE_BACKUP_DIR_NAME).exists())
            self.assertFalse((backup_root / LEGACY_LINK_MIGRATION_BACKUP_DIR_NAME).exists())
            self.assertFalse((backup_root / LEGACY_ENVIRONMENT_PATH_DIR_NAME).exists())
            self.assertFalse((backup_root / LEGACY_LINK_STORE_DIR_NAME).exists())

    @unittest.skipUnless(os.name == "nt", "Junction 迁移目录重命名只在 Windows 上验证")
    def test_normalize_internal_backup_directories_repoints_legacy_junction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backup_root = root / "backups"
            link_path = root / "home" / ".happy"
            legacy_store = backup_root / LEGACY_LINK_STORE_DIR_NAME / ".happy"
            link_path.parent.mkdir(parents=True)
            legacy_store.mkdir(parents=True)
            (legacy_store / "sessions.json").write_text("data", encoding="utf-8")

            service = BackupService(backup_root)
            service.create_junction(link_path, legacy_store)
            self.assertTrue(link_path.is_junction())

            service.normalize_internal_backup_directories([BackupItem(".happy", link_path)])

            new_store = backup_root / LINK_STORE_DIR_NAME / ".happy"
            self.assertTrue(link_path.is_junction())
            self.assertEqual(Path(os.path.realpath(link_path)), new_store)
            self.assertTrue((new_store / "sessions.json").exists())
            self.assertFalse(legacy_store.exists())

    def test_create_snapshot_generates_unique_name_when_same_second_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "home" / ".happy"
            source.mkdir(parents=True)
            (source / "sessions.json").write_text("data", encoding="utf-8")
            service = BackupService(root / "backups")

            first = service.create_snapshot([BackupItem(".happy", source)], name="same")
            second = service.create_snapshot([BackupItem(".happy", source)], name="same")

            self.assertNotEqual(first.path, second.path)
            self.assertTrue(second.path.name.startswith("same-"))

    def test_create_snapshot_default_name_uses_readable_date_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "home" / ".happy"
            source.mkdir(parents=True)
            (source / "sessions.json").write_text("data", encoding="utf-8")
            service = BackupService(root / "backups")

            snapshot = service.create_snapshot([BackupItem(".happy", source)])

            self.assertRegex(snapshot.path.name, r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$")

    def test_user_settings_round_trip_selected_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "data" / "user-settings.json"

            write_user_settings(
                config_path,
                ["AppData/Roaming/npm", ".ssh"],
                backup_root=Path("D:/backups"),
                schedule_time="21:45",
            )
            settings = load_user_settings(config_path)

            self.assertEqual(settings["selected_items"], ["AppData/Roaming/npm", ".ssh"])
            self.assertEqual(Path(settings["backup_root"]), Path("D:/backups"))
            self.assertEqual(settings["schedule_time"], "21:45")

    def test_user_settings_round_trip_custom_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "data" / "user-settings.json"
            custom_items = [
                {"name": "资料", "path": "D:/资料", "sensitive": False},
                {"name": "密钥", "path": "D:/keys.txt", "sensitive": True},
            ]

            write_user_settings(config_path, [".ssh"], custom_items)
            settings = load_user_settings(config_path)

            self.assertEqual(settings["selected_items"], [".ssh"])
            self.assertEqual(settings["custom_items"], custom_items)

    def test_user_settings_preserves_existing_optional_config_when_only_selection_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "data" / "user-settings.json"
            custom_items = [{"name": "资料", "path": "D:/资料", "sensitive": False}]
            write_user_settings(
                config_path,
                [".ssh", "自定义/资料"],
                custom_items,
                backup_root=Path("D:/backups"),
                schedule_time="21:45",
            )

            write_user_settings(config_path, [])
            settings = load_user_settings(config_path)

            self.assertEqual(settings["selected_items"], [])
            self.assertEqual(settings["custom_items"], custom_items)
            self.assertEqual(Path(settings["backup_root"]), Path("D:/backups"))
            self.assertEqual(settings["schedule_time"], "21:45")

    def test_user_settings_distinguishes_missing_file_from_empty_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "data" / "user-settings.json"

            missing_settings = load_user_settings(config_path)
            self.assertFalse(missing_settings["settings_exists"])

            write_user_settings(config_path, [])
            saved_settings = load_user_settings(config_path)

            self.assertTrue(saved_settings["settings_exists"])
            self.assertEqual(saved_settings["selected_items"], [])

    def test_user_settings_invalid_json_falls_back_to_empty_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "data" / "user-settings.json"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("{bad json", encoding="utf-8")

            settings = load_user_settings(config_path)

            self.assertFalse(settings["settings_exists"])
            self.assertEqual(settings["selected_items"], [])
            self.assertEqual(settings["custom_items"], [])
            self.assertEqual(settings["backup_root"], "")
            self.assertEqual(settings["schedule_time"], "")

    def test_prepare_link_migration_rolls_back_when_move_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "home" / ".happy"
            source.mkdir(parents=True)
            (source / "sessions.json").write_text("data", encoding="utf-8")

            class FailingMoveBackupService(BackupService):
                def _move_path(self, source_path, destination_path):
                    raise OSError("move failed")

            service = FailingMoveBackupService(root / "backups")

            with self.assertRaises(OSError):
                service.prepare_link_migration(BackupItem(".happy", source), root / "link-store")

            self.assertTrue((source / "sessions.json").exists())
            self.assertFalse((root / "link-store" / ".happy").exists())

    def test_restore_skips_missing_snapshot_items_without_removing_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backup_root = root / "backups"
            snapshot = backup_root / "snap"
            snapshot.mkdir(parents=True)
            home = root / "home"
            target = home / ".happy"
            target.mkdir(parents=True)
            (target / "sessions.json").write_text("keep", encoding="utf-8")

            service = BackupService(backup_root)
            result = service.restore_snapshot(snapshot, home, [".happy"])

            self.assertEqual(result.restored_items, [])
            self.assertEqual(result.skipped_items, [".happy"])
            self.assertEqual((target / "sessions.json").read_text(encoding="utf-8"), "keep")

    def test_custom_item_snapshot_restores_to_original_absolute_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source-data"
            source.mkdir()
            (source / "note.txt").write_text("new", encoding="utf-8")
            target = root / "target-data"
            target.mkdir()
            (target / "note.txt").write_text("old", encoding="utf-8")

            service = BackupService(root / "backups")
            snapshot = service.create_snapshot(
                [
                    BackupItem(
                        "自定义/资料",
                        source,
                        sensitive=False,
                        restore_target=target,
                    )
                ],
                name="custom",
            )

            (source / "note.txt").write_text("changed", encoding="utf-8")
            result = service.restore_snapshot(snapshot.path, root / "unused-home", ["自定义/资料"])

            self.assertEqual((target / "note.txt").read_text(encoding="utf-8"), "new")
            self.assertEqual(result.restored_items, ["自定义/资料"])
            self.assertTrue((result.pre_restore_backup_dir / "自定义" / "资料" / "note.txt").exists())

    def test_create_junction_rejects_existing_link_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            link_path = root / ".happy"
            store_path = root / "store"
            link_path.mkdir()
            store_path.mkdir()
            service = BackupService(root / "backups")

            with self.assertRaises(FileExistsError):
                service.create_junction(link_path, store_path)

    def test_failed_snapshot_removes_partial_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "home" / ".happy"
            source.mkdir(parents=True)
            (source / "sessions.json").write_text("data", encoding="utf-8")

            class FailingBackupService(BackupService):
                def _copy_path(self, source_path, destination_path):
                    destination_path.mkdir(parents=True, exist_ok=True)
                    (destination_path / "partial.txt").write_text("partial", encoding="utf-8")
                    raise OSError("copy failed")

            service = FailingBackupService(root / "backups")

            with self.assertRaises(OSError):
                service.create_snapshot([BackupItem(".happy", source)], name="broken")

            self.assertFalse((root / "backups" / "broken").exists())

    def test_read_snapshot_manifest_returns_items_and_missing_selected_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot = root / "backups" / "snap"
            snapshot.mkdir(parents=True)
            manifest = {
                "created_at": "2026-05-19T20:00:00",
                "items": [
                    {"name": ".happy", "source": "C:/Users/example/.happy", "sensitive": True},
                    {"name": ".codex", "source": "C:/Users/example/.codex", "sensitive": True},
                ],
            }
            (snapshot / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            service = BackupService(root / "backups")
            detail = service.read_snapshot_detail(snapshot, selected_names=[".happy", ".ssh"])

            self.assertEqual(detail.created_at, "2026-05-19T20:00:00")
            self.assertEqual(
                detail.items,
                [
                    SnapshotItem(".happy", Path("C:/Users/example/.happy"), True),
                    SnapshotItem(".codex", Path("C:/Users/example/.codex"), True),
                ],
            )
            self.assertEqual(detail.available_selected_names, [".happy"])
            self.assertEqual(detail.missing_selected_names, [".ssh"])
            self.assertEqual(detail.error, "")

    def test_read_snapshot_manifest_reports_missing_or_invalid_manifest_without_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot = root / "backups" / "snap"
            snapshot.mkdir(parents=True)
            service = BackupService(root / "backups")

            missing = service.read_snapshot_detail(snapshot, selected_names=[".happy"])
            self.assertEqual(missing.items, [])
            self.assertEqual(missing.missing_selected_names, [".happy"])
            self.assertIn("manifest.json 不存在", missing.error)

            (snapshot / "manifest.json").write_text("{bad json", encoding="utf-8")
            invalid = service.read_snapshot_detail(snapshot, selected_names=[".happy"])

            self.assertEqual(invalid.items, [])
            self.assertEqual(invalid.missing_selected_names, [".happy"])
            self.assertIn("manifest.json 读取失败", invalid.error)

    def test_backup_environment_path_writes_json_and_text_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = BackupService(root / "backups")

            result = service.backup_environment_path(
                name="2026-05-21_22-10-00",
                user_path=r"C:\UserBin;D:\Tools",
                system_path=r"C:\Windows;C:\Git\cmd",
                process_path=r"C:\Windows;C:\Git\cmd;C:\UserBin;D:\Tools",
            )
            duplicate = service.backup_environment_path(
                name="2026-05-21_22-10-00",
                user_path="",
                system_path="",
                process_path="",
            )

            self.assertEqual(result.path.name, "2026-05-21_22-10-00")
            self.assertEqual(duplicate.path.name, "2026-05-21_22-10-00-01")
            self.assertEqual(result.json_path, result.path / "path.json")
            self.assertEqual(result.text_path, result.path / "path.txt")

            data = json.loads(result.json_path.read_text(encoding="utf-8"))
            self.assertEqual(data["kind"], "environment_path")
            self.assertEqual(data["user_path"], [r"C:\UserBin", r"D:\Tools"])
            self.assertEqual(data["system_path"], [r"C:\Windows", r"C:\Git\cmd"])
            self.assertEqual(data["process_path"], [r"C:\Windows", r"C:\Git\cmd", r"C:\UserBin", r"D:\Tools"])

            text = result.text_path.read_text(encoding="utf-8")
            self.assertIn("[用户 Path]", text)
            self.assertIn(r"C:\UserBin", text)
            self.assertIn("[系统 Path]", text)
            self.assertIn(r"C:\Git\cmd", text)


if __name__ == "__main__":
    unittest.main()
