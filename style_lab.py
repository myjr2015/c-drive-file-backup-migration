from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
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
    LineEdit,
    ListWidget,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    ScrollArea,
    StrongBodyLabel,
    SwitchButton,
    Theme,
    setTheme,
    setThemeColor,
)

from project_config import APP_ICON_PATH, APP_TITLE


@dataclass(frozen=True)
class StyleTokens:
    primary: str
    background: str
    surface: str
    border: str
    text: str
    muted: str
    success: str
    warning: str
    radius: int
    spacing: int
    button_height: int
    card_padding: int


@dataclass(frozen=True)
class StyleFamily:
    key: str
    label: str
    stack: str
    positioning: str
    best_for: str
    caution: str
    visual_keywords: tuple[str, ...]
    tokens: StyleTokens


STYLE_FAMILIES = [
    StyleFamily(
        key="fluent",
        label="当前 / Fluent Qt",
        stack="PySide6 + qfluentwidgets",
        positioning="Windows 本地工具优先，贴近微软商店和系统设置页。",
        best_for="继续维护当前软件、任务计划、Junction、Path 等本机功能。",
        caution="GPLv3 依赖需要在开源说明里讲清楚，跨平台一致性弱于 Web。",
        visual_keywords=("侧边导航", "浅蓝强调", "紧凑卡片", "系统感"),
        tokens=StyleTokens(
            primary="#0078D4",
            background="#F7F9FC",
            surface="#FFFFFF",
            border="#DDE5F0",
            text="#1F2937",
            muted="#667085",
            success="#107C10",
            warning="#D83B01",
            radius=8,
            spacing=8,
            button_height=28,
            card_padding=10,
        ),
    ),
    StyleFamily(
        key="shadcn_tauri",
        label="Web / shadcn + Tauri",
        stack="React + shadcn/ui + Tailwind + Tauri",
        positioning="一套 Web UI 多端复用，用 CSS 和 Design Tokens 保证一致。",
        best_for="以后多软件统一风格、AI 生成界面、跨 Python/C#/Rust 后端壳。",
        caution="需要引入前端构建链；Tauri 负责壳，视觉统一来自 Web 层。",
        visual_keywords=("代码所有权", "高对比", "命令面板", "现代 Web"),
        tokens=StyleTokens(
            primary="#111827",
            background="#FAFAFA",
            surface="#FFFFFF",
            border="#E5E7EB",
            text="#111827",
            muted="#6B7280",
            success="#16A34A",
            warning="#EA580C",
            radius=6,
            spacing=8,
            button_height=32,
            card_padding=12,
        ),
    ),
    StyleFamily(
        key="flet_flutter",
        label="Python / Flet + Flutter",
        stack="Python + Flet + Flutter renderer",
        positioning="Python 写声明式 UI，视觉偏 Material/Flutter，跨平台成本低。",
        best_for="Python 工具快速做桌面、Web、移动端统一体验。",
        caution="不像 Windows 原生 Fluent；复杂本机系统集成仍要额外桥接。",
        visual_keywords=("Material", "圆角", "种子色", "跨平台"),
        tokens=StyleTokens(
            primary="#3F51B5",
            background="#F4F6FB",
            surface="#FFFFFF",
            border="#D8DEF0",
            text="#172033",
            muted="#64748B",
            success="#2E7D32",
            warning="#EF6C00",
            radius=12,
            spacing=10,
            button_height=36,
            card_padding=14,
        ),
    ),
    StyleFamily(
        key="avalonia_material",
        label="C# / Avalonia + Material",
        stack="C# + Avalonia UI + XAML themes",
        positioning="WPF 思路的跨平台自绘 UI，适合 .NET 长期桌面项目。",
        best_for="以后如果用 C# 做同类桌面工具，可保持严肃、稳定、工程化。",
        caution="Python 项目迁移成本高；视觉统一需要额外设计令牌转换。",
        visual_keywords=("XAML", "Material", "自绘", "企业工具"),
        tokens=StyleTokens(
            primary="#6750A4",
            background="#FFFBFE",
            surface="#FFFFFF",
            border="#E7E0EC",
            text="#1D1B20",
            muted="#625B71",
            success="#386A20",
            warning="#B3261E",
            radius=10,
            spacing=10,
            button_height=34,
            card_padding=12,
        ),
    ),
    StyleFamily(
        key="customtkinter",
        label="Python / CustomTkinter",
        stack="Python + Tkinter + CustomTkinter theme JSON",
        positioning="轻量、直接、部署简单，适合小脚本工具现代化。",
        best_for="体积敏感、功能简单、控件不复杂的 Python 小工具。",
        caution="高级列表、复杂布局和现代动效有限，不适合当前主线复杂度。",
        visual_keywords=("轻量", "简单", "低依赖", "传统桌面"),
        tokens=StyleTokens(
            primary="#1F6AA5",
            background="#F2F5F8",
            surface="#FFFFFF",
            border="#D0D7DE",
            text="#1F2328",
            muted="#687076",
            success="#2DA44E",
            warning="#CF222E",
            radius=8,
            spacing=8,
            button_height=30,
            card_padding=10,
        ),
    ),
]


STYLE_SHEET = """
QWidget {
    font-family: "Microsoft YaHei UI", "Segoe UI";
    font-size: 12px;
}
QLabel#LabTitle {
    font-size: 18px;
    font-weight: 700;
}
QLabel#PreviewTitle {
    font-size: 19px;
    font-weight: 700;
}
QLabel#MetricNumber {
    font-size: 20px;
    font-weight: 700;
}
QLabel#SectionLabel {
    font-size: 13px;
    font-weight: 700;
}
QFrame#Sidebar,
QFrame#PreviewShell,
QFrame#TopBar,
QFrame#TokenStrip {
    border: 1px solid transparent;
}
"""


def _set_button_height(button: QWidget, height: int) -> None:
    button.setMinimumWidth(0)
    button.setMaximumWidth(16777215)
    button.setFixedHeight(height)


def _family_by_label(label: str) -> StyleFamily:
    for family in STYLE_FAMILIES:
        if family.label == label:
            return family
    return STYLE_FAMILIES[0]


class SampleCard(CardWidget):
    def __init__(self, title: str, value: str, detail: str) -> None:
        super().__init__()
        self.title_label = CaptionLabel(title)
        self.value_label = QLabel(value)
        self.value_label.setObjectName("MetricNumber")
        self.detail_label = CaptionLabel(detail)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.detail_label)


class BackupRow(CardWidget):
    def __init__(self, name: str, detail: str, checked: bool, state: str) -> None:
        super().__init__()
        self.name_label = StrongBodyLabel(name)
        self.detail_label = CaptionLabel(detail)
        self.state_label = CaptionLabel(state)
        self.check_box = CheckBox()
        self.check_box.setChecked(checked)

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(8)
        row.addWidget(self.check_box)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        text_layout.addWidget(self.name_label)
        text_layout.addWidget(self.detail_label)
        row.addLayout(text_layout, 1)
        row.addWidget(self.state_label)


class CrossPlatformStyleLabWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("跨平台 UI 风格实验室")
        self.resize(1040, 680)
        self.setMinimumSize(920, 600)
        if Path(APP_ICON_PATH).exists():
            self.setWindowIcon(QIcon(str(APP_ICON_PATH)))

        self.current_family = STYLE_FAMILIES[0]
        self.sample_buttons: list[QWidget] = []
        self.sample_cards: list[SampleCard] = []
        self.sample_rows: list[BackupRow] = []

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(300)
        root.addWidget(sidebar)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 12, 12, 12)
        sidebar_layout.setSpacing(10)

        title = QLabel("UI 风格路线")
        title.setObjectName("LabTitle")
        subtitle = CaptionLabel("同一套备份/迁移场景，对比不同技术栈的视觉语言。")
        subtitle.setWordWrap(True)
        sidebar_layout.addWidget(title)
        sidebar_layout.addWidget(subtitle)

        self.family_combo = ComboBox()
        self.family_combo.addItems([family.label for family in STYLE_FAMILIES])
        self.family_combo.currentTextChanged.connect(self.apply_family_by_label)
        sidebar_layout.addWidget(StrongBodyLabel("选择方案"))
        sidebar_layout.addWidget(self.family_combo)

        self.stack_label = BodyLabel("")
        self.stack_label.setWordWrap(True)
        self.positioning_label = BodyLabel("")
        self.positioning_label.setWordWrap(True)
        self.best_for_label = BodyLabel("")
        self.best_for_label.setWordWrap(True)
        self.caution_label = BodyLabel("")
        self.caution_label.setWordWrap(True)
        self.notes_label = CaptionLabel("")
        self.notes_label.setWordWrap(True)

        for section_title, widget in [
            ("技术栈", self.stack_label),
            ("定位", self.positioning_label),
            ("适合", self.best_for_label),
            ("注意", self.caution_label),
            ("关键词", self.notes_label),
        ]:
            sidebar_layout.addWidget(StrongBodyLabel(section_title))
            sidebar_layout.addWidget(widget)

        sidebar_layout.addStretch(1)

        preview_scroll = ScrollArea()
        preview_scroll.setWidgetResizable(True)
        preview_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(preview_scroll, 1)

        self.preview_shell = QFrame()
        self.preview_shell.setObjectName("PreviewShell")
        preview_scroll.setWidget(self.preview_shell)

        self.preview_layout = QVBoxLayout(self.preview_shell)
        self.preview_layout.setContentsMargins(14, 14, 14, 14)
        self.preview_layout.setSpacing(10)

        self._build_preview()
        self.apply_family(self.current_family)

    def _build_preview(self) -> None:
        top_bar = QFrame()
        top_bar.setObjectName("TopBar")
        top = QHBoxLayout(top_bar)
        top.setContentsMargins(12, 10, 12, 10)
        top.setSpacing(8)

        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(2)
        self.preview_title = QLabel(APP_TITLE)
        self.preview_title.setObjectName("PreviewTitle")
        self.preview_subtitle = CaptionLabel("备份、迁移、恢复、任务计划和环境变量 Path 保护")
        title_box.addWidget(self.preview_title)
        title_box.addWidget(self.preview_subtitle)
        top.addLayout(title_box, 1)

        self.primary_button = PrimaryPushButton("立即备份")
        self.secondary_button = PushButton("选择目录")
        self.migrate_button = PushButton("迁移选中")
        self.cancel_button = PushButton("取消迁移")
        self.sample_buttons.extend([self.primary_button, self.secondary_button, self.migrate_button, self.cancel_button])
        for button in self.sample_buttons:
            top.addWidget(button)
        self.preview_layout.addWidget(top_bar)

        form = CardWidget()
        form_layout = QGridLayout(form)
        form_layout.setContentsMargins(12, 10, 12, 10)
        form_layout.setSpacing(8)
        form_layout.addWidget(StrongBodyLabel("备份目录"), 0, 0)
        path_edit = LineEdit()
        path_edit.setText("D:\\code\\backup")
        path_edit.setClearButtonEnabled(True)
        form_layout.addWidget(path_edit, 0, 1)
        form_layout.addWidget(StrongBodyLabel("排序"), 0, 2)
        sort = ComboBox()
        sort.addItems(["已迁移", "从大到小", "从小到大", "最近更新"])
        form_layout.addWidget(sort, 0, 3)
        form_layout.addWidget(StrongBodyLabel("自动保存配置"), 1, 0)
        switch = SwitchButton()
        switch.setChecked(True)
        form_layout.addWidget(switch, 1, 1)
        form_layout.addWidget(StrongBodyLabel("包含自定义目录"), 1, 2)
        check = CheckBox()
        check.setChecked(True)
        form_layout.addWidget(check, 1, 3)
        self.preview_layout.addWidget(form)

        metrics = QGridLayout()
        metrics.setSpacing(8)
        for column, data in enumerate(
            [
                ("当前保护", "7 项", "默认扫描用户目录下 . 开头文件夹"),
                ("今日备份", "1 次", "快照已校验复制完整性"),
                ("已迁移", "2 项", "D 盘真实目录 + C 盘 Junction"),
            ]
        ):
            card = SampleCard(*data)
            self.sample_cards.append(card)
            metrics.addWidget(card, 0, column)
        self.preview_layout.addLayout(metrics)

        section = QLabel("备份与迁移列表")
        section.setObjectName("SectionLabel")
        self.preview_layout.addWidget(section)

        for name, detail, checked, state in [
            (".codex", r"C:\Users\myjr2\.codex · 2.4 GB · 今天 10:30", True, "已备份"),
            (".happy", r"C:\Users\myjr2\.happy · 316 MB · 今天 10:21", True, "已备份"),
            (".vscode", r"D:\code\backup\迁移后的真实目录\.vscode · 128 MB", True, "已迁移"),
            (".ssh", r"C:\Users\myjr2\.ssh · 96 KB · 昨天 22:12", False, "敏感"),
        ]:
            row = BackupRow(name, detail, checked, state)
            self.sample_rows.append(row)
            self.preview_layout.addWidget(row)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        log_list = ListWidget()
        log_list.addItems(["2026-05-25_22-30-00 备份完成", "Path 已导出到 环境变量Path备份", ".vscode 取消迁移完成"])
        log_list.setMinimumHeight(112)
        token_strip = QFrame()
        token_strip.setObjectName("TokenStrip")
        token_layout = QVBoxLayout(token_strip)
        token_layout.setContentsMargins(12, 10, 12, 10)
        token_layout.setSpacing(6)
        token_layout.addWidget(StrongBodyLabel("Design Tokens"))
        self.token_color_label = CaptionLabel("")
        self.token_shape_label = CaptionLabel("")
        self.token_density_label = CaptionLabel("")
        self.token_color_label.setWordWrap(True)
        self.token_shape_label.setWordWrap(True)
        self.token_density_label.setWordWrap(True)
        token_layout.addWidget(self.token_color_label)
        token_layout.addWidget(self.token_shape_label)
        token_layout.addWidget(self.token_density_label)
        progress = ProgressBar()
        progress.setValue(72)
        token_layout.addWidget(progress)
        bottom.addWidget(log_list, 1)
        bottom.addWidget(token_strip, 1)
        self.preview_layout.addLayout(bottom)
        self.preview_layout.addStretch(1)

    def apply_family_by_label(self, label: str) -> None:
        self.apply_family(_family_by_label(label))

    def apply_family(self, family: StyleFamily) -> None:
        self.current_family = family
        tokens = family.tokens
        setThemeColor(QColor(tokens.primary), save=False)
        self.stack_label.setText(family.stack)
        self.positioning_label.setText(family.positioning)
        self.best_for_label.setText(family.best_for)
        self.caution_label.setText(family.caution)
        self.notes_label.setText(" / ".join(family.visual_keywords))
        self.token_color_label.setText(f"颜色：primary {tokens.primary}，surface {tokens.surface}，border {tokens.border}")
        self.token_shape_label.setText(f"形状：圆角 {tokens.radius}px，卡片内边距 {tokens.card_padding}px")
        self.token_density_label.setText(f"密度：间距 {tokens.spacing}px，按钮高度 {tokens.button_height}px")

        self.preview_shell.setStyleSheet(
            f"""
            QFrame#PreviewShell {{
                background: {tokens.background};
                border: 1px solid {tokens.border};
                border-radius: {tokens.radius + 2}px;
            }}
            QFrame#TopBar, QFrame#TokenStrip {{
                background: {tokens.surface};
                border: 1px solid {tokens.border};
                border-radius: {tokens.radius}px;
            }}
            QLabel#PreviewTitle, QLabel#MetricNumber {{
                color: {tokens.text};
            }}
            QLabel#SectionLabel {{
                color: {tokens.text};
            }}
            """
        )
        self._apply_spacing(self.preview_layout, tokens.spacing)
        for button in self.sample_buttons:
            _set_button_height(button, tokens.button_height)
        for card in [*self.sample_cards, *self.sample_rows]:
            card.layout().setContentsMargins(tokens.card_padding, tokens.card_padding, tokens.card_padding, tokens.card_padding)
            card.layout().setSpacing(max(4, tokens.spacing // 2))
            card.setStyleSheet(
                f"""
                CardWidget {{
                    background: {tokens.surface};
                    border: 1px solid {tokens.border};
                    border-radius: {tokens.radius}px;
                }}
                """
            )

    def _apply_spacing(self, layout: QVBoxLayout | QHBoxLayout | QGridLayout, spacing: int) -> None:
        layout.setSpacing(spacing)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    setTheme(Theme.AUTO)
    app.setStyleSheet(STYLE_SHEET)
    window = CrossPlatformStyleLabWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
