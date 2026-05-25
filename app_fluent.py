from __future__ import annotations

import os
import subprocess
import sys
import traceback
from ctypes import POINTER, WINFUNCTYPE, Structure, byref, c_int, c_long, c_void_p, cast, create_unicode_buffer, windll
from ctypes.wintypes import BOOL, DWORD, HWND, LPARAM, MSG, POINT
from html import escape
from pathlib import Path

from PySide6.QtCore import QTimer, QSize, Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
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
    FlowLayout,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    ListWidget,
    MSFluentWindow,
    NavigationItemPosition,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    RoundMenu,
    ScrollArea,
    StrongBodyLabel,
    SwitchButton,
    TextEdit,
    Theme,
    Action,
    setTheme,
    setThemeColor,
)

from backup_core import (
    ENVIRONMENT_PATH_DIR_NAME,
    LINK_STORE_DIR_NAME,
    RESTORE_BACKUP_DIR_NAME,
    BackupItem,
    BackupService,
    LinkMigrationStatus,
    ScannedItem,
    load_user_settings,
    write_user_settings,
)
from project_config import (
    APP_ICON_PATH,
    APP_TITLE,
    SCHEDULE_TASK_NAME,
    build_backup_items,
    build_sensitive_backup_warning,
    get_backup_root,
    is_legacy_fixed_default_selection,
    load_config,
)
from ui_helpers import format_size, is_valid_time


STYLE = """
QWidget {
    font-family: "Microsoft YaHei UI", "Segoe UI";
    font-size: 12px;
}
QFrame#DashboardMainPanel,
QFrame#RestoreDetailPanel {
    background: transparent;
}
QFrame#DashboardWorkspace,
QFrame#RestoreWorkspace {
    background: transparent;
}
QLabel#PageTitle {
    font-size: 15px;
    font-weight: 700;
}
QLabel#MetricValue {
    font-size: 15px;
    font-weight: 700;
}
CardWidget#MigratedLinkCard {
    border: 1px solid #8ec5ff;
    background: rgba(0, 120, 212, 0.08);
}
TextEdit {
    font-family: "Cascadia Mono", Consolas, "Microsoft YaHei UI";
    font-size: 11px;
}
"""


class Worker(QThread):
    log = Signal(str)
    failed = Signal(str)
    finished_ok = Signal()

    def __init__(self, func) -> None:
        super().__init__()
        self.func = func

    def run(self) -> None:
        try:
            self.func(self.log.emit)
        except Exception as exc:
            self.failed.emit(f"{exc}\n{traceback.format_exc(limit=2)}")
        else:
            self.finished_ok.emit()


class ScanWorker(QThread):
    finished_scan = Signal(list)
    failed = Signal(str)

    def __init__(self, service: BackupService, items: list[BackupItem]) -> None:
        super().__init__()
        self.service = service
        self.items = list(items)

    def run(self) -> None:
        try:
            self.finished_scan.emit(self.service.scan_items(self.items))
        except Exception as exc:
            self.failed.emit(f"{exc}\n{traceback.format_exc(limit=2)}")


class BackupItemCard(CardWidget):
    toggled = Signal(str, bool)
    open_directory_requested = Signal(Path)

    def __init__(
        self,
        scanned: ScannedItem,
        checked: bool,
        badge: str = "",
        extra_details: list[str] | None = None,
        tooltip: str | None = None,
    ) -> None:
        super().__init__()
        self.item = scanned.item
        self.source_path = Path(scanned.item.source)
        self.checkbox = CheckBox()
        self.checkbox.setChecked(checked and scanned.exists)
        self.checkbox.setEnabled(scanned.exists)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)
        layout.addWidget(self.checkbox)

        status = "存在" if scanned.exists else "缺失"
        details = [status, str(scanned.item.source), format_size(scanned.size_bytes)]
        if scanned.last_write_time:
            details.append(scanned.last_write_time.strftime("%Y-%m-%d %H:%M"))
        if scanned.item.name.startswith("自定义/"):
            details.append("自定义")
        if badge:
            details.append(badge)
        details.extend(extra_details or [])
        detail_text = " · ".join(escape(value) for value in details)
        self.title_line = QLabel(f"<strong>{escape(scanned.item.name)}</strong> · {detail_text}")
        self.title_line.setObjectName("ItemTitleLine")
        self.title_line.setTextFormat(Qt.TextFormat.RichText)
        self.title_line.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.title_line.setToolTip(tooltip or str(scanned.item.source))
        self.title_line.setWordWrap(False)
        self.title_line.setMinimumWidth(0)
        self.title_line.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.title_line, 1)

        self.checkbox.toggled.connect(lambda value: self.toggled.emit(self.item.name, value))
        self._context_actions = [Action(FluentIcon.FOLDER, "打开当前目录")]
        self._context_actions[0].triggered.connect(lambda: self.open_directory_requested.emit(self.source_path))
        for widget in [self, self.title_line]:
            widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            widget.customContextMenuRequested.connect(self._show_context_menu)

    def context_menu_actions(self) -> list[Action]:
        return list(self._context_actions)

    def _show_context_menu(self, position) -> None:
        menu = RoundMenu(parent=self)
        for action in self._context_actions:
            menu.addAction(action)
        sender = self.sender()
        widget = sender if isinstance(sender, QWidget) else self
        menu.exec(widget.mapToGlobal(position))


class MetricCard(CardWidget):
    def __init__(self, title: str, value: str, subtitle: str = "") -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(1)

        self.title_label = CaptionLabel(title)
        self.title_label.setObjectName("MetricTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("MetricValue")
        self.subtitle_label = CaptionLabel(subtitle)
        self.subtitle_label.setObjectName("Muted")
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.subtitle_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)

    def set_subtitle(self, value: str) -> None:
        self.subtitle_label.setText(value)


APP_BUTTON_HEIGHT = 30
APP_DEFAULT_SIZE = QSize(720, 540)
APP_MINIMUM_SIZE = QSize(672, 500)
DEFAULT_THEME_MODE = Theme.AUTO
DEFAULT_THEME_COLOR = "#0078D4"
WM_GETMINMAXINFO = 0x0024
WM_WINDOWPOSCHANGING = 0x0046
WM_WINDOWPOSCHANGED = 0x0047
WM_SYSCOMMAND = 0x0112
WM_ENTERSIZEMOVE = 0x0231
WM_EXITSIZEMOVE = 0x0232
SC_MOVE = 0xF010


class NativeMinMaxInfo(Structure):
    _fields_ = [
        ("ptReserved", POINT),
        ("ptMaxSize", POINT),
        ("ptMaxPosition", POINT),
        ("ptMinTrackSize", POINT),
        ("ptMaxTrackSize", POINT),
    ]


class NativeWindowPos(Structure):
    _fields_ = [
        ("hwnd", HWND),
        ("hwndInsertAfter", HWND),
        ("x", c_int),
        ("y", c_int),
        ("cx", c_int),
        ("cy", c_int),
        ("flags", c_int),
    ]


class NativeRect(Structure):
    _fields_ = [
        ("left", c_long),
        ("top", c_long),
        ("right", c_long),
        ("bottom", c_long),
    ]


EnumWindowsCallback = WINFUNCTYPE(BOOL, HWND, LPARAM)


def apply_default_ui_theme() -> None:
    setTheme(DEFAULT_THEME_MODE)
    setThemeColor(QColor(DEFAULT_THEME_COLOR), save=False)


def set_compact_button(widget: QWidget) -> None:
    widget.setMinimumWidth(0)
    widget.setMaximumWidth(16777215)
    widget.setFixedHeight(APP_BUTTON_HEIGHT)


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def app_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        return app_base_dir() / "data"
    return Path(__file__).with_name("data")


def resource_path(relative_path: Path | str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", app_base_dir()))
    return base / Path(relative_path)


class FluentBackupApp(MSFluentWindow):
    def __init__(self) -> None:
        self._system_move_size: tuple[int, int] | None = None
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        icon = QIcon(str(resource_path(APP_ICON_PATH)))
        if not icon.isNull():
            self.setWindowIcon(icon)
        self.resize(APP_DEFAULT_SIZE)
        self.setMinimumSize(APP_MINIMUM_SIZE)

        config = load_config()
        self.home = Path.home()
        self.user_settings_path = app_data_dir() / "user-settings.json"
        user_settings = load_user_settings(self.user_settings_path)
        self.backup_root = get_backup_root(config, user_settings)
        self.service = BackupService(self.backup_root)
        self.custom_items_config: list[dict] = user_settings.get("custom_items", [])
        self.items = build_backup_items(self.home, self.custom_items_config)
        self.schedule_time_value = user_settings.get("schedule_time") or "22:30"
        saved_selected = set(user_settings.get("selected_items", []))
        existing_names = {item.name for item in self.items if item.source.exists()}
        if user_settings["settings_exists"] and not is_legacy_fixed_default_selection(saved_selected):
            self.selected_names: set[str] = saved_selected & existing_names
        else:
            self.selected_names = existing_names
        self.item_cards: list[BackupItemCard] = []
        self.link_cards: list[BackupItemCard] = []
        self.link_selected_names: set[str] = set()
        self.snapshots: list[Path] = []
        self.worker: Worker | None = None
        self.scan_worker: ScanWorker | None = None
        self._active_info_bar = None
        self.scanned_items: list[ScannedItem] = []
        self.last_link_store_path = self.service.default_link_store_root()
        self._build_ui()
        self.normalize_internal_backup_directories()
        self.refresh_all()

    def sizeHint(self) -> QSize:
        return APP_DEFAULT_SIZE

    def minimumSizeHint(self) -> QSize:
        return APP_MINIMUM_SIZE

    def nativeEvent(self, eventType, message):
        if sys.platform == "win32":
            try:
                msg = MSG.from_address(message.__int__())
            except Exception:
                msg = None
            if msg is not None:
                if msg.message == WM_SYSCOMMAND and (int(msg.wParam) & 0xFFF0) == SC_MOVE:
                    self.begin_system_move_size_guard()
                elif msg.message == WM_ENTERSIZEMOVE and self._system_move_size is None:
                    self.begin_system_move_size_guard()
                elif msg.message == WM_WINDOWPOSCHANGING:
                    if self.keep_system_move_size(int(msg.lParam)):
                        return True, 0
                elif msg.message == WM_WINDOWPOSCHANGED:
                    self.keep_system_move_size(int(msg.lParam))
                elif msg.message == WM_GETMINMAXINFO:
                    if self.handle_min_track_message(msg):
                        return True, 0
                elif msg.message == WM_EXITSIZEMOVE:
                    self.end_system_move_size_guard()
        return super().nativeEvent(eventType, message)

    def begin_system_move_size_guard(self) -> None:
        self._system_move_size = (self.width(), self.height())

    def end_system_move_size_guard(self) -> None:
        self._system_move_size = None

    def keep_system_move_size(self, window_pos_address: int) -> bool:
        if self._system_move_size is None or not window_pos_address:
            return False
        width, height = self._system_move_size
        pos = cast(c_void_p(window_pos_address), POINTER(NativeWindowPos)).contents
        pos.cx = width
        pos.cy = height
        return True

    def handle_min_track_message(self, message) -> bool:
        l_param = getattr(message, "lParam", None)
        if l_param is None and hasattr(message, "contents"):
            l_param = getattr(message.contents, "lParam", None)
        if l_param is None:
            return False
        return self.apply_compact_min_track_size(int(l_param))

    def apply_compact_min_track_size(self, minmax_info_address: int) -> bool:
        if not minmax_info_address:
            return False
        info = cast(c_void_p(minmax_info_address), POINTER(NativeMinMaxInfo)).contents
        info.ptMinTrackSize.x = APP_MINIMUM_SIZE.width()
        info.ptMinTrackSize.y = APP_MINIMUM_SIZE.height()
        return True

    def closeEvent(self, event) -> None:
        self._close_active_info_bar()
        self._wait_for_thread(self.scan_worker)
        self._wait_for_thread(self.worker)
        super().closeEvent(event)

    def _build_ui(self) -> None:
        self.navigation = self.navigationInterface
        self.navigation.setMinimumWidth(48)
        self.stack = self.stackedWidget

        self.dashboard_page = self._build_dashboard_page()
        self.items_page = self._build_items_page()
        self.restore_page = self._build_restore_page()
        self.link_page = self._build_link_page()
        self.task_page = self._build_task_page()
        self.environment_page = self._build_environment_page()
        self.log_page = self._build_log_page()

        self._bind_navigation()
        self._set_current_page(self.dashboard_page)

    def _bind_navigation(self) -> None:
        page_pairs = [
            ("dashboard", "总览", FluentIcon.HOME, self.dashboard_page, NavigationItemPosition.TOP),
            ("backup", "备份", FluentIcon.CHECKBOX, self.items_page, NavigationItemPosition.TOP),
            ("restore", "恢复", FluentIcon.SYNC, self.restore_page, NavigationItemPosition.TOP),
            ("migration", "迁移", FluentIcon.LINK, self.link_page, NavigationItemPosition.TOP),
            ("task", "任务计划", FluentIcon.CALENDAR, self.task_page, NavigationItemPosition.TOP),
            ("environment", "环境", FluentIcon.DEVELOPER_TOOLS, self.environment_page, NavigationItemPosition.TOP),
            ("log", "日志", FluentIcon.DOCUMENT, self.log_page, NavigationItemPosition.BOTTOM),
        ]
        self.navigation_buttons = []
        self.page_route_keys: dict[QWidget, str] = {}
        for route_key, text, icon, page, position in page_pairs:
            page.setObjectName(route_key)
            widget = self.addSubInterface(
                interface=page,
                icon=icon,
                text=text,
                position=position,
            )
            self.navigation_buttons.append(widget)
            self.page_route_keys[page] = route_key

    def _set_current_page(self, page: QWidget) -> None:
        self.switchTo(page)
        if hasattr(self, "page_route_keys"):
            self.navigation.setCurrentItem(self.page_route_keys.get(page, "dashboard"))

    def _base_page(self) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        page.setObjectName("Page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        return page, layout

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("HeaderBand")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(5)

        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        title = QLabel(APP_TITLE)
        title.setObjectName("PageTitle")
        title_row.addWidget(title)
        title_row.addStretch()
        refresh = PushButton("刷新")
        set_compact_button(refresh)
        refresh.clicked.connect(self.refresh_all)
        title_row.addWidget(refresh)
        layout.addLayout(title_row)

        path_row = QHBoxLayout()
        path_row.setSpacing(5)
        path_row.addWidget(BodyLabel("备份目录"))
        self.backup_root_edit = LineEdit()
        self.backup_root_edit.setObjectName("BackupRootEdit")
        self.backup_root_edit.setFixedHeight(32)
        self.backup_root_edit.setMinimumWidth(120)
        self.backup_root_edit.setText(str(self.backup_root))
        path_row.addWidget(self.backup_root_edit, 1)
        choose_dir = PushButton("选择")
        set_compact_button(choose_dir)
        choose_dir.clicked.connect(self.choose_backup_root)
        save_dir = PrimaryPushButton("保存")
        set_compact_button(save_dir)
        save_dir.clicked.connect(self.save_backup_root_from_input)
        open_dir = PushButton("打开")
        set_compact_button(open_dir)
        open_dir.clicked.connect(self.open_backup_dir)
        path_row.addWidget(choose_dir)
        path_row.addWidget(save_dir)
        path_row.addWidget(open_dir)
        layout.addLayout(path_row)
        return header

    def _build_dashboard_page(self) -> QWidget:
        page, layout = self._base_page()
        layout.addWidget(self._build_header())

        self.dashboard_workspace = QFrame()
        self.dashboard_workspace.setObjectName("DashboardWorkspace")
        workspace_layout = QVBoxLayout(self.dashboard_workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(6)
        layout.addWidget(self.dashboard_workspace, 1)

        self.dashboard_main_panel = QFrame()
        self.dashboard_main_panel.setObjectName("DashboardMainPanel")
        main_layout = QVBoxLayout(self.dashboard_main_panel)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)
        workspace_layout.addWidget(self.dashboard_main_panel)

        main_layout.addWidget(self._build_next_action_card())
        main_layout.addWidget(self._build_schedule_card())

        self.dashboard_metrics_panel = self._build_metrics_panel()
        main_layout.addWidget(self.dashboard_metrics_panel)

        self.dashboard_side_panel = self.dashboard_metrics_panel
        self.status_panel = self.dashboard_metrics_panel
        return page

    def _build_items_page(self) -> QWidget:
        page, layout = self._base_page()
        layout.addWidget(self._section_title("备份", "选择要保护的用户目录、AI 会话和开发配置。"))

        item_card = CardWidget()
        item_layout = QVBoxLayout(item_card)
        item_layout.setContentsMargins(8, 6, 8, 8)
        item_layout.setSpacing(6)

        item_bar = QVBoxLayout()
        item_bar.setSpacing(5)
        title_row = QHBoxLayout()
        title_row.addWidget(StrongBodyLabel("备份列表"))
        title_row.addStretch()
        title_row.addWidget(CaptionLabel("排序"))
        self.item_sort_combo = ComboBox()
        self.item_sort_combo.addItems(["从大到小", "从小到大", "最近更新"])
        self.item_sort_combo.setCurrentText("从大到小")
        self.item_sort_combo.currentTextChanged.connect(lambda _: self.refresh_item_cards())
        title_row.addWidget(self.item_sort_combo)
        item_bar.addLayout(title_row)

        self.items_toolbar = QFrame()
        self.items_toolbar.setObjectName("ItemsGroupedToolbar")
        action_layout = FlowLayout(self.items_toolbar, needAni=False)
        action_layout.setContentsMargins(6, 5, 6, 5)
        action_layout.setHorizontalSpacing(5)
        action_layout.setVerticalSpacing(5)

        selection_group = QFrame()
        selection_group.setObjectName("ToolbarGroup")
        selection_group.setMinimumWidth(126)
        selection_layout = QVBoxLayout(selection_group)
        selection_layout.setContentsMargins(6, 5, 6, 5)
        selection_layout.setSpacing(3)
        selection_layout.addWidget(CaptionLabel("选择"))
        selection_row = QHBoxLayout()
        selection_row.setSpacing(5)
        select_all = PushButton("全选")
        set_compact_button(select_all)
        select_all.clicked.connect(lambda: self.set_all_items(True))
        select_none = PushButton("全不选")
        set_compact_button(select_none)
        select_none.clicked.connect(lambda: self.set_all_items(False))
        selection_row.addWidget(select_all)
        selection_row.addWidget(select_none)
        selection_row.addStretch()
        selection_layout.addLayout(selection_row)
        action_layout.addWidget(selection_group)

        backup_group = QFrame()
        backup_group.setObjectName("ToolbarGroup")
        backup_group.setMinimumWidth(96)
        backup_layout = QVBoxLayout(backup_group)
        backup_layout.setContentsMargins(6, 5, 6, 5)
        backup_layout.setSpacing(3)
        backup_layout.addWidget(CaptionLabel("执行"))
        backup_row = QHBoxLayout()
        backup_row.setSpacing(5)
        backup = PrimaryPushButton("立即备份")
        backup.setObjectName("BackupNowButton")
        set_compact_button(backup)
        backup.clicked.connect(self.create_backup)
        backup_row.addWidget(backup)
        backup_row.addStretch()
        backup_layout.addLayout(backup_row)
        action_layout.addWidget(backup_group)

        custom_group = QFrame()
        custom_group.setObjectName("ToolbarGroup")
        custom_group.setMinimumWidth(360)
        custom_layout = QVBoxLayout(custom_group)
        custom_layout.setContentsMargins(6, 5, 6, 5)
        custom_layout.setSpacing(3)
        custom_layout.addWidget(CaptionLabel("自定义"))
        custom_row = QHBoxLayout()
        custom_row.setSpacing(5)
        add_folder = PushButton("添加文件夹")
        set_compact_button(add_folder)
        add_folder.clicked.connect(self.add_custom_folder)
        add_file = PushButton("添加文件")
        set_compact_button(add_file)
        add_file.clicked.connect(self.add_custom_file)
        remove_custom = PushButton("删除已勾选自定义")
        set_compact_button(remove_custom)
        remove_custom.clicked.connect(self.remove_selected_custom_items)
        custom_row.addWidget(add_folder)
        custom_row.addWidget(add_file)
        custom_row.addWidget(remove_custom)
        custom_row.addStretch()
        custom_layout.addLayout(custom_row)
        action_layout.addWidget(custom_group)

        item_bar.addWidget(self.items_toolbar)
        item_layout.addLayout(item_bar)

        self.item_container = QWidget()
        self.item_layout = QVBoxLayout(self.item_container)
        self.item_layout.setContentsMargins(0, 0, 0, 0)
        self.item_layout.setSpacing(6)
        self.item_layout.addStretch()

        self.item_scroll = ScrollArea()
        self.item_scroll.setWidgetResizable(True)
        self.item_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.item_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.item_scroll.setWidget(self.item_container)
        item_layout.addWidget(self.item_scroll, 1)
        layout.addWidget(item_card, 1)
        return page

    def _build_next_action_card(self) -> CardWidget:
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)
        header = QHBoxLayout()
        header.addWidget(StrongBodyLabel("当前保护状态"))
        header.addStretch()
        header.addWidget(CaptionLabel("配置保存后会同步到计划任务"))
        layout.addLayout(header)
        self.protection_summary = BodyLabel("读取中")
        layout.addWidget(self.protection_summary)
        self.protection_bar = ProgressBar()
        self.protection_bar.setRange(0, 100)
        layout.addWidget(self.protection_bar)
        return card

    def _build_metrics_panel(self) -> CardWidget:
        panel = CardWidget()
        panel.setObjectName("DashboardMetricsPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(5)

        layout.addWidget(StrongBodyLabel("状态摘要"))

        metric_grid = QGridLayout()
        metric_grid.setHorizontalSpacing(5)
        metric_grid.setVerticalSpacing(5)
        layout.addLayout(metric_grid)

        self.exists_metric = MetricCard("可备份", "0", "存在内容")
        self.selected_metric = MetricCard("已选择", "0", "当前配置")
        self.snapshot_metric = MetricCard("快照", "0", "最近记录")
        self.schedule_metric = MetricCard("定时", "读取中", f"每天 {self.schedule_time_value}")
        metric_cards = [self.exists_metric, self.selected_metric, self.snapshot_metric, self.schedule_metric]
        for metric in metric_cards:
            metric.setMinimumHeight(48)
        metric_grid.addWidget(self.exists_metric, 0, 0)
        metric_grid.addWidget(self.selected_metric, 0, 1)
        metric_grid.addWidget(self.snapshot_metric, 1, 0)
        metric_grid.addWidget(self.schedule_metric, 1, 1)
        for column in range(2):
            metric_grid.setColumnStretch(column, 1)
        return panel

    def _build_schedule_card(self) -> CardWidget:
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        title = QHBoxLayout()
        title.addWidget(StrongBodyLabel("定时备份"))
        title.addStretch()
        self.schedule_switch = SwitchButton()
        self.schedule_switch.setOnText("启用")
        self.schedule_switch.setOffText("关闭")
        self.schedule_switch.checkedChanged.connect(self._schedule_switch_changed)
        title.addWidget(self.schedule_switch)
        layout.addLayout(title)

        row = QHBoxLayout()
        row.setSpacing(5)
        row.addWidget(BodyLabel("每天"))
        self.schedule_time = LineEdit()
        self.schedule_time.setObjectName("ScheduleTimeEdit")
        self.schedule_time.setText(self.schedule_time_value)
        self.schedule_time.setFixedWidth(78)
        self.schedule_time.setFixedHeight(32)
        self.schedule_time.editingFinished.connect(self.save_schedule_time_from_input)
        row.addWidget(self.schedule_time)
        create = PrimaryPushButton("创建/更新")
        set_compact_button(create)
        create.clicked.connect(self.create_schedule)
        delete = PushButton("删除")
        set_compact_button(delete)
        delete.clicked.connect(self.delete_schedule)
        row.addWidget(create)
        row.addWidget(delete)
        layout.addLayout(row)

        self.schedule_status = CaptionLabel("状态：读取中")
        self.schedule_status.setObjectName("Muted")
        layout.addWidget(self.schedule_status)
        return card

    def _build_restore_page(self) -> QWidget:
        page, layout = self._base_page()
        layout.addWidget(self._section_title("恢复快照", f"恢复前会自动把当前目标目录备份到{RESTORE_BACKUP_DIR_NAME}。"))

        self.restore_workspace = QFrame()
        self.restore_workspace.setObjectName("RestoreWorkspace")
        body = QHBoxLayout(self.restore_workspace)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(6)
        layout.addWidget(self.restore_workspace, 1)

        list_card = CardWidget()
        list_card.setMinimumWidth(170)
        list_card.setMaximumWidth(204)
        list_layout = QVBoxLayout(list_card)
        list_layout.setContentsMargins(8, 6, 8, 8)
        list_layout.setSpacing(5)
        list_layout.addWidget(StrongBodyLabel("快照列表"))
        self.restore_snapshot_list = ListWidget()
        self.restore_snapshot_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.restore_snapshot_list.currentRowChanged.connect(lambda _: self.refresh_restore_detail())
        list_layout.addWidget(self.restore_snapshot_list, 1)
        body.addWidget(list_card)

        self.restore_detail_panel = CardWidget()
        self.restore_detail_panel.setObjectName("RestoreDetailPanel")
        action_layout = QVBoxLayout(self.restore_detail_panel)
        action_layout.setContentsMargins(8, 6, 8, 8)
        action_layout.setSpacing(6)
        header = QHBoxLayout()
        header.addWidget(StrongBodyLabel("快照详情"))
        header.addStretch()
        restore = PrimaryPushButton("恢复选中快照")
        set_compact_button(restore)
        restore.clicked.connect(self.restore_selected)
        header.addWidget(restore)
        action_layout.addLayout(header)
        self.restore_selected_summary = BodyLabel("读取中")
        action_layout.addWidget(self.restore_selected_summary)
        action_layout.addWidget(CaptionLabel("默认项目恢复到当前用户目录；自定义项目恢复到 manifest 记录的原始路径。"))
        self.restore_snapshot_detail = TextEdit()
        self.restore_snapshot_detail.setReadOnly(True)
        self.restore_snapshot_detail.setMinimumHeight(120)
        action_layout.addWidget(self.restore_snapshot_detail, 1)
        warning = CaptionLabel("恢复会覆盖目标路径，执行前会先备份当前目标。")
        warning.setObjectName("Muted")
        action_layout.addWidget(warning)
        body.addWidget(self.restore_detail_panel, 1)
        return page

    def _build_link_page(self) -> QWidget:
        page, layout = self._base_page()
        layout.addWidget(self._section_title("迁移", f"先备份，再移动到 D 盘{LINK_STORE_DIR_NAME}，原位置保留 Junction 引用。"))

        card = CardWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 6, 8, 8)
        card_layout.setSpacing(6)

        link_bar = QVBoxLayout()
        link_bar.setSpacing(5)
        title_row = QHBoxLayout()
        title_row.addWidget(StrongBodyLabel("迁移列表"))
        title_row.addStretch()
        title_row.addWidget(CaptionLabel("排序"))
        self.link_sort_combo = ComboBox()
        self.link_sort_combo.addItems(["已迁移", "从大到小", "从小到大", "最近更新"])
        self.link_sort_combo.setCurrentText("已迁移")
        self.link_sort_combo.currentTextChanged.connect(lambda _: self.refresh_link_items())
        title_row.addWidget(self.link_sort_combo)
        link_bar.addLayout(title_row)

        self.link_toolbar = QFrame()
        self.link_toolbar.setObjectName("ItemsGroupedToolbar")
        toolbar_layout = FlowLayout(self.link_toolbar, needAni=False)
        toolbar_layout.setContentsMargins(6, 5, 6, 5)
        toolbar_layout.setHorizontalSpacing(5)
        toolbar_layout.setVerticalSpacing(5)

        self.link_selection_group = QFrame()
        self.link_selection_group.setObjectName("ToolbarGroup")
        self.link_selection_group.setMinimumWidth(126)
        selection_layout = QVBoxLayout(self.link_selection_group)
        selection_layout.setContentsMargins(6, 5, 6, 5)
        selection_layout.setSpacing(3)
        selection_layout.addWidget(CaptionLabel("选择"))
        selection_row = QHBoxLayout()
        selection_row.setSpacing(5)
        link_select_all = PushButton("全选")
        set_compact_button(link_select_all)
        link_select_all.clicked.connect(lambda: self.set_all_link_items(True))
        link_select_none = PushButton("全不选")
        set_compact_button(link_select_none)
        link_select_none.clicked.connect(lambda: self.set_all_link_items(False))
        selection_row.addWidget(link_select_all)
        selection_row.addWidget(link_select_none)
        selection_row.addStretch()
        selection_layout.addLayout(selection_row)
        toolbar_layout.addWidget(self.link_selection_group)

        self.link_action_group = QFrame()
        self.link_action_group.setObjectName("ToolbarGroup")
        self.link_action_group.setMinimumWidth(120)
        action_group_layout = QVBoxLayout(self.link_action_group)
        action_group_layout.setContentsMargins(6, 5, 6, 5)
        action_group_layout.setSpacing(3)
        action_group_layout.addWidget(CaptionLabel("操作"))
        action_row = QHBoxLayout()
        action_row.setSpacing(5)
        self.migrate_button = PrimaryPushButton("迁移")
        set_compact_button(self.migrate_button)
        self.migrate_button.clicked.connect(self.migrate_selected_link)
        action_row.addWidget(self.migrate_button)
        action_row.addStretch()
        action_group_layout.addLayout(action_row)
        toolbar_layout.addWidget(self.link_action_group)

        self.link_cancel_group = QFrame()
        self.link_cancel_group.setObjectName("ToolbarGroup")
        self.link_cancel_group.setMinimumWidth(120)
        cancel_group_layout = QVBoxLayout(self.link_cancel_group)
        cancel_group_layout.setContentsMargins(6, 5, 6, 5)
        cancel_group_layout.setSpacing(3)
        cancel_group_layout.addWidget(CaptionLabel("还原"))
        cancel_row = QHBoxLayout()
        cancel_row.setSpacing(5)
        self.cancel_migration_button = PushButton("取消迁移")
        set_compact_button(self.cancel_migration_button)
        self.cancel_migration_button.clicked.connect(self.cancel_selected_link_migration)
        cancel_row.addWidget(self.cancel_migration_button)
        cancel_row.addStretch()
        cancel_group_layout.addLayout(cancel_row)
        toolbar_layout.addWidget(self.link_cancel_group)

        link_bar.addWidget(self.link_toolbar)
        card_layout.addLayout(link_bar)

        self.link_container = QWidget()
        self.link_layout = QVBoxLayout(self.link_container)
        self.link_layout.setContentsMargins(0, 0, 0, 0)
        self.link_layout.setSpacing(6)
        self.link_layout.addStretch()

        self.link_scroll = ScrollArea()
        self.link_scroll.setWidgetResizable(True)
        self.link_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.link_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.link_scroll.setWidget(self.link_container)
        card_layout.addWidget(self.link_scroll)
        self.link_hint = CaptionLabel("")
        card_layout.addWidget(self.link_hint)
        self.refresh_link_items()
        layout.addWidget(card, 1)
        self.link_terms_card = self._build_link_terms_card()
        layout.addWidget(self.link_terms_card)
        return page

    def _build_link_terms_card(self) -> CardWidget:
        card = CardWidget()
        card.setObjectName("LinkTermsCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(0)
        self.link_terms_text = CaptionLabel(
            "术语说明 · Junction：原位置引用 D 盘迁移后的真实目录；恢复前备份用于回退；取消迁移会把真实目录移回原位置。"
        )
        self.link_terms_text.setObjectName("Muted")
        self.link_terms_text.setWordWrap(True)
        layout.addWidget(self.link_terms_text)
        return card

    def _build_task_page(self) -> QWidget:
        page, layout = self._base_page()
        layout.addWidget(self._section_title("任务计划", "打开 Windows 任务计划程序，检查或调整自动备份任务。"))

        card = CardWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 6, 8, 8)
        card_layout.setSpacing(6)
        card_layout.addWidget(StrongBodyLabel("定时备份任务"))
        self.task_page_summary = BodyLabel(f"任务计划名：{SCHEDULE_TASK_NAME}\n默认时间：每天 {self.schedule_time_value}")
        self.task_page_summary.setWordWrap(True)
        card_layout.addWidget(self.task_page_summary)
        hint = CaptionLabel("如果想确认任务是否启用、查看上次运行结果，打开后在任务计划程序库里查找这个任务名。")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        card_layout.addWidget(hint)
        open_task = PushButton("打开任务计划程序")
        set_compact_button(open_task)
        open_task.clicked.connect(self.open_task_scheduler)
        card_layout.addWidget(open_task, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _build_environment_page(self) -> QWidget:
        page, layout = self._base_page()
        layout.addWidget(self._section_title("环境变量", "以管理员身份打开系统环境变量，重点检查 Path。"))

        card = CardWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 6, 8, 8)
        card_layout.setSpacing(6)
        card_layout.addWidget(StrongBodyLabel("系统 Path"))
        self.environment_page_summary = BodyLabel(
            "Path 决定命令行能不能直接找到 Python、Node.js、Git、ffmpeg 等工具。\n"
            "点击下面按钮会请求管理员权限打开系统环境变量；打开后请选择 Path 再编辑。"
        )
        self.environment_page_summary.setWordWrap(True)
        card_layout.addWidget(self.environment_page_summary)
        warning = CaptionLabel("修改 Path 前建议先备份当前内容；删除错误路径可能影响命令行工具。")
        warning.setObjectName("Muted")
        warning.setWordWrap(True)
        card_layout.addWidget(warning)
        backup_path = PushButton("备份 Path")
        set_compact_button(backup_path)
        backup_path.clicked.connect(self.backup_environment_path_async)
        card_layout.addWidget(backup_path, alignment=Qt.AlignmentFlag.AlignLeft)
        open_env = PushButton("以管理员身份打开环境变量")
        set_compact_button(open_env)
        open_env.clicked.connect(self.open_environment_variables)
        card_layout.addWidget(open_env, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _build_log_page(self) -> QWidget:
        page, layout = self._base_page()
        layout.addWidget(self._section_title("日志", "后台任务输出和错误会显示在这里。"))
        self.log = TextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, 1)
        return page

    def _section_title(self, title: str, subtitle: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("HeaderBand")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(1)
        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        layout.addWidget(title_label)
        hint = CaptionLabel(subtitle)
        hint.setObjectName("Muted")
        layout.addWidget(hint)
        return frame

    def refresh_all(self) -> None:
        self.refresh_items()
        self.refresh_snapshots()
        self.refresh_schedule_status()

    def normalize_internal_backup_directories(self) -> None:
        try:
            moved_paths = self.service.normalize_internal_backup_directories(self.items)
        except Exception as exc:
            self.append_log(f"中文维护目录整理失败：{exc}")
            return
        if moved_paths:
            self.append_log("已整理旧英文维护目录为中文目录。")

    def refresh_items(self) -> None:
        if self.scan_worker and self.scan_worker.isRunning():
            return
        self.protection_summary.setText("正在扫描备份内容...")
        self.scan_worker = ScanWorker(self.service, self.items)
        self.scan_worker.finished_scan.connect(self.apply_scanned_items)
        self.scan_worker.failed.connect(self._show_error)
        self.scan_worker.start()

    def apply_scanned_items(self, scanned: list[ScannedItem]) -> None:
        self.scanned_items = scanned
        self.refresh_item_cards()
        self.refresh_link_items()
        self.refresh_link_hint()
        self.refresh_restore_detail()

    def refresh_item_cards(self) -> None:
        scrollbar = self.item_scroll.verticalScrollBar() if hasattr(self, "item_scroll") else None
        previous_scroll_value = scrollbar.value() if scrollbar else 0
        for card in self.item_cards:
            card.setParent(None)
        self.item_cards = []

        exists_count = self._refresh_item_status_widgets(rebuild_cards=True)
        if scrollbar:
            scrollbar.setValue(min(previous_scroll_value, scrollbar.maximum()))
        self.refresh_link_items()

    def _refresh_item_status_widgets(self, rebuild_cards: bool = False) -> int:
        exists_count = 0
        for entry in self._sorted_scanned_items():
            if entry.exists:
                exists_count += 1
            if rebuild_cards:
                card = BackupItemCard(entry, entry.item.name in self.selected_names)
                card.toggled.connect(self._set_item_selected)
                card.open_directory_requested.connect(self.open_current_directory)
                self.item_layout.insertWidget(self.item_layout.count() - 1, card)
                self.item_cards.append(card)

        self.exists_metric.set_value(str(exists_count))
        selected_count = len(self._selected_items())
        self.selected_metric.set_value(str(selected_count))
        percent = int(selected_count / exists_count * 100) if exists_count else 0
        self.protection_bar.setValue(percent)
        self.protection_summary.setText(f"已选择 {selected_count} / {exists_count} 个存在内容。")
        if hasattr(self, "restore_selected_summary"):
            self.restore_selected_summary.setText(f"将恢复当前勾选的 {selected_count} 个项目。")
        return exists_count

    def _sorted_scanned_items(self, mode: str | None = None) -> list[ScannedItem]:
        if mode is None:
            mode = self.item_sort_combo.currentText() if hasattr(self, "item_sort_combo") else "从大到小"
        if mode == "从小到大":
            return sorted(self.scanned_items, key=lambda entry: (not entry.exists, entry.size_bytes, entry.item.name.lower()))
        if mode == "最近更新":
            return sorted(
                self.scanned_items,
                key=lambda entry: (
                    not entry.exists,
                    -(entry.last_write_time.timestamp() if entry.last_write_time else 0),
                    entry.item.name.lower(),
                ),
            )
        return sorted(self.scanned_items, key=lambda entry: (not entry.exists, -entry.size_bytes, entry.item.name.lower()))

    def refresh_snapshots(self) -> None:
        self.snapshots = self.service.list_snapshots()
        self.restore_snapshot_list.clear()
        for snapshot in self.snapshots:
            self.restore_snapshot_list.addItem(snapshot.name)
        if self.snapshots and self.restore_snapshot_list.currentRow() < 0:
            self.restore_snapshot_list.setCurrentRow(0)
        self.snapshot_metric.set_value(str(len(self.snapshots)))
        if self.snapshots:
            self.snapshot_metric.set_subtitle(f"最新：{self.snapshots[0].name}")
        else:
            self.snapshot_metric.set_subtitle("暂无备份")
        self.refresh_restore_detail()

    def refresh_schedule_status(self) -> None:
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", SCHEDULE_TASK_NAME, "/FO", "LIST"],
            capture_output=True,
            text=True,
        )
        created = result.returncode == 0
        self.schedule_status.setText("状态：已创建" if created else "状态：未创建")
        self.schedule_metric.set_value("已启用" if created else "未启用")
        self.schedule_metric.set_subtitle(f"每天 {self.schedule_time_value}")
        self.schedule_switch.blockSignals(True)
        self.schedule_switch.setChecked(created)
        self.schedule_switch.blockSignals(False)

    def create_backup(self) -> None:
        selected = self._selected_items()
        if not selected:
            self._warn("请至少选择一个存在的备份内容。")
            return
        warning = build_sensitive_backup_warning(selected)
        message = f"将备份 {len(selected)} 个项目到：\n{self.backup_root}\n\n是否开始？"
        if warning:
            message = f"{warning}\n\n{message}"
        ok = QMessageBox.question(
            self,
            APP_TITLE,
            message,
        )
        if ok != QMessageBox.StandardButton.Yes:
            return

        def job(log):
            log("开始备份...")
            result = self.service.create_snapshot(selected)
            log(f"备份完成：{result.path}")
            if result.skipped_items:
                log(f"跳过项目：{', '.join(result.skipped_items)}")

        self._run_worker(job, refresh=True, success_text="备份完成")

    def create_schedule(self) -> None:
        selected_names = [item.name for item in self._selected_items()]
        schedule_time = self.schedule_time.text().strip()
        if not selected_names:
            self._warn("请至少选择一个存在的备份内容。")
            return
        if not is_valid_time(schedule_time):
            self._warn("请输入 HH:mm 格式的时间，例如 22:30。")
            return
        self.schedule_time_value = schedule_time
        self.persist_selected_items()

        def job(log):
            config_path = self.user_settings_path.parent / "schedule.json"
            self.service.write_schedule_config(config_path, self.backup_root, selected_names, self.custom_items_config)
            launcher = Path(__file__).with_name("定时备份入口.bat")
            subprocess.run(
                ["schtasks", "/Create", "/TN", SCHEDULE_TASK_NAME, "/SC", "DAILY", "/ST", schedule_time, "/TR", str(launcher), "/F"],
                check=True,
                capture_output=True,
                text=True,
            )
            log(f"定时备份任务已创建：每天 {schedule_time}")

        self._run_worker(job, refresh=True, success_text="定时备份已更新")

    def delete_schedule(self) -> None:
        def job(log):
            result = subprocess.run(["schtasks", "/Delete", "/TN", SCHEDULE_TASK_NAME, "/F"], capture_output=True, text=True)
            log("定时备份任务已删除。" if result.returncode == 0 else "没有找到可删除的定时备份任务。")

        self._run_worker(job, refresh=True, success_text="定时备份状态已刷新")

    def restore_selected(self) -> None:
        row = self.restore_snapshot_list.currentRow()
        if row < 0 or row >= len(self.snapshots):
            self._warn("请先选择一个备份快照。")
            return
        selected_names = [item.name for item in self._selected_items()]
        if not selected_names:
            self._warn("请至少选择一个要恢复的项目。")
            return
        snapshot = self.snapshots[row]
        detail = self.service.read_snapshot_detail(snapshot, selected_names)
        sensitive_names = [
            item.name
            for item in detail.items
            if item.name in selected_names and item.sensitive_plaintext
        ]
        detail_lines = []
        if detail.error:
            detail_lines.append(f"快照详情：{detail.error}")
        if detail.missing_selected_names:
            detail_lines.append(f"快照缺少项目：{', '.join(detail.missing_selected_names)}")
        if sensitive_names:
            detail_lines.append(f"敏感明文项目：{', '.join(sensitive_names)}")
        detail_text = "\n".join(detail_lines)
        if detail_text:
            detail_text += "\n\n"
        ok = QMessageBox.question(
            self,
            APP_TITLE,
            f"将从快照恢复选中项目。\n默认项目恢复到：{self.home}\n自定义项目恢复到快照记录的原始路径。\n\n快照：{snapshot.name}\n项目：{', '.join(selected_names)}\n\n{detail_text}恢复前会先备份当前目标目录。是否继续？",
        )
        if ok != QMessageBox.StandardButton.Yes:
            return

        def job(log):
            result = self.service.restore_snapshot(snapshot, self.home, selected_names)
            log(f"恢复完成：{', '.join(result.restored_items)}")
            if result.skipped_items:
                log(f"跳过项目：{', '.join(result.skipped_items)}")
            log(f"恢复前备份：{result.pre_restore_backup_dir}")

        self._run_worker(job, refresh=True, success_text="恢复完成")

    def migrate_selected_link(self) -> None:
        selected_items = self._selected_link_items()
        if not selected_items:
            self._warn("请选择要迁移的目录。")
            return
        for item in selected_items:
            status = self.service.get_link_migration_status(item)
            if not status.can_migrate:
                self._warn(f"{item.name} 当前状态为 {status.label}，不能迁移。{status.problem}")
                return
        ok = QMessageBox.question(
            self,
            APP_TITLE,
            f"这是高级操作，会移动原目录并创建 Junction。\n\n目录：{', '.join(item.name for item in selected_items)}\n\n是否继续？",
        )
        if ok != QMessageBox.StandardButton.Yes:
            return

        def job(log):
            for item in selected_items:
                result = self.service.prepare_link_migration(item, self.service.default_link_store_root())
                self.service.create_junction(result.link_path, result.store_path)
                log(f"迁移完成：{result.link_path} -> {result.store_path}")
                log(f"迁移前备份：{result.pre_migration_backup_dir}")

        self._run_worker(job, refresh=True, success_text="Junction 迁移完成")

    def cancel_selected_link_migration(self, checked: bool = False, confirm: bool = True) -> None:
        selected_items = self._selected_link_items()
        if not selected_items:
            self._warn("请选择要取消迁移的目录。")
            return
        for item in selected_items:
            status = self.service.get_link_migration_status(item)
            if not status.can_cancel:
                self._warn(f"{item.name} 当前状态为 {status.label}，不能取消迁移。{status.problem}")
                return
        if confirm:
            ok = QMessageBox.question(
                self,
                APP_TITLE,
                f"将取消迁移，把 D 盘真实目录移动回原位置。\n\n目录：{', '.join(item.name for item in selected_items)}\n\n是否继续？",
            )
            if ok != QMessageBox.StandardButton.Yes:
                return

        def job(log):
            for item in selected_items:
                result = self.service.cancel_link_migration(item)
                log(f"取消迁移完成：{result.link_path}")
                log(f"取消迁移前备份：{result.pre_cancel_backup_dir}")

        if confirm:
            self._run_worker(job, refresh=True, success_text="取消迁移完成")
        else:
            job(lambda message: None)

    def open_backup_dir(self) -> None:
        self.backup_root.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer", str(self.backup_root)])

    def open_current_directory(self, path: Path) -> None:
        target = Path(path)
        directory = target if target.is_dir() else target.parent
        if not directory.exists():
            self._warn(f"目录不存在：{directory}")
            return
        subprocess.Popen(["explorer", str(directory)])

    def open_task_scheduler_command(self) -> list[str]:
        return [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            "Start-Process mmc.exe -ArgumentList 'taskschd.msc' -Verb RunAs",
        ]

    def open_task_scheduler(self) -> None:
        subprocess.Popen(self.open_task_scheduler_command())

    def open_environment_variables_command(self) -> list[str]:
        return [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            "Start-Process rundll32.exe -ArgumentList 'sysdm.cpl,EditEnvironmentVariables' -Verb RunAs",
        ]

    def open_environment_variables(self) -> None:
        subprocess.Popen(self.open_environment_variables_command())

    def backup_environment_path(
        self,
        name: str | None = None,
        user_path: str | None = None,
        system_path: str | None = None,
        process_path: str | None = None,
    ):
        result = self.service.backup_environment_path(
            name=name,
            user_path=user_path if user_path is not None else os.environ.get("USER_PATH", ""),
            system_path=system_path if system_path is not None else os.environ.get("SYSTEM_PATH", ""),
            process_path=process_path if process_path is not None else os.environ.get("PATH", ""),
        )
        self.append_log(f"环境变量 Path 已备份：{result.path}")
        return result

    def backup_environment_path_async(self) -> None:
        def job(log):
            result = self.service.backup_environment_path()
            log(f"环境变量 Path 已备份：{result.path}")

        self._run_worker(job, refresh=False, success_text="Path 已备份")

    def choose_backup_root(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择备份保存目录", str(self.backup_root))
        if path:
            self.backup_root_edit.setText(path)
            self.save_backup_root_from_input()

    def save_backup_root_from_input(self) -> None:
        path_text = self.backup_root_edit.text().strip()
        if not path_text:
            self._warn("备份目录不能为空。")
            return
        schedule_time = self.schedule_time.text().strip() if hasattr(self, "schedule_time") else self.schedule_time_value
        if schedule_time and not is_valid_time(schedule_time):
            if hasattr(self, "schedule_time"):
                self.schedule_time.setText(self.schedule_time_value)
            self._warn("请输入 HH:mm 格式的时间，例如 22:30。")
            return
        self.backup_root = Path(path_text)
        self.service = BackupService(self.backup_root)
        self.last_link_store_path = self.service.default_link_store_root()
        self.schedule_time_value = schedule_time or self.schedule_time_value
        if hasattr(self, "backup_root_edit"):
            self.backup_root_edit.setText(str(self.backup_root))
        self.normalize_internal_backup_directories()
        self.persist_selected_items()
        self.schedule_metric.set_subtitle(f"每天 {self.schedule_time_value}")
        self.refresh_snapshots()
        self.refresh_link_hint()
        self._success("配置已保存")

    def save_schedule_time_from_input(self) -> None:
        schedule_time = self.schedule_time.text().strip()
        if not schedule_time:
            return
        if not is_valid_time(schedule_time):
            self._warn("请输入 HH:mm 格式的时间，例如 22:30。")
            return
        self.schedule_time_value = schedule_time
        self.persist_selected_items()
        self.schedule_metric.set_subtitle(f"每天 {self.schedule_time_value}")

    def refresh_link_hint(self) -> None:
        if not hasattr(self, "link_hint"):
            return
        selected_items = self._selected_link_items()
        self._update_link_action_buttons(selected_items)
        if not selected_items:
            self.link_hint.setText("请选择要迁移的目录。")
            return
        migrated = []
        migratable = []
        broken = []
        for item in selected_items:
            status = self.service.get_link_migration_status(item)
            if status.state == "migrated":
                migrated.append(item.name)
            elif status.state == "normal":
                migratable.append(item.name)
            else:
                broken.append(f"{item.name} 需要手动检查：{status.problem}")
        if broken:
            self.link_hint.setText("；".join(broken))
            return
        if migrated and migratable:
            self.link_hint.setText(f"已选择 {len(selected_items)} 个目录；已迁移的可取消迁移，未迁移的可迁移。")
            return
        if migrated:
            self.link_hint.setText(f"{', '.join(migrated)} 已迁移，可取消迁移。")
            return
        self.link_hint.setText(f"已选择 {len(migratable)} 个目录，将移动到迁移后的真实目录并在原位置创建 Junction。")

    def _update_link_action_buttons(self, selected_items: list[BackupItem]) -> None:
        if not hasattr(self, "migrate_button") or not hasattr(self, "cancel_migration_button"):
            return
        statuses = [self.service.get_link_migration_status(item) for item in selected_items]
        self.migrate_button.setEnabled(bool(statuses) and all(status.can_migrate for status in statuses))
        self.cancel_migration_button.setEnabled(bool(statuses) and all(status.can_cancel for status in statuses))

    def _link_status_extra_details(self, status: LinkMigrationStatus) -> list[str]:
        if status.state == "migrated":
            return [f"D盘真实目录 {status.store_path}"]
        if status.state == "broken":
            return [status.problem]
        return []

    def _link_status_tooltip(self, status: LinkMigrationStatus) -> str:
        lines = [status.label, status.detail]
        if status.problem:
            lines.append(status.problem)
        return "\n".join(lines)

    def add_custom_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择要备份的文件夹", str(self.home))
        if path:
            self.add_custom_path(Path(path))

    def add_custom_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择要备份的文件", str(self.home))
        if path:
            self.add_custom_path(Path(path))

    def add_custom_path(self, path: Path, sensitive: bool = True) -> None:
        path = Path(path)
        if any(Path(item["path"]) == path for item in self.custom_items_config):
            self._info("这个自定义项目已经存在。")
            return
        self.custom_items_config.append({"name": path.name, "path": str(path), "sensitive": sensitive})
        self._reload_items_from_settings(select_new_paths={path})
        self.persist_selected_items()
        self.refresh_link_items()
        self.refresh_items()

    def remove_selected_custom_items(self) -> None:
        selected_custom = [item for item in self.items if item.name in self.selected_names and item.name.startswith("自定义/")]
        if not selected_custom:
            self._warn("请先勾选要删除的自定义项目。")
            return
        remove_paths = {str(item.restore_target or item.source) for item in selected_custom}
        self.custom_items_config = [item for item in self.custom_items_config if str(Path(item["path"])) not in remove_paths]
        for item in selected_custom:
            self.selected_names.discard(item.name)
        self._reload_items_from_settings()
        self.persist_selected_items()
        self.refresh_link_items()
        self.refresh_items()

    def refresh_link_items(self) -> None:
        if not hasattr(self, "link_layout"):
            return
        selected_names = set(self.link_selected_names)
        for card in self.link_cards:
            card.setParent(None)
        self.link_cards = []
        scanned_by_name = {entry.item.name: entry for entry in self.scanned_items}
        self.link_selected_names = {name for name in self.link_selected_names if any(item.name == name for item in self._sorted_linkable_items())}
        for item in self._sorted_linkable_items():
            scanned = scanned_by_name.get(item.name)
            if scanned is None:
                scanned = ScannedItem(item, item.source.exists(), self.service._path_size(item.source) if item.source.exists() else 0, self.service._last_write_time(item.source) if item.source.exists() else None)
            status = self.service.get_link_migration_status(item)
            extra_details = self._link_status_extra_details(status)
            tooltip = self._link_status_tooltip(status)
            card = BackupItemCard(scanned, item.name in selected_names, badge=status.label, extra_details=extra_details, tooltip=tooltip)
            self._apply_link_card_status_style(card, status)
            card.toggled.connect(self._set_link_item_selected)
            card.open_directory_requested.connect(self.open_current_directory)
            self.link_layout.insertWidget(self.link_layout.count() - 1, card)
            self.link_cards.append(card)
        self.refresh_link_hint()

    def _apply_link_card_status_style(self, card: BackupItemCard, status: LinkMigrationStatus) -> None:
        migrated = status.state == "migrated"
        card.setProperty("migrated", migrated)
        card.setObjectName("MigratedLinkCard" if migrated else "")
        card.style().unpolish(card)
        card.style().polish(card)

    def set_all_link_items(self, checked: bool) -> None:
        if not hasattr(self, "link_cards"):
            return
        self.link_selected_names = {item.name for item in self._sorted_linkable_items()} if checked else set()
        for card in self.link_cards:
            card.checkbox.blockSignals(True)
            card.checkbox.setChecked(card.item.name in self.link_selected_names)
            card.checkbox.blockSignals(False)
        self.refresh_link_hint()

    def refresh_restore_detail(self) -> None:
        if not hasattr(self, "restore_snapshot_detail"):
            return
        row = self.restore_snapshot_list.currentRow()
        selected_names = [item.name for item in self._selected_items()]
        if row < 0 or row >= len(self.snapshots):
            self.restore_snapshot_detail.setPlainText("请选择一个备份快照。")
            return
        snapshot = self.snapshots[row]
        detail = self.service.read_snapshot_detail(snapshot, selected_names)
        lines = [f"快照：{snapshot.name}"]
        if detail.created_at:
            lines.append(f"创建时间：{detail.created_at}")
        if detail.error:
            lines.append(f"状态：{detail.error}")
        lines.append("")
        if detail.items:
            lines.append("包含项目：")
            for item in detail.items:
                target = f" -> {item.restore_target}" if item.restore_target else ""
                lines.append(f"- {item.name} <- {item.source}{target}")
        else:
            lines.append("包含项目：未读取到项目明细")
        lines.append("")
        available = ", ".join(detail.available_selected_names) if detail.available_selected_names else "无"
        missing = ", ".join(detail.missing_selected_names) if detail.missing_selected_names else "无"
        lines.append(f"可恢复：{available}")
        lines.append(f"快照缺少：{missing}")
        self.restore_snapshot_detail.setPlainText("\n".join(lines))

    def set_all_items(self, checked: bool) -> None:
        self.selected_names = set(self._selectable_item_names()) if checked else set()
        self.persist_selected_items()
        if self.scanned_items:
            self.apply_scanned_items(self.scanned_items)
        else:
            self.refresh_items()

    def _schedule_switch_changed(self, checked: bool) -> None:
        if checked:
            self.create_schedule()
        else:
            self.delete_schedule()

    def _set_item_selected(self, name: str, checked: bool) -> None:
        if checked:
            self.selected_names.add(name)
        else:
            self.selected_names.discard(name)
        self.persist_selected_items()
        self._refresh_item_status_widgets()
        self.refresh_restore_detail()

    def _set_link_item_selected(self, name: str, checked: bool) -> None:
        if checked:
            self.link_selected_names.add(name)
        else:
            self.link_selected_names.discard(name)
        self.refresh_link_hint()

    def _selected_items(self) -> list[BackupItem]:
        existing_names = self._existing_item_names()
        return [item for item in self.items if item.name in self.selected_names and item.name in existing_names]

    def persist_selected_items(self) -> None:
        existing_names = self._existing_item_names()
        selected_names = [item.name for item in self.items if item.name in self.selected_names and item.name in existing_names]
        custom_payload = self._custom_settings_payload()
        schedule_time = self.schedule_time.text().strip() if hasattr(self, "schedule_time") else self.schedule_time_value
        if not is_valid_time(schedule_time):
            schedule_time = self.schedule_time_value
            if hasattr(self, "schedule_time"):
                self.schedule_time.setText(schedule_time)
        write_user_settings(
            self.user_settings_path,
            selected_names,
            custom_payload,
            backup_root=self.backup_root,
            schedule_time=schedule_time,
        )
        self.service.write_schedule_config(
            self.user_settings_path.parent / "schedule.json",
            self.backup_root,
            selected_names,
            custom_payload,
        )

    def _existing_item_names(self) -> set[str]:
        if self.scanned_items:
            return {entry.item.name for entry in self.scanned_items if entry.exists}
        return {item.name for item in self.items if item.source.exists()}

    def _selectable_item_names(self) -> set[str]:
        return self._existing_item_names() | {item.name for item in self.items if item.name.startswith("自定义/")}

    def _reload_items_from_settings(self, select_new_paths: set[Path] | None = None) -> None:
        self.items = build_backup_items(self.home, self.custom_items_config)
        self.scanned_items = []
        if select_new_paths:
            normalized = {Path(path) for path in select_new_paths}
            for item in self.items:
                if Path(item.restore_target or item.source) in normalized:
                    self.selected_names.add(item.name)

    def _linkable_items(self) -> list[BackupItem]:
        return [item for item in self.items if not item.name.startswith("自定义/")]

    def _sorted_linkable_items(self) -> list[BackupItem]:
        if self.scanned_items:
            mode = self.link_sort_combo.currentText() if hasattr(self, "link_sort_combo") else "已迁移"
            if mode == "已迁移":
                status_rank = {"migrated": 0, "broken": 1, "normal": 2}
                scanned_entries = [
                    entry for entry in self.scanned_items if entry.exists and not entry.item.name.startswith("自定义/")
                ]
                return [
                    entry.item
                    for entry in sorted(
                        scanned_entries,
                        key=lambda entry: (
                            status_rank.get(self.service.get_link_migration_status(entry.item).state, 3),
                            -(entry.last_write_time.timestamp() if entry.last_write_time else 0),
                            entry.item.name.lower(),
                        ),
                    )
                ]
            return [
                entry.item
                for entry in self._sorted_scanned_items(mode)
                if entry.exists and not entry.item.name.startswith("自定义/")
            ]
        return sorted(self._linkable_items(), key=lambda item: item.name.lower())

    def _selected_link_items(self) -> list[BackupItem]:
        if not hasattr(self, "link_cards"):
            return []
        return [item for item in self._sorted_linkable_items() if item.name in self.link_selected_names]

    def _custom_settings_payload(self) -> list[dict]:
        payload = []
        for item in self.items:
            if not item.name.startswith("自定义/"):
                continue
            payload.append(
                {
                    "name": item.name.split("/", 1)[1],
                    "path": str(item.restore_target or item.source),
                    "sensitive": item.sensitive,
                }
            )
        return payload

    def _run_worker(self, func, refresh: bool, success_text: str) -> None:
        if self.worker and self.worker.isRunning():
            self._info("当前已有任务在运行。")
            return
        self.worker = Worker(func)
        self.worker.log.connect(self.append_log)
        self.worker.failed.connect(self._show_error)
        self.worker.finished_ok.connect(lambda: self._success(success_text))
        if refresh:
            self.worker.finished_ok.connect(self.refresh_all)
        self.worker.start()

    def append_log(self, message: str) -> None:
        self.log.append(message)

    def _warn(self, text: str) -> None:
        self._show_info_bar(InfoBar.warning, "需要处理", text, 2600)

    def _info(self, text: str) -> None:
        self._show_info_bar(InfoBar.info, "提示", text, 2200)

    def _success(self, text: str) -> None:
        self._show_info_bar(InfoBar.success, "完成", text, 2600)

    def _show_error(self, text: str) -> None:
        self.append_log(text)
        self._show_info_bar(InfoBar.error, "任务失败", text.splitlines()[0], 5000)

    def _show_info_bar(self, factory, title: str, content: str, duration: int) -> None:
        self._close_active_info_bar()
        self._cleanup_orphan_pythonw_info_windows()
        bar = factory(title=title, content=content, parent=self, position=InfoBarPosition.TOP_RIGHT, duration=duration)
        self._active_info_bar = bar
        bar.closedSignal.connect(lambda bar=bar: self._forget_info_bar(bar))
        bar.destroyed.connect(lambda *_: self._cleanup_orphan_pythonw_info_windows())
        QTimer.singleShot(duration + 500, self._cleanup_orphan_pythonw_info_windows)

    def _close_active_info_bar(self) -> None:
        bar = self._active_info_bar
        if bar is None:
            return
        self._active_info_bar = None
        try:
            bar.close()
        except RuntimeError:
            pass

    def _forget_info_bar(self, bar) -> None:
        if self._active_info_bar is bar:
            self._active_info_bar = None

    def _cleanup_orphan_pythonw_info_windows(self) -> None:
        if os.name != "nt":
            return
        try:
            windows = self._orphan_pythonw_info_windows()
        except Exception:
            return
        for hwnd in windows:
            try:
                windll.user32.ShowWindow(HWND(hwnd), 0)
            except Exception:
                continue

    def _orphan_pythonw_info_windows(self) -> list[int]:
        if os.name != "nt":
            return []
        current_pid = os.getpid()
        hwnds: list[int] = []

        def callback(hwnd, _lparam):
            pid = DWORD()
            windll.user32.GetWindowThreadProcessId(HWND(hwnd), byref(pid))
            if pid.value != current_pid or not windll.user32.IsWindowVisible(HWND(hwnd)):
                return True
            title_length = windll.user32.GetWindowTextLengthW(HWND(hwnd))
            title_buffer = create_unicode_buffer(title_length + 1)
            windll.user32.GetWindowTextW(HWND(hwnd), title_buffer, title_length + 1)
            if title_buffer.value != "pythonw":
                return True
            class_buffer = create_unicode_buffer(256)
            windll.user32.GetClassNameW(HWND(hwnd), class_buffer, 256)
            if "QWindowIcon" not in class_buffer.value:
                return True
            rect = NativeRect()
            windll.user32.GetWindowRect(HWND(hwnd), byref(rect))
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            if width <= 360 and height <= 120:
                hwnds.append(int(hwnd))
            return True

        callback_proc = EnumWindowsCallback(callback)
        windll.user32.EnumWindows(callback_proc, 0)
        return hwnds

    def _wait_for_thread(self, thread: QThread | None) -> None:
        if thread and thread.isRunning():
            thread.wait()


def main() -> int:
    app = QApplication(sys.argv)
    apply_default_ui_theme()
    app.setStyleSheet(STYLE)
    window = FluentBackupApp()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
