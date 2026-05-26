import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


class ProjectConfigTests(unittest.TestCase):
    def test_public_product_metadata_uses_release_name_version_and_icon(self):
        import project_config

        self.assertEqual(project_config.APP_TITLE, "Ai会话备份")
        self.assertEqual(project_config.APP_VERSION, "1.0.0")
        self.assertEqual(project_config.GITHUB_REPOSITORY, "myjr2015/ai-session-backup")
        self.assertEqual(project_config.SCHEDULE_TASK_NAME, "Ai会话备份-定时备份")
        schedule_compat_names = [name for name in dir(project_config) if name.startswith("LEGACY") and "SCHEDULE" in name]
        self.assertEqual(schedule_compat_names, [])
        self.assertEqual(project_config.APP_ICON_PATH, Path("assets/app.ico"))
        self.assertTrue(project_config.APP_ICON_PATH.exists())

    def test_default_items_include_expected_user_config_paths(self):
        from project_config import default_items

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            for name in [".happy", ".codex", ".claude", ".ssh", ".cache"]:
                (home / name).mkdir()
            (home / ".gitconfig").write_text("[user]", encoding="utf-8")
            (home / "normal").mkdir()

            items = default_items(home)

        names = [item.name for item in items]
        self.assertEqual(names, [".cache", ".claude", ".codex", ".happy", ".ssh"])
        self.assertNotIn(".gitconfig", names)
        self.assertNotIn("normal", names)

    def test_default_items_falls_back_to_known_dot_folders_when_home_is_not_scannable(self):
        from project_config import default_items

        home = Path("C:/Users/example")
        names = [item.name for item in default_items(home)]

        self.assertEqual(names[:4], [".claude", ".codex", ".happy", ".ssh"])
        self.assertNotIn(".gitconfig", names)

    def test_legacy_fixed_default_selection_detection(self):
        from project_config import is_legacy_fixed_default_selection

        self.assertTrue(is_legacy_fixed_default_selection({".happy", ".codex", ".ssh", "AppData/Roaming/npm"}))
        self.assertFalse(is_legacy_fixed_default_selection({".happy", ".vscode"}))
        self.assertFalse(is_legacy_fixed_default_selection({".ssh"}))
        self.assertFalse(is_legacy_fixed_default_selection(set()))

    def test_sensitive_backup_warning_lists_only_sensitive_items(self):
        from project_config import build_sensitive_backup_warning, default_items

        warning = build_sensitive_backup_warning(default_items(Path("C:/Users/example")))

        self.assertIn("明文备份", warning)
        self.assertIn(".ssh", warning)
        self.assertIn(".codex", warning)
        self.assertNotIn(".gitconfig", warning)

    def test_get_backup_root_prefers_english_key_and_supports_legacy_chinese_key(self):
        from project_config import DEFAULT_BACKUP_ROOT, get_backup_root

        self.assertEqual(DEFAULT_BACKUP_ROOT, Path(r"D:\code\backup"))
        self.assertEqual(get_backup_root({"backup_root": "D:/new"}), Path("D:/new"))
        self.assertEqual(get_backup_root({"backup_root": "D:/config"}, {"backup_root": "D:/settings"}), Path("D:/settings"))
        self.assertEqual(get_backup_root({"默认备份目录": "D:/old"}), Path("D:/old"))

    def test_tracked_config_uses_current_default_backup_root(self):
        from project_config import load_config

        self.assertEqual(load_config().get("backup_root"), r"D:\code\backup")

    def test_load_config_returns_empty_dict_when_file_is_missing(self):
        from project_config import load_config

        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_config(Path(tmp) / "missing.json"), {})

    def test_custom_items_are_loaded_with_stable_snapshot_names(self):
        from project_config import build_backup_items

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            custom_dir = root / "我的资料"
            custom_file = root / "token.txt"
            custom_dir.mkdir()
            custom_file.write_text("secret", encoding="utf-8")

            items = build_backup_items(
                Path("C:/Users/example"),
                [
                    {"path": str(custom_dir), "sensitive": False},
                    {"path": str(custom_file), "name": "令牌文件", "sensitive": True},
                ],
            )

            names = [item.name for item in items]
            self.assertIn("自定义/我的资料", names)
            self.assertIn("自定义/令牌文件", names)
            custom = {item.name: item for item in items if item.name.startswith("自定义/")}
            self.assertEqual(custom["自定义/我的资料"].restore_target, custom_dir)
            self.assertFalse(custom["自定义/我的资料"].sensitive)
            self.assertTrue(custom["自定义/令牌文件"].sensitive)

    def test_backup_cli_does_not_import_legacy_tk_app_at_import_time(self):
        sys.modules.pop("backup_cli", None)
        sys.modules.pop("app", None)

        importlib.import_module("backup_cli")

        self.assertNotIn("app", sys.modules)

    def test_backup_cli_includes_custom_items_when_running_backup(self):
        from backup_cli import run_backup

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            custom = root / "资料"
            custom.mkdir()
            (custom / "note.txt").write_text("data", encoding="utf-8")
            exit_code = run_backup(
                root / "backups",
                {"自定义/资料"},
                [{"name": "资料", "path": str(custom), "sensitive": False}],
            )

            self.assertEqual(exit_code, 0)
            snapshots = [path for path in (root / "backups").iterdir() if path.is_dir()]
            self.assertEqual(len(snapshots), 1)
            self.assertTrue((snapshots[0] / "自定义" / "资料" / "note.txt").exists())

    def test_backup_cli_manual_backup_can_read_custom_items_from_settings(self):
        from backup_cli import run_backup
        from backup_core import write_user_settings

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            custom = root / "资料"
            custom.mkdir()
            (custom / "note.txt").write_text("data", encoding="utf-8")
            settings_path = root / "data" / "user-settings.json"
            write_user_settings(settings_path, [], [{"name": "资料", "path": str(custom), "sensitive": False}])

            exit_code = run_backup(
                root / "backups",
                {"自定义/资料"},
                settings_path=settings_path,
            )

            self.assertEqual(exit_code, 0)
            snapshots = [path for path in (root / "backups").iterdir() if path.is_dir()]
            self.assertEqual(len(snapshots), 1)
            self.assertTrue((snapshots[0] / "自定义" / "资料" / "note.txt").exists())

    def test_backup_cli_scheduled_backup_reads_custom_items_from_config_file(self):
        from backup_cli import main

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            custom = root / "资料"
            custom.mkdir()
            (custom / "note.txt").write_text("data", encoding="utf-8")
            config_path = root / "data" / "schedule.json"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(
                json.dumps(
                    {
                        "backup_root": str(root / "backups"),
                        "items": ["自定义/资料"],
                        "custom_items": [{"name": "资料", "path": str(custom), "sensitive": False}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            original_argv = sys.argv
            sys.argv = ["backup_cli.py", "scheduled-backup", "--config", str(config_path)]
            try:
                exit_code = main()
            finally:
                sys.argv = original_argv

            self.assertEqual(exit_code, 0)
            snapshots = [path for path in (root / "backups").iterdir() if path.is_dir()]
            self.assertEqual(len(snapshots), 1)
            self.assertTrue((snapshots[0] / "自定义" / "资料" / "note.txt").exists())

    def test_newer_entrypoints_do_not_import_shared_config_from_legacy_tk_app(self):
        for filename in ["app_fluent.py", "backup_cli.py"]:
            source = Path(filename).read_text(encoding="utf-8")
            self.assertNotIn("from app import", source, filename)


if __name__ == "__main__":
    unittest.main()
