import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class GuiConfigSyncTests(unittest.TestCase):
    def test_fluent_invalid_schedule_time_does_not_overwrite_when_selection_changes(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp
        from backup_core import load_user_settings, write_user_settings

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            (home / ".ssh").mkdir(parents=True)
            settings_path = root / "data" / "user-settings.json"
            write_user_settings(settings_path, [".ssh"], backup_root=root / "backups", schedule_time="06:30")
            original_with_name = Path.with_name

            def fake_with_name(path: Path, name: str) -> Path:
                if str(path).endswith("app_fluent.py") and name == "data":
                    return root / "data"
                return original_with_name(path, name)

            app = QApplication.instance() or QApplication([])
            with patch("app_fluent.Path.home", return_value=home), patch("app_fluent.Path.with_name", fake_with_name):
                window = FluentBackupApp()

            window.schedule_time.setText("99:99")
            window.set_all_items(False)

            settings = load_user_settings(settings_path)
            self.assertEqual(settings["schedule_time"], "06:30")
            window.close()
            app.quit()

    def test_restore_dialog_copy_mentions_custom_restore_targets_in_fluent_gui(self):
        source = Path("app_fluent.py").read_text(encoding="utf-8")
        self.assertIn("自定义项目恢复到快照记录的原始路径", source)

    def test_tracked_schedule_config_is_not_polluted_by_temp_paths(self):
        schedule = json.loads(Path("data/schedule.json").read_text(encoding="utf-8"))
        serialized = json.dumps(schedule, ensure_ascii=False)

        self.assertNotRegex(serialized, re.compile(r"AppData\\\\Local\\\\Temp|/tmp|\\\\Temp\\\\tmp", re.IGNORECASE))
        self.assertEqual(schedule["backup_root"], r"D:\code\backup")
        self.assertIn("items", schedule)
        self.assertIn("custom_items", schedule)


if __name__ == "__main__":
    unittest.main()
