import os
import unittest


class FluentStyleDemoTests(unittest.TestCase):
    def test_style_demo_exposes_comparable_options(self):
        from style_demo_fluent import (
            COMPONENT_DENSITY_OPTIONS,
            DEFAULT_COMPONENT_DENSITY_KEY,
            DEFAULT_NAVIGATION_STYLE_KEY,
            DEFAULT_THEME_COLOR_KEY,
            DEFAULT_THEME_KEY,
            DEFAULT_WINDOW_STYLE_KEY,
            NAVIGATION_STYLE_OPTIONS,
            THEME_COLOR_OPTIONS,
            THEME_OPTIONS,
            WINDOW_STYLE_OPTIONS,
        )

        self.assertEqual([option.label for option in THEME_OPTIONS], ["浅色", "深色", "跟随系统"])
        self.assertGreaterEqual(len(THEME_COLOR_OPTIONS), 6)
        self.assertEqual([option.label for option in NAVIGATION_STYLE_OPTIONS], ["侧边导航", "顶部标签", "无导航"])
        self.assertEqual([option.label for option in WINDOW_STYLE_OPTIONS], ["标准 Fluent", "微软商店风格", "分栏 Fluent"])
        self.assertEqual([option.label for option in COMPONENT_DENSITY_OPTIONS], ["紧凑", "标准", "宽松"])
        self.assertEqual(DEFAULT_THEME_KEY, "auto")
        self.assertEqual(DEFAULT_THEME_COLOR_KEY, "blue")
        self.assertEqual(DEFAULT_NAVIGATION_STYLE_KEY, "side")
        self.assertEqual(DEFAULT_WINDOW_STYLE_KEY, "store")
        self.assertEqual(DEFAULT_COMPONENT_DENSITY_KEY, "compact")

    def test_style_demo_window_builds_offscreen(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from style_demo_fluent import FluentStyleDemoWindow

        app = QApplication.instance() or QApplication([])
        window = FluentStyleDemoWindow()

        self.assertEqual(window.windowTitle(), "Fluent 风格演示器")
        self.assertGreaterEqual(window.width(), 900)
        self.assertIn("主题", window.control_title.text())
        self.assertEqual(window.theme_combo.currentText(), "跟随系统")
        self.assertEqual(window.color_combo.currentText(), "蓝色")
        self.assertEqual(window.navigation_combo.currentText(), "侧边导航")
        self.assertEqual(window.window_combo.currentText(), "微软商店风格")
        self.assertEqual(window.density_combo.currentText(), "紧凑")
        self.assertIn("总览", window.preview_nav_labels())
        self.assertGreaterEqual(len(window.preview_buttons), 3)
        self.assertGreaterEqual(len(window.preview_cards), 3)

        window.close()
        app.quit()


if __name__ == "__main__":
    unittest.main()
