import os
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


class FluentSmokeTests(unittest.TestCase):
    def test_fluent_window_uses_compact_default_size(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QFrame
        from app_fluent import FluentBackupApp

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()

        self.assertEqual(window.width(), 720)
        self.assertEqual(window.height(), 540)
        self.assertLessEqual(window.minimumWidth(), 672)
        self.assertLessEqual(window.minimumHeight(), 500)
        self.assertLessEqual(window.sizeHint().width(), 720)
        self.assertLessEqual(window.sizeHint().height(), 540)
        self.assertLessEqual(window.minimumSizeHint().width(), 672)
        self.assertLessEqual(window.minimumSizeHint().height(), 500)
        window.close()
        app.quit()

    def test_fluent_window_uses_product_title_and_icon(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import STYLE, FluentBackupApp
        from project_config import APP_TITLE

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()

        self.assertEqual(window.windowTitle(), APP_TITLE)
        self.assertFalse(window.windowIcon().isNull())
        window.close()
        app.quit()

    def test_windows_min_track_size_matches_compact_window_minimum(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from ctypes import POINTER, Structure, addressof, c_void_p, cast
        from ctypes.wintypes import POINT

        from PySide6.QtWidgets import QApplication
        from app_fluent import APP_MINIMUM_SIZE, FluentBackupApp, NativeMinMaxInfo

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()

        info = NativeMinMaxInfo()
        info.ptMinTrackSize = POINT(900, 667)
        handled = window.apply_compact_min_track_size(addressof(info))

        self.assertTrue(handled)
        self.assertEqual(info.ptMinTrackSize.x, APP_MINIMUM_SIZE.width())
        self.assertEqual(info.ptMinTrackSize.y, APP_MINIMUM_SIZE.height())

        class Message(Structure):
            _fields_ = [("lParam", c_void_p)]

        message = Message(addressof(info))
        pointer = cast(addressof(message), POINTER(Message))
        handled = window.handle_min_track_message(pointer)

        self.assertTrue(handled)
        self.assertEqual(info.ptMinTrackSize.x, APP_MINIMUM_SIZE.width())
        self.assertEqual(info.ptMinTrackSize.y, APP_MINIMUM_SIZE.height())
        window.close()
        app.quit()

    def test_system_move_position_change_keeps_starting_window_size(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from ctypes import addressof

        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp, NativeWindowPos

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()

        window.resize(720, 540)
        window._set_current_page(window.items_page)
        window.begin_system_move_size_guard()
        pos = NativeWindowPos()
        pos.x = 360
        pos.y = 230
        pos.cx = 720
        pos.cy = 667

        handled = window.keep_system_move_size(addressof(pos))

        self.assertTrue(handled)
        self.assertEqual((pos.x, pos.y), (360, 230))
        self.assertEqual((pos.cx, pos.cy), (720, 540))

        window.end_system_move_size_guard()
        pos.cy = 667
        self.assertFalse(window.keep_system_move_size(addressof(pos)))
        self.assertEqual(pos.cy, 667)
        window.close()
        app.quit()

    def test_fluent_app_uses_default_ui_theme_settings(self):
        from PySide6.QtGui import QColor
        from qfluentwidgets import Theme, qconfig
        from app_fluent import DEFAULT_THEME_COLOR, DEFAULT_THEME_MODE, apply_default_ui_theme

        self.assertEqual(DEFAULT_THEME_MODE, Theme.AUTO)
        self.assertEqual(QColor(DEFAULT_THEME_COLOR).name(), "#0078d4")

        apply_default_ui_theme()

        self.assertEqual(qconfig.themeMode.value, Theme.AUTO)
        self.assertEqual(qconfig.themeColor.value.name(), "#0078d4")

    def test_fluent_window_loads_saved_selected_items(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QFrame
        from app_fluent import FluentBackupApp
        from backup_core import write_user_settings

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            (home / ".ssh").mkdir(parents=True)
            (home / ".codex").mkdir()
            settings_path = root / "data" / "user-settings.json"
            write_user_settings(settings_path, [".ssh"])
            original_with_name = Path.with_name

            def fake_with_name(path: Path, name: str) -> Path:
                if str(path).endswith("app_fluent.py") and name == "data":
                    return root / "data"
                return original_with_name(path, name)

            app = QApplication.instance() or QApplication([])
            with patch("app_fluent.Path.home", return_value=home), patch("app_fluent.Path.with_name", fake_with_name):
                window = FluentBackupApp()

            self.assertEqual(window.selected_names, {".ssh"})
            window.close()
            app.quit()

    def test_fluent_migrates_legacy_fixed_default_selection_to_existing_dot_folders(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import STYLE, FluentBackupApp
        from backup_core import write_user_settings

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            (home / ".codex").mkdir(parents=True)
            (home / ".vscode").mkdir()
            settings_path = root / "data" / "user-settings.json"
            write_user_settings(settings_path, [".happy", ".codex", ".claude", ".ssh", "AppData/Roaming/npm"])
            original_with_name = Path.with_name

            def fake_with_name(path: Path, name: str) -> Path:
                if str(path).endswith("app_fluent.py") and name == "data":
                    return root / "data"
                return original_with_name(path, name)

            app = QApplication.instance() or QApplication([])
            with patch("app_fluent.Path.home", return_value=home), patch("app_fluent.Path.with_name", fake_with_name):
                window = FluentBackupApp()

            self.assertEqual(window.selected_names, {".codex", ".vscode"})
            window.close()
            app.quit()

    def test_fluent_window_loads_saved_custom_items(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QFrame
        from app_fluent import FluentBackupApp
        from backup_core import write_user_settings

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            custom = root / "my-config"
            home.mkdir()
            custom.mkdir()
            settings_path = root / "data" / "user-settings.json"
            write_user_settings(
                settings_path,
                ["自定义/my-config"],
                [{"path": str(custom), "sensitive": False}],
            )
            original_with_name = Path.with_name

            def fake_with_name(path: Path, name: str) -> Path:
                if str(path).endswith("app_fluent.py") and name == "data":
                    return root / "data"
                return original_with_name(path, name)

            app = QApplication.instance() or QApplication([])
            with patch("app_fluent.Path.home", return_value=home), patch("app_fluent.Path.with_name", fake_with_name):
                window = FluentBackupApp()

            item_names = [item.name for item in window.items]
            self.assertIn("自定义/my-config", item_names)
            self.assertIn("自定义/my-config", window.selected_names)
            self.assertNotIn("自定义/my-config", [card.item.name for card in window.link_cards])
            window.close()
            app.quit()

    def test_fluent_window_loads_saved_backup_root_and_uses_text_navigation(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp
        from backup_core import write_user_settings

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            backup_root = root / "saved-backups"
            home.mkdir()
            settings_path = root / "data" / "user-settings.json"
            write_user_settings(settings_path, [], backup_root=backup_root, schedule_time="06:30")
            original_with_name = Path.with_name

            def fake_with_name(path: Path, name: str) -> Path:
                if str(path).endswith("app_fluent.py") and name == "data":
                    return root / "data"
                return original_with_name(path, name)

            app = QApplication.instance() or QApplication([])
            with patch("app_fluent.Path.home", return_value=home), patch("app_fluent.Path.with_name", fake_with_name):
                window = FluentBackupApp()

            self.assertEqual(window.backup_root, backup_root)
            self.assertEqual(window.backup_root_edit.text(), str(backup_root))
            self.assertEqual(window.schedule_time.text(), "06:30")
            self.assertGreaterEqual(window.navigation.minimumWidth(), 48)
            self.assertEqual(len(window.navigation_buttons), 7)
            self.assertEqual(
                [button.text() for button in window.navigation_buttons],
                ["总览", "备份", "恢复", "迁移", "任务计划", "环境", "日志"],
            )
            for button in window.navigation_buttons:
                self.assertFalse(button.icon().isNull())
            window._set_current_page(window.task_page)
            self.assertEqual(window.navigation.currentItem().property("routeKey"), "task")
            window._set_current_page(window.environment_page)
            self.assertEqual(window.navigation.currentItem().property("routeKey"), "environment")
            window.close()
            app.quit()

    def test_fluent_navigation_clicks_switch_pages(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()

        page_pairs = [
            (0, window.dashboard_page),
            (1, window.items_page),
            (2, window.restore_page),
            (3, window.link_page),
            (4, window.task_page),
            (5, window.environment_page),
            (6, window.log_page),
        ]
        for index, page in page_pairs:
            window.navigation_buttons[index].click()
            app.processEvents()
            self.assertIs(window.stack.currentWidget(), page)

        window.close()
        app.quit()

    def test_fluent_layout_keeps_key_controls_visible_at_supported_sizes(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()

        for width, height in [(720, 540), (672, 500)]:
            window.resize(width, height)
            app.processEvents()

            self.assertGreaterEqual(window.navigation.minimumWidth(), 48)
            self.assertGreaterEqual(window.backup_root_edit.width(), 120)
            self.assertGreater(window.schedule_time.width(), 60)
            self.assertGreater(window.dashboard_metrics_panel.width(), 0)
            self.assertFalse(hasattr(window, "inline_log"))
            self.assertFalse(hasattr(window, "snapshot_list"))

            window._set_current_page(window.items_page)
            app.processEvents()
            self.assertGreater(window.item_container.width(), 0)
            self.assertGreater(window.item_container.height(), 0)
            self.assertFalse(window.item_scroll.horizontalScrollBar().isVisible())

            window._set_current_page(window.restore_page)
            app.processEvents()
            self.assertGreater(window.restore_snapshot_list.width(), 0)
            self.assertGreater(window.restore_snapshot_detail.width(), 0)

        window.close()
        app.quit()

    def test_fluent_solution_three_layout_has_workbench_structure(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QFrame
        from qfluentwidgets import FlowLayout
        from app_fluent import FluentBackupApp

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()
        window.resize(720, 540)
        window.show()
        app.processEvents()

        self.assertEqual(window.dashboard_workspace.objectName(), "DashboardWorkspace")
        self.assertEqual(window.dashboard_main_panel.objectName(), "DashboardMainPanel")
        self.assertEqual(window.dashboard_metrics_panel.objectName(), "DashboardMetricsPanel")
        self.assertFalse(hasattr(window, "dashboard_snapshots_panel"))
        self.assertFalse(hasattr(window, "dashboard_log_panel"))
        self.assertGreaterEqual(window.backup_root_edit.width(), 120)
        self.assertGreater(window.schedule_time.width(), 60)

        window._set_current_page(window.items_page)
        app.processEvents()
        self.assertEqual(window.items_toolbar.objectName(), "ItemsGroupedToolbar")
        self.assertFalse(window.items_page.findChildren(QFrame, "ItemsExecutionGroup"))
        self.assertFalse(window.item_scroll.horizontalScrollBar().isVisible())

        window._set_current_page(window.restore_page)
        app.processEvents()
        self.assertEqual(window.restore_workspace.objectName(), "RestoreWorkspace")
        self.assertGreaterEqual(window.restore_snapshot_list.width(), 120)
        self.assertGreater(window.restore_detail_panel.width(), window.restore_snapshot_list.width())

        window._set_current_page(window.link_page)
        app.processEvents()
        self.assertIsInstance(window.link_toolbar.layout(), FlowLayout)
        self.assertFalse(window.link_page.findChildren(QFrame, "DashboardSidePanel"))
        self.assertEqual(window.link_terms_card.objectName(), "LinkTermsCard")
        terms_text = window.link_terms_text.text()
        self.assertIn("Junction", terms_text)
        self.assertIn("迁移后的真实目录", terms_text)
        self.assertIn("恢复前备份", terms_text)
        self.assertIn("取消迁移", terms_text)
        self.assertIn("原位置", terms_text)
        self.assertIn("D 盘", terms_text)
        self.assertTrue(hasattr(window, "link_scroll"))
        self.assertTrue(hasattr(window, "link_cards"))
        self.assertFalse(hasattr(window, "link_list"))
        self.assertFalse(hasattr(window, "link_combo"))

        window.close()
        app.quit()

    def test_dashboard_explains_when_to_use_backup_or_migration(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()

        self.assertEqual(window.protection_guide_card.objectName(), "ProtectionGuideCard")
        guide_text = window.protection_guide_text.text()
        self.assertIn("备份：", guide_text)
        self.assertIn("数据还是放在C盘", guide_text)
        self.assertIn("定时或手工备份", guide_text)
        self.assertIn("迁移：", guide_text)
        self.assertIn("Junction技术", guide_text)
        self.assertIn("不再写入C盘", guide_text)

        window.close()
        app.quit()

    def test_fluent_compact_density_limits_card_and_panel_sizes(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()
        window.resize(720, 540)
        window.show()
        window._wait_for_thread(window.scan_worker)
        app.processEvents()

        self.assertLessEqual(window.restore_snapshot_list.parentWidget().maximumWidth(), 204)
        self.assertLessEqual(window.backup_root_edit.minimumWidth(), 130)
        window.close()
        app.quit()

    def test_fluent_action_buttons_use_default_auto_width_style(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QPushButton
        from qfluentwidgets import ComboBox
        from app_fluent import (
            APP_BUTTON_HEIGHT,
            FluentBackupApp,
        )

        self.assertEqual(APP_BUTTON_HEIGHT, 30)

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()
        window.resize(720, 540)
        window.show()
        app.processEvents()

        action_buttons = [
            button
            for page in [
                window.dashboard_page,
                window.items_page,
                window.restore_page,
                window.link_page,
                window.task_page,
                window.environment_page,
            ]
            for button in page.findChildren(QPushButton)
            if button not in window.navigation_buttons and not isinstance(button, ComboBox)
        ]
        expected_texts = {
            "刷新",
            "选择",
            "保存",
            "打开",
            "立即备份",
            "创建/更新",
            "删除",
            "全选",
            "全不选",
            "添加文件夹",
            "添加文件",
            "删除已勾选自定义",
            "恢复选中快照",
            "迁移",
            "取消迁移",
            "打开任务计划程序",
            "备份 Path",
            "以管理员身份打开环境变量",
        }
        buttons_by_text = {button.text(): button for button in action_buttons}
        self.assertEqual(set(buttons_by_text), expected_texts)
        self.assertNotIn("AppButton", {button.objectName() for button in action_buttons})
        self.assertEqual({button.height() for button in action_buttons}, {30})
        for button in action_buttons:
            self.assertEqual(button.minimumHeight(), 30)
            self.assertEqual(button.maximumHeight(), 30)
            self.assertEqual(button.minimumWidth(), 0)
            self.assertEqual(button.maximumWidth(), 16777215)
            self.assertNotIn("#dbeafe", button.styleSheet())
            self.assertNotIn("#1d4ed8", button.styleSheet())
        self.assertGreater(
            buttons_by_text["删除已勾选自定义"].sizeHint().width(),
            buttons_by_text["删除"].sizeHint().width(),
        )
        self.assertEqual(window.backup_root_edit.height(), 32)
        self.assertEqual(window.schedule_time.height(), 32)

        window.close()
        app.quit()

    def test_backup_item_card_keeps_long_paths_to_compact_single_line(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QLabel
        from app_fluent import BackupItemCard
        from backup_core import BackupItem, ScannedItem

        app = QApplication.instance() or QApplication([])
        long_source = Path("C:/Users/example/.codex") / ("very-long-folder-name" * 8)
        scanned = ScannedItem(
            BackupItem(".codex", long_source),
            True,
            1024,
            datetime(2026, 5, 20, 9, 30),
        )
        card = BackupItemCard(scanned, True)

        self.assertLessEqual(card.sizeHint().height(), 42)
        labels = [label for label in card.findChildren(QLabel) if label.objectName() == "ItemTitleLine"]
        self.assertEqual(labels, [card.title_line])
        detail_text = card.title_line.text().replace("\\", "/")
        self.assertIn("<strong>.codex</strong>", detail_text)
        self.assertIn("C:/Users/example/.codex", detail_text)
        self.assertIn("1.0 KB", detail_text)
        self.assertIn("2026-05-20 09:30", detail_text)
        self.assertNotIn("<strong>C:/Users/example/.codex", detail_text)
        self.assertNotEqual(card.checkbox.lightCheckedColor.name(), "#bfdbfe")
        self.assertNotEqual(card.checkbox.darkCheckedColor.name(), "#60a5fa")
        card.close()
        app.quit()

    def test_backup_item_card_uses_single_open_directory_context_menu(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        from app_fluent import BackupItemCard
        from backup_core import BackupItem, ScannedItem

        app = QApplication.instance() or QApplication([])
        source = Path("C:/Users/example/.vscode")
        card = BackupItemCard(ScannedItem(BackupItem(".vscode", source), True, 1024, None), True)

        self.assertEqual(card.contextMenuPolicy(), Qt.ContextMenuPolicy.CustomContextMenu)
        self.assertEqual(card.title_line.contextMenuPolicy(), Qt.ContextMenuPolicy.CustomContextMenu)
        self.assertEqual([action.text() for action in card.context_menu_actions()], ["打开当前目录"])

        opened = []
        card.open_directory_requested.connect(lambda path: opened.append(path))
        card.context_menu_actions()[0].trigger()
        self.assertEqual(opened, [source])

        card.close()
        app.quit()

    def test_link_card_can_open_source_and_real_migrated_directories(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import STYLE, FluentBackupApp
        from backup_core import BackupItem, LinkMigrationStatus, ScannedItem

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()
        item = BackupItem(".vscode", Path("C:/Users/example/.vscode"))
        store_path = Path("D:/code/backup/迁移后的真实目录/.vscode")
        status = LinkMigrationStatus(
            state="migrated",
            label="已迁移",
            detail=f"C 盘引用：{item.source}；D 盘真实目录：{store_path}",
            link_path=item.source,
            store_path=store_path,
            can_migrate=False,
            can_cancel=True,
        )

        with patch.object(window.service, "get_link_migration_status", return_value=status):
            window.apply_scanned_items([ScannedItem(item, True, 100, datetime(2026, 5, 24, 1, 0))])

        card = window.link_cards[0]
        self.assertEqual([action.text() for action in card.context_menu_actions()], ["打开原位置", "打开真实目录"])

        opened = []
        card.open_directory_requested.connect(lambda path: opened.append(path))
        with patch.object(window, "open_current_directory"):
            card.context_menu_actions()[0].trigger()
            card.context_menu_actions()[1].trigger()

        self.assertEqual(opened, [item.source, store_path])
        window.close()
        app.quit()

    def test_fluent_item_sort_modes_order_scanned_items(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp
        from backup_core import BackupItem, ScannedItem

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()
        scanned = [
            ScannedItem(BackupItem(".small", Path("C:/Users/example/.small")), True, 10, datetime(2026, 5, 19, 9, 0)),
            ScannedItem(BackupItem(".large", Path("C:/Users/example/.large")), True, 300, datetime(2026, 5, 18, 9, 0)),
            ScannedItem(BackupItem(".recent", Path("C:/Users/example/.recent")), True, 100, datetime(2026, 5, 20, 9, 0)),
        ]

        window.apply_scanned_items(scanned)
        self.assertEqual(window.item_sort_combo.currentText(), "从大到小")
        self.assertEqual([window.item_sort_combo.itemText(index) for index in range(window.item_sort_combo.count())], ["从大到小", "从小到大", "最近更新"])
        self.assertEqual([card.item.name for card in window.item_cards], [".large", ".recent", ".small"])
        self.assertFalse(window.item_scroll.horizontalScrollBar().isVisible())

        window.item_sort_combo.setCurrentText("从小到大")
        self.assertEqual([card.item.name for card in window.item_cards], [".small", ".recent", ".large"])

        window.item_sort_combo.setCurrentText("最近更新")
        self.assertEqual([card.item.name for card in window.item_cards], [".recent", ".small", ".large"])

        window.close()
        app.quit()

    def test_fluent_removes_duplicate_navigation_shortcuts_from_pages(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QPushButton
        from app_fluent import FluentBackupApp

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()

        page_buttons = [
            button.text()
            for page in [window.dashboard_page, window.items_page]
            for button in page.findChildren(QPushButton)
        ]
        self.assertNotIn("管理项目", page_buttons)
        self.assertNotIn("恢复快照", page_buttons)
        self.assertNotIn("查看全部", page_buttons)
        self.assertEqual(window.dashboard_page.findChildren(QPushButton, "BackupNowButton"), [])
        self.assertEqual(len(window.items_page.findChildren(QPushButton, "BackupNowButton")), 1)
        self.assertEqual(page_buttons.count("立即备份"), 1)

        window.close()
        app.quit()

    def test_link_page_explains_junction_terms(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QLabel
        from app_fluent import FluentBackupApp

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()
        window.show()
        app.processEvents()

        labels = [label.text() for label in window.link_page.findChildren(QLabel)]
        combined_text = "\n".join(labels)
        self.assertIn("Junction是什么", combined_text)
        self.assertIn("Junction", combined_text)
        self.assertIn("迁移后的真实目录", combined_text)
        self.assertIn("不支持单文件", combined_text)
        self.assertIn("取消迁移", combined_text)
        self.assertIn("原位置", combined_text)
        self.assertIn("迁移", combined_text)

        window.close()
        app.quit()

    def test_task_and_environment_pages_expose_system_entry_points(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QLabel
        from app_fluent import FluentBackupApp

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()

        self.assertEqual(window.task_page.objectName(), "task")
        self.assertEqual(window.environment_page.objectName(), "environment")
        task_text = "\n".join(label.text() for label in window.task_page.findChildren(QLabel))
        self.assertIn("任务计划", task_text)
        self.assertNotIn("计划任务", task_text)
        self.assertIn("Path", window.environment_page_summary.text())
        self.assertEqual(
            window.open_task_scheduler_command(),
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                "Start-Process mmc.exe -ArgumentList 'taskschd.msc' -Verb RunAs",
            ],
        )
        self.assertEqual(
            window.open_environment_variables_command(),
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                "Start-Process rundll32.exe -ArgumentList 'sysdm.cpl,EditEnvironmentVariables' -Verb RunAs",
            ],
        )

        with patch("app_fluent.subprocess.Popen") as popen:
            window.open_task_scheduler()
            popen.assert_called_once_with(window.open_task_scheduler_command())
        with patch("app_fluent.subprocess.Popen") as popen:
            window.open_environment_variables()
            popen.assert_called_once_with(window.open_environment_variables_command())

        window.close()
        app.quit()

    def test_schedule_status_accepts_legacy_task_name(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp

        class Result:
            def __init__(self, returncode: int) -> None:
                self.returncode = returncode

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()
        with patch.object(window, "query_schedule_task", return_value=Result(1)), patch.object(
            window, "query_legacy_schedule_tasks", return_value=[Result(0)]
        ):
            window.refresh_schedule_status()

        self.assertEqual(window.schedule_status.text(), "状态：已创建")
        window.close()
        app.quit()

    def test_schedule_task_query_uses_hidden_subprocess_window(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()

        with patch("app_fluent.subprocess.run") as run:
            run.return_value.returncode = 1
            window.query_schedule_task("demo-task")

        _, kwargs = run.call_args
        if os.name == "nt":
            self.assertIn("startupinfo", kwargs)
            self.assertIn("creationflags", kwargs)
        self.assertTrue(kwargs["capture_output"])
        window.close()
        app.quit()

    def test_environment_page_can_backup_path_variables(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp

        with tempfile.TemporaryDirectory() as tmp:
            app = QApplication.instance() or QApplication([])
            window = FluentBackupApp()
            window.backup_root = Path(tmp) / "backups"
            window.service = window.service.__class__(window.backup_root)

            result = window.backup_environment_path(
                name="2026-05-21_22-20-00",
                user_path=r"C:\UserBin",
                system_path=r"C:\Windows",
                process_path=r"C:\Windows;C:\UserBin",
            )

            self.assertEqual(result.path, window.backup_root / "环境变量Path备份" / "2026-05-21_22-20-00")
            self.assertTrue(result.json_path.exists())
            self.assertTrue(result.text_path.exists())
            self.assertIn("环境变量 Path 已备份", window.log.toPlainText())
            self.assertIn(str(result.path), window.log.toPlainText())

            window.close()
            app.quit()

    def test_main_page_copy_uses_user_facing_navigation_names(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QLabel
        from app_fluent import FluentBackupApp

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()

        items_text = "\n".join(label.text() for label in window.items_page.findChildren(QLabel))
        link_text = "\n".join(label.text() for label in window.link_page.findChildren(QLabel))

        self.assertIn("备份", items_text)
        self.assertIn("备份列表", items_text)
        self.assertIn("正在扫描备份内容", window.protection_summary.text())
        self.assertNotIn("备份项目", items_text)
        self.assertNotIn("项目列表", items_text)

        self.assertIn("迁移", link_text)
        self.assertIn("迁移列表", link_text)
        self.assertNotIn("链接迁移", link_text)

        window.close()
        app.quit()

    def test_link_list_follows_backup_card_style_sort_order_and_multi_selection(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import BackupItemCard, FluentBackupApp
        from backup_core import BackupItem, ScannedItem

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()
        scanned = [
            ScannedItem(BackupItem(".small", Path("C:/Users/example/.small")), True, 10, datetime(2026, 5, 19, 9, 0)),
            ScannedItem(BackupItem(".large", Path("C:/Users/example/.large")), True, 300, datetime(2026, 5, 18, 9, 0)),
            ScannedItem(BackupItem(".recent", Path("C:/Users/example/.recent")), True, 100, datetime(2026, 5, 20, 9, 0)),
            ScannedItem(BackupItem("自定义/data", Path("D:/data")), True, 999, datetime(2026, 5, 21, 9, 0)),
        ]

        window.apply_scanned_items(scanned)
        self.assertEqual(window.link_sort_combo.currentText(), "已经迁移")
        self.assertEqual([card.item.name for card in window.link_cards], [".recent", ".small", ".large"])
        window.link_sort_combo.setCurrentText("最近更新")
        self.assertEqual([card.item.name for card in window.link_cards], [".recent", ".small", ".large"])
        self.assertTrue(all(isinstance(card, BackupItemCard) for card in window.link_cards))
        self.assertFalse(window.link_scroll.horizontalScrollBar().isVisible())

        window.link_sort_combo.setCurrentText("从大到小")
        self.assertEqual([card.item.name for card in window.link_cards], [".large", ".recent", ".small"])

        window.link_cards[1].checkbox.setChecked(True)
        window.link_sort_combo.setCurrentText("从小到大")
        self.assertEqual([card.item.name for card in window.link_cards], [".small", ".recent", ".large"])
        self.assertEqual([card.item.name for card in window.link_cards if card.checkbox.isChecked()], [".recent"])

        window.link_cards[0].checkbox.setChecked(True)
        window.link_cards[1].checkbox.setChecked(True)
        self.assertEqual([item.name for item in window._selected_link_items()], [".small", ".recent"])

        window.close()
        app.quit()

    def test_link_page_matches_backup_page_toolbar_layout(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QFrame
        from app_fluent import FluentBackupApp

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()

        self.assertEqual(window.link_toolbar.objectName(), "ItemsGroupedToolbar")
        self.assertEqual(window.link_selection_group.objectName(), "ToolbarGroup")
        self.assertEqual(window.link_action_group.objectName(), "ToolbarGroup")
        self.assertEqual(window.link_cancel_group.objectName(), "ToolbarGroup")
        self.assertEqual(window.cancel_migration_button.text(), "取消迁移")
        self.assertEqual(window.link_refresh_group.objectName(), "ToolbarGroup")
        self.assertEqual(window.refresh_link_button.text(), "刷新")
        self.assertIn("color: #c42b1c", window.link_hint.styleSheet())
        self.assertEqual(window.link_sort_combo.currentText(), "已经迁移")
        self.assertEqual([window.link_sort_combo.itemText(index) for index in range(window.link_sort_combo.count())], ["已经迁移", "从大到小", "从小到大", "最近更新"])
        self.assertGreaterEqual(len(window.link_page.findChildren(QFrame, "ToolbarGroup")), 4)

        window.close()
        app.quit()

    def test_link_refresh_button_recalculates_status_after_external_change(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp
        from backup_core import BackupItem, LinkMigrationStatus, ScannedItem

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()
        item = BackupItem(".codex", Path("C:/Users/example/.codex"))
        store_path = Path("D:/code/backup/迁移后的真实目录/.codex")
        state = {"value": "broken"}

        def status_for_item(_item):
            if state["value"] == "broken":
                return LinkMigrationStatus(
                    state="broken",
                    label="异常",
                    detail="",
                    link_path=item.source,
                    store_path=store_path,
                    can_migrate=False,
                    can_cancel=False,
                    problem="迁移后的真实目录已存在，但 C 盘原位置不是 Junction。",
                )
            return LinkMigrationStatus(
                state="normal",
                label="未迁移",
                detail="",
                link_path=item.source,
                store_path=store_path,
                can_migrate=True,
                can_cancel=False,
            )

        with patch.object(window.service, "get_link_migration_status", side_effect=status_for_item), patch(
            "app_fluent.QToolTip.hideText"
        ) as hide_tooltip, patch.object(window, "refresh_items") as refresh_items:
            window.apply_scanned_items([ScannedItem(item, True, 100, datetime(2026, 5, 26, 12, 0))])
            self.assertIn("异常", window.link_cards[0].title_line.text())
            old_cards = list(window.link_cards)

            state["value"] = "normal"
            window.refresh_link_button.click()

            self.assertIn("未迁移", window.link_cards[0].title_line.text())
            self.assertNotIn(old_cards[0], window.link_cards)
            hide_tooltip.assert_called()
            refresh_items.assert_not_called()

        window.close()
        app.quit()

    def test_link_sort_migrated_first_and_highlights_migrated_cards(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import STYLE, FluentBackupApp
        from backup_core import BackupItem, LinkMigrationStatus, ScannedItem

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()
        migrated_item = BackupItem(".migrated", Path("C:/Users/example/.migrated"))
        normal_item = BackupItem(".normal", Path("C:/Users/example/.normal"))
        broken_item = BackupItem(".broken", Path("C:/Users/example/.broken"))
        scanned = [
            ScannedItem(normal_item, True, 300, datetime(2026, 5, 22, 9, 0)),
            ScannedItem(migrated_item, True, 10, datetime(2026, 5, 20, 9, 0)),
            ScannedItem(broken_item, True, 100, datetime(2026, 5, 21, 9, 0)),
        ]

        statuses = {
            ".migrated": LinkMigrationStatus("migrated", "已迁移", "已迁移", migrated_item.source, Path("D:/store/.migrated"), False, True),
            ".normal": LinkMigrationStatus("normal", "未迁移", "未迁移", normal_item.source, Path("D:/store/.normal"), True, False),
            ".broken": LinkMigrationStatus("broken", "异常", "异常", broken_item.source, Path("D:/store/.broken"), False, False, "需要手动检查"),
        }

        with patch.object(window.service, "get_link_migration_status", side_effect=lambda item: statuses[item.name]):
            window.apply_scanned_items(scanned)

        self.assertEqual(window.link_sort_combo.currentText(), "已经迁移")
        self.assertEqual([card.item.name for card in window.link_cards], [".migrated", ".broken", ".normal"])
        self.assertTrue(window.link_cards[0].property("migrated"))
        self.assertFalse(window.link_cards[0].property("broken"))
        self.assertEqual(window.link_cards[0].objectName(), "MigratedLinkCard")
        self.assertIn("background: rgba(0, 120, 212, 0.24)", STYLE)
        self.assertIn("已迁移", window.link_cards[0].title_line.text())
        self.assertFalse(window.link_cards[1].property("migrated"))
        self.assertTrue(window.link_cards[1].property("broken"))
        self.assertEqual(window.link_cards[1].objectName(), "BrokenLinkCard")
        self.assertIn("background: rgba(255, 185, 0, 0.20)", STYLE)
        self.assertFalse(window.link_cards[1].property("migrated"))
        self.assertFalse(window.link_cards[2].property("migrated"))
        self.assertFalse(window.link_cards[2].property("broken"))
        window.link_sort_combo.setCurrentText("从大到小")
        self.assertEqual([card.item.name for card in window.link_cards], [".normal", ".broken", ".migrated"])

        window.close()
        app.quit()

    def test_info_bar_replaces_previous_notification_to_avoid_taskbar_window_buildup(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp

        class DummySignal:
            def __init__(self):
                self.callbacks = []

            def connect(self, callback):
                self.callbacks.append(callback)

            def emit(self):
                for callback in list(self.callbacks):
                    callback()

        class DummyInfoBar:
            def __init__(self):
                self.closedSignal = DummySignal()
                self.destroyed = DummySignal()
                self.closed = False

            def close(self):
                self.closed = True
                self.closedSignal.emit()

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()
        bars = []
        cleanup_calls = []

        def factory(**_kwargs):
            bar = DummyInfoBar()
            bars.append(bar)
            return bar

        with patch.object(window, "_cleanup_orphan_pythonw_info_windows", side_effect=lambda: cleanup_calls.append("cleanup")):
            window._show_info_bar(factory, "提示", "第一条", 1)
            self.assertIs(window._active_info_bar, bars[0])

            window._show_info_bar(factory, "提示", "第二条", 1)

            self.assertTrue(bars[0].closed)
            self.assertIs(window._active_info_bar, bars[1])
            self.assertFalse(bars[1].closed)
            self.assertGreaterEqual(len(cleanup_calls), 2)

            window._close_active_info_bar()
            self.assertTrue(bars[1].closed)
            self.assertIsNone(window._active_info_bar)

        window.close()
        app.quit()

    def test_link_page_marks_migrated_items_and_uses_cancel_action(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp
        from backup_core import LinkMigrationStatus
        from backup_core import BackupItem, ScannedItem

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()
        item = BackupItem(".vscode", Path("C:/Users/example/.vscode"))
        scanned = [ScannedItem(item, True, 100, datetime(2026, 5, 24, 1, 0))]
        store_path = Path("D:/code/backup/迁移后的真实目录/.vscode")
        migrated = LinkMigrationStatus(
            state="migrated",
            label="已迁移",
            detail=f"C 盘引用：{item.source}；D 盘真实目录：{store_path}",
            link_path=item.source,
            store_path=store_path,
            can_migrate=False,
            can_cancel=True,
        )

        with patch.object(window.service, "get_link_migration_status", return_value=migrated), patch.object(
            window.service, "cancel_link_migration"
        ) as cancel, patch.object(
            window, "_run_worker", side_effect=lambda job, refresh=True, success_text="", after_success=None, after_failed=None, on_failed=None: job(lambda message: None)
        ) as run_worker:
            window.apply_scanned_items(scanned)

            self.assertEqual([card.item.name for card in window.link_cards], [".vscode"])
            self.assertTrue(window.link_cards[0].checkbox.isChecked() is False)
            self.assertIn("已迁移", window.link_cards[0].title_line.text())
            self.assertIn(str(store_path), window.link_cards[0].title_line.toolTip())
            window.link_cards[0].checkbox.setChecked(True)
            self.assertIn("已迁移，可取消迁移", window.link_hint.text())
            window.cancel_selected_link_migration(confirm=False)

        cancel.assert_called_once_with(item)
        run_worker.assert_called_once()
        window.close()
        app.quit()

    def test_link_migrate_and_cancel_actions_do_not_show_confirmation_dialogs_by_default(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp
        from backup_core import BackupItem, LinkCancelResult, LinkMigrationResult, LinkMigrationStatus, ScannedItem

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()
        item = BackupItem(".codex", Path("C:/Users/example/.codex"))
        store_path = Path("D:/code/backup/迁移后的真实目录/.codex")
        normal = LinkMigrationStatus(
            state="normal",
            label="未迁移",
            detail=f"C 盘原目录：{item.source}；迁移后真实目录：{store_path}",
            link_path=item.source,
            store_path=store_path,
            can_migrate=True,
            can_cancel=False,
        )
        migrated = LinkMigrationStatus(
            state="migrated",
            label="已迁移",
            detail=f"C 盘引用：{item.source}；D 盘真实目录：{store_path}",
            link_path=item.source,
            store_path=store_path,
            can_migrate=False,
            can_cancel=True,
        )

        window.apply_scanned_items([ScannedItem(item, True, 100, datetime(2026, 5, 24, 1, 0))])
        window.link_cards[0].checkbox.setChecked(True)

        worker_calls = []

        def run_worker_without_dialog(job, refresh=True, success_text="", after_success=None, after_failed=None, on_failed=None):
            worker_calls.append({"refresh": refresh, "success_text": success_text, "after_success": after_success, "after_failed": after_failed})
            job(lambda message: None)
            if after_success is not None:
                after_success()

        with patch.object(window.service, "get_link_migration_status", return_value=normal), patch.object(
            window.service, "prepare_link_migration", return_value=LinkMigrationResult(item.source, store_path, Path("D:/backup/pre"))
        ) as prepare, patch.object(window.service, "create_junction") as junction, patch.object(
            window, "_run_worker", side_effect=run_worker_without_dialog
        ), patch("app_fluent.QMessageBox.question") as question:
            window.migrate_selected_link()

        question.assert_not_called()
        prepare.assert_called_once_with(item, window.service.default_link_store_root())
        junction.assert_called_once_with(item.source, store_path)
        self.assertFalse(worker_calls[-1]["refresh"])
        self.assertEqual(worker_calls[-1]["success_text"], "")
        self.assertIsNotNone(worker_calls[-1]["after_success"])

        with patch.object(window.service, "get_link_migration_status", return_value=migrated), patch.object(
            window.service, "cancel_link_migration", return_value=LinkCancelResult(item.source, store_path, Path("D:/backup/cancel"))
        ) as cancel, patch.object(
            window, "_run_worker", side_effect=run_worker_without_dialog
        ), patch("app_fluent.QMessageBox.question") as question:
            window.link_cards[0].checkbox.setChecked(True)
            window.cancel_selected_link_migration()

        question.assert_not_called()
        cancel.assert_called_once_with(item)
        self.assertFalse(worker_calls[-1]["refresh"])
        self.assertEqual(worker_calls[-1]["success_text"], "")
        self.assertIsNotNone(worker_calls[-1]["after_success"])
        window.close()
        app.quit()

    def test_link_actions_show_busy_state_and_disable_controls_while_running(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp
        from backup_core import BackupItem, LinkMigrationStatus, ScannedItem

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()
        item = BackupItem(".codex", Path("C:/Users/example/.codex"))
        status = LinkMigrationStatus(
            state="normal",
            label="未迁移",
            detail="",
            link_path=item.source,
            store_path=Path("D:/store/.codex"),
            can_migrate=True,
            can_cancel=False,
        )

        worker_call = {}

        def hold_worker(job, refresh=True, success_text="", after_success=None, after_failed=None, on_failed=None):
            worker_call.update({"job": job, "refresh": refresh, "success_text": success_text, "after_success": after_success, "after_failed": after_failed})

        with patch.object(window.service, "get_link_migration_status", return_value=status), patch.object(
            window, "_run_worker", side_effect=hold_worker
        ):
            window.apply_scanned_items([ScannedItem(item, True, 100, datetime(2026, 5, 24, 1, 0))])
            window.link_cards[0].checkbox.setChecked(True)

            window.migrate_selected_link()

            self.assertTrue(window._link_action_busy)
            self.assertIn("正在迁移中", window.link_hint.text())
            self.assertFalse(window.migrate_button.isEnabled())
            self.assertFalse(window.cancel_migration_button.isEnabled())
            self.assertFalse(window.refresh_link_button.isEnabled())
            self.assertFalse(window.link_cards[0].checkbox.isEnabled())

            worker_call["after_success"]()

            self.assertFalse(window._link_action_busy)
            self.assertTrue(window.refresh_link_button.isEnabled())

        window.close()
        app.quit()

    def test_link_action_does_not_enter_busy_state_when_another_worker_is_running(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp
        from backup_core import BackupItem, LinkMigrationStatus, ScannedItem

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()
        item = BackupItem(".codex", Path("C:/Users/example/.codex"))
        status = LinkMigrationStatus(
            state="normal",
            label="未迁移",
            detail="",
            link_path=item.source,
            store_path=Path("D:/store/.codex"),
            can_migrate=True,
            can_cancel=False,
        )

        class RunningWorker:
            def isRunning(self):
                return True

            def wait(self):
                return True

        window.worker = RunningWorker()
        with patch.object(window.service, "get_link_migration_status", return_value=status), patch.object(window, "_info") as info:
            window.apply_scanned_items([ScannedItem(item, True, 100, datetime(2026, 5, 24, 1, 0))])
            window.link_cards[0].checkbox.setChecked(True)

            window.migrate_selected_link()

            self.assertFalse(window._link_action_busy)
            self.assertNotIn("正在迁移中", window.link_hint.text())
            self.assertTrue(window.migrate_button.isEnabled())
            info.assert_called_once_with("当前已有任务在运行。")

        window.close()
        app.quit()

    def test_link_action_busy_state_resets_when_worker_fails(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp
        from backup_core import BackupItem, LinkMigrationStatus, ScannedItem

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()
        item = BackupItem(".codex", Path("C:/Users/example/.codex"))
        status = LinkMigrationStatus(
            state="normal",
            label="未迁移",
            detail="",
            link_path=item.source,
            store_path=Path("D:/store/.codex"),
            can_migrate=True,
            can_cancel=False,
        )

        with patch.object(window.service, "get_link_migration_status", return_value=status), patch.object(
            window, "_run_worker", side_effect=lambda job, refresh=True, success_text="", after_success=None, after_failed=None, on_failed=None: None
        ):
            window.apply_scanned_items([ScannedItem(item, True, 100, datetime(2026, 5, 24, 1, 0))])
            window.link_cards[0].checkbox.setChecked(True)
            window.migrate_selected_link()
            self.assertTrue(window._link_action_busy)

            window._finish_failed_link_action_refresh()

            self.assertFalse(window._link_action_busy)
            self.assertTrue(window.refresh_link_button.isEnabled())

        window.close()
        app.quit()

    def test_run_worker_skips_success_info_bar_when_success_text_is_empty(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()

        with patch.object(window, "_success") as success:
            window._run_worker(lambda log: None, refresh=False, success_text="")
            QTimer.singleShot(0, app.quit)
            app.exec()

        success.assert_not_called()
        window.close()
        app.quit()

    def test_show_error_displays_user_friendly_migration_error(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()
        captured = {}

        def capture(_factory, title, content, duration):
            captured.update({"title": title, "content": content, "duration": duration})

        window._show_info_bar = capture
        window._show_error("PermissionError: [WinError 32] 另一个程序正在使用此文件。: 'C:\\Users\\me\\.codex\\logs.sqlite'\nTraceback...")

        self.assertEqual(captured["title"], "任务失败")
        self.assertIn("文件正在使用中", captured["content"])
        self.assertIn("logs.sqlite", captured["content"])

        window.close()
        app.quit()

    def test_link_action_failure_uses_modal_message_box_until_confirmed(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import APP_TITLE, FluentBackupApp

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()
        error_text = "PermissionError: [WinError 32] 另一个程序正在使用此文件。: 'C:\\Users\\me\\.codex\\logs.sqlite'\nTraceback..."

        with patch.object(window, "_show_info_bar") as info_bar, patch("app_fluent.QMessageBox.critical") as critical:
            window._show_link_action_error_dialog(error_text)

        info_bar.assert_not_called()
        critical.assert_called_once()
        args = critical.call_args.args
        self.assertIs(args[0], window)
        self.assertEqual(args[1], APP_TITLE)
        self.assertIn("文件正在使用中", args[2])
        self.assertIn("logs.sqlite", args[2])

        window.close()
        app.quit()

    def test_link_action_success_clears_selection_sorts_migrated_first_and_scrolls_top(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp
        from backup_core import BackupItem, LinkMigrationResult, LinkMigrationStatus, ScannedItem

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()
        migrated_item = BackupItem(".already", Path("C:/Users/example/.already"))
        target_item = BackupItem(".target", Path("C:/Users/example/.target"))
        normal_item = BackupItem(".normal", Path("C:/Users/example/.normal"))
        target_store = Path("D:/code/backup/迁移后的真实目录/.target")
        scanned = [
            ScannedItem(normal_item, True, 10, datetime(2026, 5, 20, 1, 0)),
            ScannedItem(target_item, True, 20, datetime(2026, 5, 22, 1, 0)),
            ScannedItem(migrated_item, True, 30, datetime(2026, 5, 21, 1, 0)),
        ]
        states = {".already": "migrated", ".target": "normal", ".normal": "normal"}

        def status_for_item(item):
            state = states[item.name]
            store = target_store if item.name == ".target" else Path(f"D:/code/backup/迁移后的真实目录/{item.name}")
            return LinkMigrationStatus(
                state=state,
                label="已迁移" if state == "migrated" else "未迁移",
                detail="",
                link_path=item.source,
                store_path=store,
                can_migrate=state == "normal",
                can_cancel=state == "migrated",
            )

        def prepare_item(item, _store_root):
            states[item.name] = "migrated"
            return LinkMigrationResult(item.source, target_store, Path("D:/backup/pre"))

        def run_worker_and_finish(job, refresh=True, success_text="", after_success=None, after_failed=None, on_failed=None):
            job(lambda message: None)
            if after_success is not None:
                after_success()
            elif refresh:
                window.refresh_link_items()

        with patch.object(window.service, "get_link_migration_status", side_effect=status_for_item), patch.object(
            window.service, "prepare_link_migration", side_effect=prepare_item
        ), patch.object(window.service, "create_junction"), patch.object(
            window, "_run_worker", side_effect=run_worker_and_finish
        ), patch.object(window, "_scroll_link_list_to_top") as scroll_top:
            window.apply_scanned_items(scanned)
            window.link_sort_combo.setCurrentText("从小到大")
            window.link_cards[1].checkbox.setChecked(True)
            self.assertEqual(window.link_selected_names, {".target"})

            window.migrate_selected_link()

            self.assertEqual(window.link_sort_combo.currentText(), "已经迁移")
            self.assertEqual(window.link_selected_names, set())
            self.assertEqual([card.item.name for card in window.link_cards[:2]], [".target", ".already"])
            self.assertTrue(all(not card.checkbox.isChecked() for card in window.link_cards))
            scroll_top.assert_called()

        window.close()
        app.quit()

    def test_cancel_link_action_success_clears_selection_and_scrolls_top(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp
        from backup_core import BackupItem, LinkCancelResult, LinkMigrationStatus, ScannedItem

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()
        target_item = BackupItem(".target", Path("C:/Users/example/.target"))
        other_item = BackupItem(".other", Path("C:/Users/example/.other"))
        target_store = Path("D:/code/backup/迁移后的真实目录/.target")
        scanned = [
            ScannedItem(target_item, True, 20, datetime(2026, 5, 22, 1, 0)),
            ScannedItem(other_item, True, 10, datetime(2026, 5, 21, 1, 0)),
        ]
        states = {".target": "migrated", ".other": "migrated"}

        def status_for_item(item):
            state = states[item.name]
            store = target_store if item.name == ".target" else Path(f"D:/code/backup/迁移后的真实目录/{item.name}")
            return LinkMigrationStatus(
                state=state,
                label="已迁移" if state == "migrated" else "未迁移",
                detail="",
                link_path=item.source,
                store_path=store,
                can_migrate=state == "normal",
                can_cancel=state == "migrated",
            )

        def cancel_item(item):
            states[item.name] = "normal"
            return LinkCancelResult(item.source, target_store, Path("D:/backup/cancel"))

        def run_worker_and_finish(job, refresh=True, success_text="", after_success=None, after_failed=None, on_failed=None):
            job(lambda message: None)
            if after_success is not None:
                after_success()
            elif refresh:
                window.refresh_link_items()

        with patch.object(window.service, "get_link_migration_status", side_effect=status_for_item), patch.object(
            window.service, "cancel_link_migration", side_effect=cancel_item
        ), patch.object(window, "_run_worker", side_effect=run_worker_and_finish), patch.object(
            window, "_scroll_link_list_to_top"
        ) as scroll_top:
            window.apply_scanned_items(scanned)
            window.link_sort_combo.setCurrentText("从大到小")
            window.link_cards[0].checkbox.setChecked(True)
            self.assertEqual(window.link_selected_names, {".target"})

            window.cancel_selected_link_migration()

            self.assertEqual(window.link_sort_combo.currentText(), "已经迁移")
            self.assertEqual(window.link_selected_names, set())
            self.assertTrue(all(not card.checkbox.isChecked() for card in window.link_cards))
            self.assertIn("未迁移", next(card.title_line.text() for card in window.link_cards if card.item.name == ".target"))
            scroll_top.assert_called()

        window.close()
        app.quit()

    def test_cancel_link_migration_refreshes_link_status_after_success(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp
        from backup_core import BackupItem, LinkCancelResult, LinkMigrationStatus, ScannedItem

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()
        item = BackupItem(".vscode", Path("C:/Users/example/.vscode"))
        store_path = Path("D:/code/backup/迁移后的真实目录/.vscode")
        state = {"value": "migrated"}

        def status_for_item(_item):
            if state["value"] == "migrated":
                return LinkMigrationStatus(
                    state="migrated",
                    label="已迁移",
                    detail=f"C 盘引用：{item.source}；D 盘真实目录：{store_path}",
                    link_path=item.source,
                    store_path=store_path,
                    can_migrate=False,
                    can_cancel=True,
                )
            return LinkMigrationStatus(
                state="normal",
                label="未迁移",
                detail=f"C 盘原目录：{item.source}；迁移后真实目录：{store_path}",
                link_path=item.source,
                store_path=store_path,
                can_migrate=True,
                can_cancel=False,
            )

        def cancel_item(_item):
            state["value"] = "normal"
            return LinkCancelResult(item.source, store_path, Path("D:/backup/cancel"))

        def run_worker_and_refresh(job, refresh=True, success_text="", after_success=None, after_failed=None, on_failed=None):
            job(lambda message: None)
            if after_success is not None:
                after_success()
            elif refresh:
                window.refresh_link_items()

        with patch.object(window.service, "get_link_migration_status", side_effect=status_for_item), patch.object(
            window.service, "cancel_link_migration", side_effect=cancel_item
        ), patch.object(window, "_run_worker", side_effect=run_worker_and_refresh):
            window.apply_scanned_items([ScannedItem(item, True, 100, datetime(2026, 5, 24, 1, 0))])
            self.assertIn("已迁移", window.link_cards[0].title_line.text())
            window.link_cards[0].checkbox.setChecked(True)

            window.cancel_selected_link_migration()

            self.assertIn("未迁移", window.link_cards[0].title_line.text())
            self.assertEqual(window.link_selected_names, set())
            self.assertFalse(window.cancel_migration_button.isEnabled())
            self.assertFalse(window.migrate_button.isEnabled())

        window.close()
        app.quit()

    def test_link_page_shows_broken_migration_status_without_enabling_actions(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp
        from backup_core import BackupItem, LinkMigrationStatus, ScannedItem

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()
        item = BackupItem(".codex", Path("C:/Users/example/.codex"))
        store_path = Path("D:/code/backup/迁移后的真实目录/.codex")
        broken = LinkMigrationStatus(
            state="broken",
            label="异常",
            detail=f"C 盘原目录：{item.source}；D 盘真实目录：{store_path}",
            link_path=item.source,
            store_path=store_path,
            can_migrate=False,
            can_cancel=False,
            problem="迁移后的真实目录已存在，但 C 盘原位置不是 Junction。",
        )

        with patch.object(window.service, "get_link_migration_status", return_value=broken):
            window.apply_scanned_items([ScannedItem(item, True, 100, datetime(2026, 5, 24, 1, 0))])
            window.link_cards[0].checkbox.setChecked(True)

        self.assertIn("异常", window.link_cards[0].title_line.text())
        self.assertIn("异常类型：D盘已有真实目录，C盘不是Junction", window.link_cards[0].title_line.toolTip())
        self.assertIn("处理建议：先确认 C 盘和 D 盘哪边数据完整，再手动整理。", window.link_cards[0].title_line.toolTip())
        self.assertIn("需要手动检查", window.link_hint.text())
        self.assertFalse(window.migrate_button.isEnabled())
        self.assertFalse(window.cancel_migration_button.isEnabled())
        window.close()
        app.quit()

    def test_link_broken_status_tooltip_summarizes_each_exception_type(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp
        from backup_core import BackupItem, LinkMigrationStatus

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()
        item = BackupItem(".codex", Path("C:/Users/example/.codex"))
        store_path = Path("D:/code/backup/迁移后的真实目录/.codex")

        cases = [
            ("C 盘原位置是 Junction，但真实目录不存在：D:/missing", "异常类型：C盘是Junction，但D盘真实目录不存在"),
            ("迁移后的真实目录已存在，但 C 盘原位置不是 Junction。", "异常类型：D盘已有真实目录，C盘不是Junction"),
            ("迁移后的真实目录已存在，但 C 盘原位置不存在。", "异常类型：D盘已有真实目录，C盘原位置不存在"),
            ("C 盘原目录不存在，无法迁移或取消迁移。", "异常类型：C盘原目录不存在，D盘也没有迁移目录"),
            ("其他未知问题", "异常类型：需要手动检查迁移状态"),
        ]

        for problem, expected in cases:
            status = LinkMigrationStatus(
                state="broken",
                label="异常",
                detail=f"C 盘原目录：{item.source}；D 盘真实目录：{store_path}",
                link_path=item.source,
                store_path=store_path,
                can_migrate=False,
                can_cancel=False,
                problem=problem,
            )
            self.assertIn(expected, window._link_status_tooltip(status))

        window.close()
        app.quit()

    def test_link_page_uses_compact_terms_bar_without_forcing_tall_window(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()
        window.resize(720, 540)
        window.show()
        window._set_current_page(window.link_page)
        app.processEvents()

        self.assertEqual(window.height(), 540)
        self.assertLessEqual(window.link_terms_card.sizeHint().height(), 58)
        self.assertEqual(window.link_scroll.minimumHeight(), 0)
        self.assertTrue(window.link_terms_text.wordWrap())
        window.close()
        app.quit()

    def test_checking_backup_item_preserves_scroll_position(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp
        from backup_core import BackupItem, ScannedItem

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()
        window._wait_for_thread(window.scan_worker)
        app.processEvents()
        window.scan_worker = None
        window.persist_selected_items = lambda: None
        window.items = [
            BackupItem(f".item{i:02d}", Path(f"C:/Users/example/.item{i:02d}"))
            for i in range(40)
        ]
        window.selected_names = {item.name for item in window.items}
        scanned = [
            ScannedItem(item, True, index + 1, None)
            for index, item in enumerate(window.items)
        ]
        window.apply_scanned_items(scanned)
        window._set_current_page(window.items_page)
        window.resize(720, 540)
        window.show()
        app.processEvents()

        scrollbar = window.item_scroll.verticalScrollBar()
        scrollbar.setValue(max(0, scrollbar.maximum() // 2))
        before = scrollbar.value()
        window.item_cards[25].checkbox.setChecked(not window.item_cards[25].checkbox.isChecked())
        app.processEvents()

        self.assertEqual(scrollbar.value(), before)
        window.close()
        app.quit()

    def test_fluent_restore_snapshot_list_does_not_show_horizontal_scrollbar(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp

        app = QApplication.instance() or QApplication([])
        window = FluentBackupApp()
        window.show()
        window.resize(720, 540)
        long_name = "2026-05-20_10-20-18-" + ("很长的快照名称" * 12)
        window.restore_snapshot_list.addItem(long_name)
        app.processEvents()

        self.assertFalse(window.restore_snapshot_list.horizontalScrollBar().isVisible())

        window.close()
        app.quit()

    def test_fluent_save_config_persists_backup_root_and_schedule_time(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp
        from backup_core import load_user_settings

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            backup_root = root / "saved-backups"
            home.mkdir()
            original_with_name = Path.with_name

            def fake_with_name(path: Path, name: str) -> Path:
                if str(path).endswith("app_fluent.py") and name == "data":
                    return root / "data"
                return original_with_name(path, name)

            app = QApplication.instance() or QApplication([])
            with patch("app_fluent.Path.home", return_value=home), patch("app_fluent.Path.with_name", fake_with_name):
                window = FluentBackupApp()

            window.backup_root_edit.setText(str(backup_root))
            window.schedule_time.setText("07:15")
            window.save_backup_root_from_input()

            settings = load_user_settings(root / "data" / "user-settings.json")
            self.assertEqual(Path(settings["backup_root"]), backup_root)
            self.assertEqual(settings["schedule_time"], "07:15")
            window.close()
            app.quit()

    def test_fluent_save_config_persists_schedule_time_without_changing_backup_root(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp
        from backup_core import load_user_settings, write_user_settings

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            backup_root = root / "saved-backups"
            home.mkdir()
            settings_path = root / "data" / "user-settings.json"
            write_user_settings(settings_path, [], backup_root=backup_root, schedule_time="06:30")
            original_with_name = Path.with_name

            def fake_with_name(path: Path, name: str) -> Path:
                if str(path).endswith("app_fluent.py") and name == "data":
                    return root / "data"
                return original_with_name(path, name)

            app = QApplication.instance() or QApplication([])
            with patch("app_fluent.Path.home", return_value=home), patch("app_fluent.Path.with_name", fake_with_name):
                window = FluentBackupApp()

            window.schedule_time.setText("08:45")
            window.save_backup_root_from_input()

            settings = load_user_settings(settings_path)
            self.assertEqual(Path(settings["backup_root"]), backup_root)
            self.assertEqual(settings["schedule_time"], "08:45")
            self.assertEqual(window.schedule_time_value, "08:45")
            self.assertEqual(window.schedule_metric.subtitle_label.text(), "每天 08:45")
            window.close()
            app.quit()

    def test_fluent_schedule_time_editing_finished_persists_settings(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp
        from backup_core import load_user_settings, write_user_settings

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            backup_root = root / "saved-backups"
            home.mkdir()
            settings_path = root / "data" / "user-settings.json"
            write_user_settings(settings_path, [], backup_root=backup_root, schedule_time="06:30")
            original_with_name = Path.with_name

            def fake_with_name(path: Path, name: str) -> Path:
                if str(path).endswith("app_fluent.py") and name == "data":
                    return root / "data"
                return original_with_name(path, name)

            app = QApplication.instance() or QApplication([])
            with patch("app_fluent.Path.home", return_value=home), patch("app_fluent.Path.with_name", fake_with_name):
                window = FluentBackupApp()

            window.schedule_time.setText("09:20")
            window.schedule_time.editingFinished.emit()

            settings = load_user_settings(settings_path)
            self.assertEqual(settings["schedule_time"], "09:20")
            self.assertEqual(window.schedule_time_value, "09:20")
            window.close()
            app.quit()

    def test_fluent_custom_item_change_updates_schedule_config(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            custom = root / "资料"
            home.mkdir()
            custom.mkdir()
            (custom / "note.txt").write_text("data", encoding="utf-8")
            original_with_name = Path.with_name

            def fake_with_name(path: Path, name: str) -> Path:
                if str(path).endswith("app_fluent.py") and name == "data":
                    return root / "data"
                return original_with_name(path, name)

            app = QApplication.instance() or QApplication([])
            with patch("app_fluent.Path.home", return_value=home), patch("app_fluent.Path.with_name", fake_with_name):
                window = FluentBackupApp()

            window.add_custom_path(custom, sensitive=False)

            schedule = json.loads((root / "data" / "schedule.json").read_text(encoding="utf-8"))
            self.assertIn("自定义/资料", schedule["items"])
            self.assertEqual(schedule["custom_items"], [{"name": "资料", "path": str(custom), "sensitive": False}])
            window.close()
            app.quit()

    def test_fluent_remove_custom_item_updates_saved_settings_and_schedule_config(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp
        from backup_core import load_user_settings, write_user_settings

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            custom = root / "资料"
            home.mkdir()
            custom.mkdir()
            settings_path = root / "data" / "user-settings.json"
            backup_root = root / "saved-backups"
            write_user_settings(
                settings_path,
                ["自定义/资料"],
                [{"name": "资料", "path": str(custom), "sensitive": False}],
                backup_root=backup_root,
                schedule_time="06:30",
            )
            original_with_name = Path.with_name

            def fake_with_name(path: Path, name: str) -> Path:
                if str(path).endswith("app_fluent.py") and name == "data":
                    return root / "data"
                return original_with_name(path, name)

            app = QApplication.instance() or QApplication([])
            with patch("app_fluent.Path.home", return_value=home), patch("app_fluent.Path.with_name", fake_with_name):
                window = FluentBackupApp()

            window.remove_selected_custom_items()

            settings = load_user_settings(settings_path)
            schedule = json.loads((root / "data" / "schedule.json").read_text(encoding="utf-8"))
            self.assertEqual(settings["custom_items"], [])
            self.assertNotIn("自定义/资料", settings["selected_items"])
            self.assertEqual(Path(settings["backup_root"]), backup_root)
            self.assertEqual(settings["schedule_time"], "06:30")
            self.assertEqual(schedule["custom_items"], [])
            self.assertNotIn("自定义/资料", schedule["items"])
            self.assertEqual(schedule["backup_root"], str(backup_root))
            window.close()
            app.quit()

    def test_fluent_delete_checked_custom_items_after_select_all_keeps_default_dot_items(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp
        from backup_core import load_user_settings, write_user_settings

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            custom = root / "资料"
            (home / ".codex").mkdir(parents=True)
            custom.mkdir()
            settings_path = root / "data" / "user-settings.json"
            backup_root = root / "saved-backups"
            write_user_settings(
                settings_path,
                [".codex", "自定义/资料"],
                [{"name": "资料", "path": str(custom), "sensitive": False}],
                backup_root=backup_root,
                schedule_time="06:30",
            )
            original_with_name = Path.with_name

            def fake_with_name(path: Path, name: str) -> Path:
                if str(path).endswith("app_fluent.py") and name == "data":
                    return root / "data"
                return original_with_name(path, name)

            app = QApplication.instance() or QApplication([])
            with patch("app_fluent.Path.home", return_value=home), patch("app_fluent.Path.with_name", fake_with_name):
                window = FluentBackupApp()

            window.set_all_items(True)
            window.remove_selected_custom_items()

            settings = load_user_settings(settings_path)
            self.assertIn(".codex", settings["selected_items"])
            self.assertNotIn("自定义/资料", settings["selected_items"])
            self.assertEqual(settings["custom_items"], [])
            window.close()
            app.quit()

    def test_fluent_select_all_can_remove_missing_custom_items(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp
        from backup_core import load_user_settings, write_user_settings

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            missing_custom = root / "missing-custom"
            (home / ".codex").mkdir(parents=True)
            settings_path = root / "data" / "user-settings.json"
            write_user_settings(
                settings_path,
                [".codex"],
                [{"name": "missing-custom", "path": str(missing_custom), "sensitive": False}],
            )
            original_with_name = Path.with_name

            def fake_with_name(path: Path, name: str) -> Path:
                if str(path).endswith("app_fluent.py") and name == "data":
                    return root / "data"
                return original_with_name(path, name)

            app = QApplication.instance() or QApplication([])
            with patch("app_fluent.Path.home", return_value=home), patch("app_fluent.Path.with_name", fake_with_name):
                window = FluentBackupApp()

            window.set_all_items(True)
            self.assertIn("自定义/missing-custom", window.selected_names)

            window.remove_selected_custom_items()

            settings = load_user_settings(settings_path)
            self.assertEqual(settings["custom_items"], [])
            self.assertNotIn("自定义/missing-custom", settings["selected_items"])
            self.assertIn(".codex", settings["selected_items"])
            window.close()
            app.quit()

    def test_fluent_save_config_rejects_invalid_schedule_time_without_overwriting_previous_value(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp
        from backup_core import load_user_settings, write_user_settings

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            backup_root = root / "saved-backups"
            home.mkdir()
            settings_path = root / "data" / "user-settings.json"
            write_user_settings(settings_path, [], backup_root=backup_root, schedule_time="06:30")
            original_with_name = Path.with_name

            def fake_with_name(path: Path, name: str) -> Path:
                if str(path).endswith("app_fluent.py") and name == "data":
                    return root / "data"
                return original_with_name(path, name)

            app = QApplication.instance() or QApplication([])
            with patch("app_fluent.Path.home", return_value=home), patch("app_fluent.Path.with_name", fake_with_name):
                window = FluentBackupApp()

            window.schedule_time.setText("99:99")
            window.save_backup_root_from_input()

            settings = load_user_settings(settings_path)
            self.assertEqual(settings["schedule_time"], "06:30")
            self.assertEqual(window.schedule_time_value, "06:30")
            window.close()
            app.quit()

    def test_restore_page_shows_snapshot_manifest_detail_and_missing_selected_items(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app_fluent import FluentBackupApp

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            (home / ".happy").mkdir(parents=True)
            (home / ".ssh").mkdir()
            backup_root = root / "backups"
            snapshot = backup_root / "2026-05-19_20-00-00"
            snapshot.mkdir(parents=True)
            manifest = {
                "created_at": "2026-05-19T20:00:00",
                "items": [
                    {"name": ".happy", "source": str(home / ".happy"), "sensitive": True},
                    {"name": ".codex", "source": str(home / ".codex"), "sensitive": True},
                ],
            }
            (snapshot / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            original_with_name = Path.with_name

            def fake_with_name(path: Path, name: str) -> Path:
                if str(path).endswith("app_fluent.py") and name == "data":
                    return root / "data"
                return original_with_name(path, name)

            app = QApplication.instance() or QApplication([])
            with (
                patch("app_fluent.Path.home", return_value=home),
                patch("app_fluent.Path.with_name", fake_with_name),
                patch("app_fluent.load_config", return_value={"backup_root": str(backup_root)}),
            ):
                window = FluentBackupApp()

            window.restore_snapshot_list.setCurrentRow(0)
            detail = window.restore_snapshot_detail.toPlainText()

            self.assertIn("2026-05-19T20:00:00", detail)
            self.assertIn(".happy", detail)
            self.assertIn(".codex", detail)
            self.assertIn("可恢复：.happy", detail)
            self.assertIn("快照缺少：.ssh", detail)
            window.close()
            app.quit()

    def test_fluent_refresh_uses_background_scan_worker(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        import app_fluent
        from app_fluent import FluentBackupApp
        from backup_core import ScannedItem

        class SignalProxy:
            def __init__(self):
                self.callbacks = []

            def connect(self, callback):
                self.callbacks.append(callback)

            def emit(self, *args):
                for callback in self.callbacks:
                    callback(*args)

        class RecordingScanWorker:
            started = False

            def __init__(self, service, items):
                self.service = service
                self.items = list(items)
                self.finished_scan = SignalProxy()
                self.failed = SignalProxy()

            def isRunning(self):
                return False

            def start(self):
                type(self).started = True
                scanned = [
                    ScannedItem(item, False, 0, None)
                    for item in self.items
                ]
                self.finished_scan.emit(scanned)

        app = QApplication.instance() or QApplication([])
        with patch("app_fluent.ScanWorker", RecordingScanWorker):
            window = FluentBackupApp()

        self.assertTrue(RecordingScanWorker.started)
        window.close()
        app.quit()

    def test_capture_ui_snapshots_writes_non_empty_png_files(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        import scripts.capture_ui_snapshots as capture_script
        from app_fluent import FluentBackupApp

        with tempfile.TemporaryDirectory() as tmp:
            original_wait = FluentBackupApp._wait_for_thread
            original_grab = FluentBackupApp.grab
            events = []

            def recording_wait(self, thread):
                events.append("wait")
                original_wait(self, thread)

            def recording_grab(self, *args, **kwargs):
                events.append("grab")
                return original_grab(self, *args, **kwargs)

            with (
                patch.object(FluentBackupApp, "_wait_for_thread", recording_wait),
                patch.object(FluentBackupApp, "grab", recording_grab),
            ):
                files = capture_script.capture_ui_snapshots(Path(tmp))

            self.assertGreaterEqual(len(files), 5)
            for file_path in files:
                self.assertTrue(file_path.exists(), file_path)
                self.assertEqual(file_path.suffix, ".png")
                self.assertGreater(file_path.stat().st_size, 1024, file_path)
            self.assertIn("wait", events)
            self.assertIn("grab", events)
            self.assertLess(events.index("wait"), events.index("grab"))

    def test_capture_ui_snapshots_script_can_run_from_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env.setdefault("QT_QPA_PLATFORM", "offscreen")
            result = subprocess.run(
                [sys.executable, "scripts/capture_ui_snapshots.py", tmp],
                capture_output=True,
                text=True,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            files = sorted(Path(tmp).glob("*.png"))
            self.assertGreaterEqual(len(files), 5)

    def test_gui_launcher_bat_detaches_pythonw_and_exits_cmd_prompt(self):
        launcher = Path("启动Ai会话备份.bat")
        text = launcher.read_text(encoding="utf-8")

        self.assertIn("start", text.lower())
        self.assertIn("pythonw.exe", text)
        self.assertIn("app_fluent.py", text)
        self.assertIn("exit /b 0", text.lower())
        self.assertNotIn("python.exe\" app_fluent.py", text.lower())


if __name__ == "__main__":
    unittest.main()

