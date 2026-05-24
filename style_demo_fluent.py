from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    CheckBox,
    ComboBox,
    FluentIcon,
    FluentWindow,
    LineEdit,
    ListWidget,
    MSFluentWindow,
    NavigationInterface,
    NavigationItemPosition,
    Pivot,
    PrimaryPushButton,
    PrimaryToolButton,
    ProgressBar,
    PushButton,
    ScrollArea,
    SegmentedWidget,
    Slider,
    SplitFluentWindow,
    StrongBodyLabel,
    SwitchButton,
    TextEdit,
    Theme,
    ToolButton,
    TransparentToolButton,
    setTheme,
    setThemeColor,
)


@dataclass(frozen=True)
class DemoOption:
    key: str
    label: str
    value: object


THEME_OPTIONS = [
    DemoOption("light", "浅色", Theme.LIGHT),
    DemoOption("dark", "深色", Theme.DARK),
    DemoOption("auto", "跟随系统", Theme.AUTO),
]

THEME_COLOR_OPTIONS = [
    DemoOption("blue", "蓝色", "#0078D4"),
    DemoOption("cyan", "青色", "#0099BC"),
    DemoOption("green", "绿色", "#107C10"),
    DemoOption("purple", "紫色", "#5C2D91"),
    DemoOption("orange", "橙色", "#D83B01"),
    DemoOption("neutral", "灰色", "#5E5E5E"),
]

NAVIGATION_STYLE_OPTIONS = [
    DemoOption("side", "侧边导航", "side"),
    DemoOption("top", "顶部标签", "top"),
    DemoOption("none", "无导航", "none"),
]

WINDOW_STYLE_OPTIONS = [
    DemoOption("fluent", "标准 Fluent", FluentWindow),
    DemoOption("store", "微软商店风格", MSFluentWindow),
    DemoOption("split", "分栏 Fluent", SplitFluentWindow),
]

COMPONENT_DENSITY_OPTIONS = [
    DemoOption("compact", "紧凑", {"button": 28, "margin": 6, "spacing": 4}),
    DemoOption("standard", "标准", {"button": 32, "margin": 10, "spacing": 8}),
    DemoOption("relaxed", "宽松", {"button": 36, "margin": 14, "spacing": 12}),
]

DEFAULT_THEME_KEY = "auto"
DEFAULT_THEME_COLOR_KEY = "blue"
DEFAULT_NAVIGATION_STYLE_KEY = "side"
DEFAULT_WINDOW_STYLE_KEY = "store"
DEFAULT_COMPONENT_DENSITY_KEY = "compact"


STYLE = """
QWidget {
    font-family: "Microsoft YaHei UI", "Segoe UI";
    font-size: 12px;
}
QLabel#DemoTitle {
    font-size: 18px;
    font-weight: 700;
}
QLabel#SectionTitle {
    font-size: 14px;
    font-weight: 700;
}
QFrame#PreviewShell,
QFrame#PreviewContent,
QFrame#ControlPanel {
    background: transparent;
}
TextEdit {
    font-family: "Cascadia Mono", Consolas, "Microsoft YaHei UI";
    font-size: 11px;
}
"""


def _option_by_label(options: list[DemoOption], label: str) -> DemoOption:
    for option in options:
        if option.label == label:
            return option
    return options[0]


def _option_by_key(options: list[DemoOption], key: str) -> DemoOption:
    for option in options:
        if option.key == key:
            return option
    return options[0]


def _set_button_height(widget: QWidget, height: int) -> None:
    widget.setMinimumWidth(0)
    widget.setMaximumWidth(16777215)
    widget.setFixedHeight(height)


class DemoCard(CardWidget):
    def __init__(self, title: str, body: str, footer: str = "") -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        title_label = StrongBodyLabel(title)
        body_label = BodyLabel(body)
        body_label.setWordWrap(True)
        footer_label = CaptionLabel(footer)

        layout.addWidget(title_label)
        layout.addWidget(body_label)
        if footer:
            layout.addWidget(footer_label)


class ComponentPreview(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.preview_buttons: list[QWidget] = []
        self.preview_cards: list[CardWidget] = []
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel("备份助手界面预览")
        title.setObjectName("DemoTitle")
        status = CaptionLabel("真实 qfluentwidgets 控件组合")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(status)
        layout.addLayout(header)

        controls = CardWidget()
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(10, 8, 10, 8)
        controls_layout.setSpacing(8)

        controls_title = QLabel("常用操作")
        controls_title.setObjectName("SectionTitle")
        controls_layout.addWidget(controls_title)

        button_row = QHBoxLayout()
        button_row.setSpacing(6)
        primary = PrimaryPushButton("立即备份")
        secondary = PushButton("选择目录")
        danger = PushButton("删除自定义")
        icon_save = ToolButton(FluentIcon.SAVE)
        icon_folder = PrimaryToolButton(FluentIcon.FOLDER)
        icon_more = TransparentToolButton(FluentIcon.MORE)
        for button in [primary, secondary, danger, icon_save, icon_folder, icon_more]:
            self.preview_buttons.append(button)
            button_row.addWidget(button)
        button_row.addStretch(1)
        controls_layout.addLayout(button_row)

        form_row = QHBoxLayout()
        form_row.setSpacing(6)
        path_edit = LineEdit()
        path_edit.setText("D:\\code\\backup")
        path_edit.setClearButtonEnabled(True)
        sort_combo = ComboBox()
        sort_combo.addItems(["从大到小", "从小到大", "最近更新"])
        sort_combo.setCurrentText("最近更新")
        form_row.addWidget(path_edit, 1)
        form_row.addWidget(sort_combo)
        controls_layout.addLayout(form_row)

        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(12)
        auto_switch = SwitchButton()
        auto_switch.setChecked(True)
        check = CheckBox("包含自定义目录")
        check.setChecked(True)
        slider = Slider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(68)
        progress = ProgressBar()
        progress.setValue(68)
        toggle_row.addWidget(CaptionLabel("自动保存配置"))
        toggle_row.addWidget(auto_switch)
        toggle_row.addWidget(check)
        toggle_row.addWidget(slider, 1)
        toggle_row.addWidget(progress, 1)
        controls_layout.addLayout(toggle_row)

        layout.addWidget(controls)

        card_grid = QGridLayout()
        card_grid.setContentsMargins(0, 0, 0, 0)
        card_grid.setSpacing(8)
        card_data = [
            ("总览", "当前保护 5 个配置目录，定时备份 22:30。", "适合放状态摘要"),
            ("备份", ".codex · D:\\Users\\me\\.codex · 2.4 GB · 今天 10:30", "单行列表密度"),
            ("迁移", ".ssh · 128 KB · 昨天 21:12，可迁移到 link-store", "同备份页样式"),
        ]
        for index, (title, body, footer) in enumerate(card_data):
            card = DemoCard(title, body, footer)
            self.preview_cards.append(card)
            card_grid.addWidget(card, 0, index)
        layout.addLayout(card_grid)

        lower = QHBoxLayout()
        lower.setSpacing(8)
        list_widget = ListWidget()
        list_widget.addItems(["2026-05-23_22-30-00", "2026-05-22_22-30-00", "environment-path"])
        detail = TextEdit()
        detail.setPlainText("manifest.json\n- .codex\n- .ssh\n- 自定义/脚本目录\n\n用于观察列表、文本框和详情区的字体密度。")
        lower.addWidget(list_widget, 1)
        lower.addWidget(detail, 2)
        layout.addLayout(lower, 1)

    def apply_density(self, density: dict[str, int]) -> None:
        margin = int(density["margin"])
        spacing = int(density["spacing"])
        button_height = int(density["button"])

        def walk(widget: QWidget) -> None:
            if isinstance(widget.layout(), (QVBoxLayout, QHBoxLayout, QGridLayout)):
                widget.layout().setContentsMargins(margin, margin, margin, margin)
                widget.layout().setSpacing(spacing)
            for child in widget.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly):
                walk(child)

        walk(self)
        for button in self.preview_buttons:
            _set_button_height(button, button_height)


class FluentStyleDemoWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Fluent 风格演示器")
        self.resize(960, 640)
        self.setMinimumSize(860, 560)

        self.preview_buttons: list[QWidget] = []
        self.preview_cards: list[CardWidget] = []
        self._window_previews: list[QWidget] = []
        self.current_theme = _option_by_key(THEME_OPTIONS, DEFAULT_THEME_KEY)
        self.current_color = _option_by_key(THEME_COLOR_OPTIONS, DEFAULT_THEME_COLOR_KEY)
        self.current_navigation = _option_by_key(NAVIGATION_STYLE_OPTIONS, DEFAULT_NAVIGATION_STYLE_KEY)
        self.current_window = _option_by_key(WINDOW_STYLE_OPTIONS, DEFAULT_WINDOW_STYLE_KEY)
        self.current_density = _option_by_key(COMPONENT_DENSITY_OPTIONS, DEFAULT_COMPONENT_DENSITY_KEY)

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        self.control_panel = QFrame()
        self.control_panel.setObjectName("ControlPanel")
        self.control_panel.setFixedWidth(250)
        root.addWidget(self.control_panel)

        control_layout = QVBoxLayout(self.control_panel)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(10)

        self.control_title = QLabel("主题和布局选择")
        self.control_title.setObjectName("DemoTitle")
        control_layout.addWidget(self.control_title)

        self.theme_combo = self._add_combo(control_layout, "主题", THEME_OPTIONS, self.current_theme, self._apply_theme)
        self.color_combo = self._add_combo(control_layout, "主题色", THEME_COLOR_OPTIONS, self.current_color, self._apply_theme_color)
        self.navigation_combo = self._add_combo(
            control_layout,
            "导航栏风格",
            NAVIGATION_STYLE_OPTIONS,
            self.current_navigation,
            self._apply_navigation_style,
        )
        self.window_combo = self._add_combo(
            control_layout,
            "窗口风格",
            WINDOW_STYLE_OPTIONS,
            self.current_window,
            self._remember_window_style,
        )
        self.density_combo = self._add_combo(
            control_layout,
            "组件密度",
            COMPONENT_DENSITY_OPTIONS,
            self.current_density,
            self._apply_density,
        )

        open_window = PrimaryPushButton("打开窗口风格预览")
        open_window.clicked.connect(self.open_selected_window_preview)
        _set_button_height(open_window, 30)
        control_layout.addWidget(open_window)

        note = CaptionLabel("窗口风格会打开独立窗口；主题、主题色、导航和组件密度在右侧实时变化。")
        note.setWordWrap(True)
        control_layout.addWidget(note)
        control_layout.addStretch(1)

        self.preview_stack = QStackedWidget()
        root.addWidget(self.preview_stack, 1)

        self.side_preview = self._build_side_navigation_preview()
        self.top_preview = self._build_top_navigation_preview()
        self.plain_preview = self._build_plain_preview()
        self.preview_stack.addWidget(self.side_preview)
        self.preview_stack.addWidget(self.top_preview)
        self.preview_stack.addWidget(self.plain_preview)

        self.preview_buttons = self.side_component.preview_buttons
        self.preview_cards = self.side_component.preview_cards
        self._apply_theme(self.current_theme.label)
        self._apply_theme_color(self.current_color.label)
        self._apply_navigation_style(self.current_navigation.label)
        self._apply_density(self.current_density.label)

    def _add_combo(
        self,
        parent_layout: QVBoxLayout,
        title: str,
        options: list[DemoOption],
        default_option: DemoOption,
        callback: Callable[[str], None],
    ) -> ComboBox:
        label = StrongBodyLabel(title)
        combo = ComboBox()
        combo.addItems([option.label for option in options])
        combo.setCurrentText(default_option.label)
        combo.currentTextChanged.connect(callback)
        parent_layout.addWidget(label)
        parent_layout.addWidget(combo)
        return combo

    def _make_component(self) -> ComponentPreview:
        component = ComponentPreview()
        component.apply_density(self.current_density.value)
        return component

    def _build_side_navigation_preview(self) -> QWidget:
        shell = QFrame()
        shell.setObjectName("PreviewShell")
        layout = QHBoxLayout(shell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.preview_navigation = NavigationInterface(shell, showMenuButton=True, collapsible=True)
        for key, icon, text in [
            ("dashboard", FluentIcon.HOME, "总览"),
            ("backup", FluentIcon.SAVE, "备份"),
            ("restore", FluentIcon.HISTORY, "恢复"),
            ("migrate", FluentIcon.LINK, "迁移"),
            ("task", FluentIcon.CALENDAR, "任务计划"),
            ("environment", FluentIcon.DEVELOPER_TOOLS, "环境"),
            ("log", FluentIcon.DOCUMENT, "日志"),
        ]:
            self.preview_navigation.addItem(key, icon, text)
        self.preview_navigation.setCurrentItem("dashboard")
        layout.addWidget(self.preview_navigation)

        self.side_component = self._make_component()
        layout.addWidget(self.side_component, 1)
        return shell

    def _build_top_navigation_preview(self) -> QWidget:
        shell = QFrame()
        shell.setObjectName("PreviewShell")
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.top_pivot = Pivot()
        for key, text in [
            ("dashboard", "总览"),
            ("backup", "备份"),
            ("restore", "恢复"),
            ("migrate", "迁移"),
            ("task", "任务计划"),
            ("environment", "环境"),
            ("log", "日志"),
        ]:
            self.top_pivot.addItem(key, text)
        self.top_pivot.setCurrentItem("dashboard")
        layout.addWidget(self.top_pivot)

        self.top_component = self._make_component()
        layout.addWidget(self.top_component, 1)
        return shell

    def _build_plain_preview(self) -> QWidget:
        shell = QFrame()
        shell.setObjectName("PreviewShell")
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        segmented = SegmentedWidget()
        for key, text in [("daily", "日常备份"), ("restore", "恢复检查"), ("path", "Path 备份")]:
            segmented.addItem(key, text)
        segmented.setCurrentItem("daily")
        layout.addWidget(segmented)

        self.plain_component = self._make_component()
        layout.addWidget(self.plain_component, 1)
        return shell

    def _apply_theme(self, label: str) -> None:
        self.current_theme = _option_by_label(THEME_OPTIONS, label)
        setTheme(self.current_theme.value)

    def _apply_theme_color(self, label: str) -> None:
        self.current_color = _option_by_label(THEME_COLOR_OPTIONS, label)
        setThemeColor(QColor(str(self.current_color.value)), save=False)

    def _apply_navigation_style(self, label: str) -> None:
        self.current_navigation = _option_by_label(NAVIGATION_STYLE_OPTIONS, label)
        mapping = {"side": self.side_preview, "top": self.top_preview, "none": self.plain_preview}
        self.preview_stack.setCurrentWidget(mapping[str(self.current_navigation.value)])

    def _remember_window_style(self, label: str) -> None:
        self.current_window = _option_by_label(WINDOW_STYLE_OPTIONS, label)

    def _apply_density(self, label: str) -> None:
        self.current_density = _option_by_label(COMPONENT_DENSITY_OPTIONS, label)
        for component in [self.side_component, self.top_component, self.plain_component]:
            component.apply_density(self.current_density.value)

    def preview_nav_labels(self) -> list[str]:
        return ["总览", "备份", "恢复", "迁移", "任务计划", "环境", "日志"]

    def open_selected_window_preview(self) -> None:
        option = getattr(self, "current_window", WINDOW_STYLE_OPTIONS[0])
        window_class = option.value
        window = window_class()
        window.setWindowTitle(f"{option.label} 预览")
        window.resize(820, 560)
        window.setMinimumSize(720, 500)

        pages = [
            ("demo_dashboard", FluentIcon.HOME, "总览"),
            ("demo_backup", FluentIcon.SAVE, "备份"),
            ("demo_migrate", FluentIcon.LINK, "迁移"),
            ("demo_environment", FluentIcon.DEVELOPER_TOOLS, "环境"),
        ]
        first_page = None
        for route_key, icon, text in pages:
            page = ComponentPreview()
            page.setObjectName(route_key)
            page.apply_density(self.current_density.value)
            window.addSubInterface(page, icon, text, NavigationItemPosition.TOP)
            if first_page is None:
                first_page = page
        if first_page is not None:
            window.switchTo(first_page)
        self._window_previews.append(window)
        window.destroyed.connect(lambda *_: self._remove_window_preview(window))
        window.show()

    def _remove_window_preview(self, window: QWidget) -> None:
        if window in self._window_previews:
            self._window_previews.remove(window)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    setTheme(_option_by_key(THEME_OPTIONS, DEFAULT_THEME_KEY).value)
    setThemeColor(QColor(str(_option_by_key(THEME_COLOR_OPTIONS, DEFAULT_THEME_COLOR_KEY).value)), save=False)
    app.setStyleSheet(STYLE)
    window = FluentStyleDemoWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
