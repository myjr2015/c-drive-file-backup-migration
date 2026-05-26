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

    def test_cross_platform_style_lab_exposes_requested_style_families(self):
        from style_lab import STYLE_FAMILIES, StyleFamily

        self.assertGreaterEqual(len(STYLE_FAMILIES), 5)
        self.assertEqual(
            [family.key for family in STYLE_FAMILIES],
            ["fluent", "shadcn_tauri", "flet_flutter", "avalonia_material", "customtkinter"],
        )
        for family in STYLE_FAMILIES:
            self.assertIsInstance(family, StyleFamily)
            self.assertTrue(family.label)
            self.assertTrue(family.stack)
            self.assertTrue(family.positioning)
            self.assertTrue(family.best_for)
            self.assertTrue(family.caution)
            self.assertTrue(family.tokens.primary)
            self.assertGreaterEqual(family.tokens.button_height, 28)

    def test_cross_platform_style_lab_window_builds_offscreen_and_switches_styles(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from style_lab import STYLE_FAMILIES, CrossPlatformStyleLabWindow

        app = QApplication.instance() or QApplication([])
        window = CrossPlatformStyleLabWindow()

        self.assertEqual(window.windowTitle(), "跨平台 UI 风格实验室")
        self.assertEqual(window.family_combo.count(), len(STYLE_FAMILIES))
        self.assertEqual(window.family_combo.currentText(), STYLE_FAMILIES[0].label)
        self.assertIn("Ai会话备份", window.preview_title.text())
        self.assertGreaterEqual(len(window.sample_buttons), 4)
        self.assertGreaterEqual(len(window.sample_cards), 3)

        window.family_combo.setCurrentText("Web / shadcn + Tauri")
        self.assertIn("shadcn", window.stack_label.text())
        self.assertIn("代码所有权", window.notes_label.text())

        window.family_combo.setCurrentText("Python / Flet + Flutter")
        self.assertIn("Flutter", window.stack_label.text())

        window.close()
        app.quit()

    def test_cross_platform_style_lab_launcher_detaches_pythonw(self):
        from pathlib import Path

        launcher = Path("ui方案") / "启动跨平台UI风格实验室.bat"
        text = launcher.read_text(encoding="utf-8")

        self.assertIn('set "ROOT=%~dp0.."', text)
        self.assertIn('start "" /D "%ROOT%" pythonw.exe style_lab.py', text)
        self.assertIn("exit /b 0", text)

    def test_github_style_gallery_contains_full_project_demos(self):
        from pathlib import Path

        gallery = Path("docs/github_style_gallery.html")
        html = gallery.read_text(encoding="utf-8")

        for project in [
            "shadcn/ui",
            "Tauri",
            "Avalonia UI",
            "Material Design In XAML",
            "Flet",
            "CustomTkinter",
            "Uno Platform",
            "PyQt-Fluent-Widgets",
        ]:
            self.assertIn(project, html)

        for marker in [
            'data-project="shadcn"',
            'data-project="tauri"',
            'data-project="avalonia"',
            'data-project="material-xaml"',
            'data-project="flet"',
            'data-project="customtkinter"',
            'data-project="uno"',
            'data-project="pyqt-fluent"',
        ]:
            self.assertIn(marker, html)

        self.assertGreaterEqual(html.count("demo-page"), 8)
        self.assertIn("Ai会话备份", html)
        launcher = (Path("ui方案") / "启动GitHub风格全景演示.bat").read_text(encoding="utf-8")
        self.assertIn('start "" "%ROOT%\\docs\\github_style_gallery.html"', launcher)
        self.assertIn("exit /b 0", launcher)

    def test_github_style_gallery_has_per_project_adjustable_controls(self):
        from pathlib import Path

        html = Path("docs/github_style_gallery.html").read_text(encoding="utf-8")

        for control_id in [
            'id="themeSelect"',
            'id="fontSelect"',
            'id="buttonSelect"',
            'id="navSelect"',
            'id="layoutSelect"',
        ]:
            self.assertIn(control_id, html)

        self.assertIn("const projectOptions", html)
        for project_key in [
            "shadcn",
            "tauri",
            "avalonia",
            "material-xaml",
            "flet",
            "customtkinter",
            "uno",
            "pyqt-fluent",
        ]:
            self.assertIn(f'"{project_key}":', html)

        for option_key in ["themes", "fonts", "buttons", "navs", "layouts"]:
            self.assertGreaterEqual(html.count(option_key), 8)

        for function_name in ["renderControls", "applyOptions", "setProject"]:
            self.assertIn(f"function {function_name}", html)

        for class_name in ["font-segoe", "font-inter", "buttons-pill", "nav-top", "layout-dense"]:
            self.assertIn(class_name, html)

    def test_ui_component_gallery_has_one_page_per_framework(self):
        from pathlib import Path

        gallery_dir = Path("docs/ui_components")
        expected_pages = {
            "index.html": "UI 组件图库",
            "shadcn-ui.html": "shadcn/ui",
            "tauri.html": "Tauri",
            "avalonia-ui.html": "Avalonia UI",
            "material-design-xaml.html": "Material Design In XAML",
            "flet.html": "Flet",
            "customtkinter.html": "CustomTkinter",
            "uno-platform.html": "Uno Platform",
            "pyqt-fluent-widgets.html": "PyQt-Fluent-Widgets",
        }

        for filename, title in expected_pages.items():
            page = gallery_dir / filename
            self.assertTrue(page.exists(), f"missing {filename}")
            html = page.read_text(encoding="utf-8")
            self.assertIn(title, html)

        shared_css = gallery_dir / "component_gallery.css"
        self.assertTrue(shared_css.exists())

    def test_each_ui_component_page_shows_component_categories_and_official_source(self):
        from pathlib import Path

        gallery_dir = Path("docs/ui_components")
        pages = [
            "shadcn-ui.html",
            "tauri.html",
            "avalonia-ui.html",
            "material-design-xaml.html",
            "flet.html",
            "customtkinter.html",
            "uno-platform.html",
            "pyqt-fluent-widgets.html",
        ]
        required_sections = ["官方定位", "主题和字体", "按钮", "输入和选择", "导航", "数据展示", "弹窗和反馈", "布局容器"]

        for filename in pages:
            html = (gallery_dir / filename).read_text(encoding="utf-8")
            for section in required_sections:
                self.assertIn(section, html, f"{filename} missing {section}")
            self.assertIn("官方链接", html)
            self.assertGreaterEqual(html.count("component-sample"), 12, f"{filename} has too few samples")
            self.assertIn("theme-switcher", html)


if __name__ == "__main__":
    unittest.main()
