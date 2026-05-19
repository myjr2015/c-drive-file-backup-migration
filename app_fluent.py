from __future__ import annotations

import subprocess
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
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
    InfoBar,
    InfoBarPosition,
    LineEdit,
    ListWidget,
    NavigationInterface,
    NavigationItemPosition,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    ScrollArea,
    StrongBodyLabel,
    SwitchButton,
    TextEdit,
    Theme,
    setTheme,
)

from backup_core import BackupItem, BackupService, ScannedItem, load_user_settings, write_user_settings
from project_config import (
    APP_TITLE,
    SCHEDULE_TASK_NAME,
    build_sensitive_backup_warning,
    default_items,
    get_backup_root,
    load_config,
)
from ui_helpers import format_size, is_valid_time


STYLE = """
QWidget {
    font-family: "Microsoft YaHei UI", "Segoe UI";
    font-size: 13px;
}
QWidget#Page {
    background: #f7f9fc;
}
QFrame#HeaderBand {
    background: #ffffff;
    border: 1px solid #e6eaf0;
    border-radius: 8px;
}
QLabel#PageTitle {
    font-size: 22px;
    font-weight: 700;
    color: #172033;
}
QLabel#Muted {
    color: #677386;
}
QLabel#MetricValue {
    font-size: 24px;
    font-weight: 700;
    color: #172033;
}
QLabel#MetricTitle {
    color: #677386;
}
CardWidget {
    border-radius: 8px;
}
TextEdit {
    font-family: "Cascadia Mono", Consolas, "Microsoft YaHei UI";
    font-size: 12px;
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

    def __init__(self, scanned, checked: bool) -> None:
        super().__init__()
        self.item = scanned.item
        self.checkbox = CheckBox()
        self.checkbox.setChecked(checked and scanned.exists)
        self.checkbox.setEnabled(scanned.exists)

        layout = QGridLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(2)
        layout.addWidget(self.checkbox, 0, 0, 2, 1)

        name = StrongBodyLabel(scanned.item.name)
        layout.addWidget(name, 0, 1)

        status = "存在" if scanned.exists else "缺失"
        detail = f"{status} · {format_size(scanned.size_bytes)}"
        if scanned.last_write_time:
            detail += f" · {scanned.last_write_time.strftime('%Y-%m-%d %H:%M')}"
        meta = CaptionLabel(detail)
        meta.setObjectName("Muted")
        layout.addWidget(meta, 0, 2, alignment=Qt.AlignmentFlag.AlignRight)

        path = CaptionLabel(str(scanned.item.source))
        path.setObjectName("Muted")
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(path, 1, 1, 1, 2)
        layout.setColumnStretch(1, 1)

        self.checkbox.toggled.connect(lambda value: self.toggled.emit(self.item.name, value))


class MetricCard(CardWidget):
    def __init__(self, title: str, value: str, subtitle: str = "") -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

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


class FluentBackupApp(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(980, 620)
        self.setMinimumSize(860, 540)

        config = load_config()
        self.home = Path.home()
        self.backup_root = get_backup_root(config)
        self.service = BackupService(self.backup_root)
        self.items = default_items(self.home)
        self.user_settings_path = Path(__file__).with_name("data") / "user-settings.json"
        user_settings = load_user_settings(self.user_settings_path)
        saved_selected = set(user_settings.get("selected_items", []))
        existing_names = {item.name for item in self.items if item.source.exists()}
        self.selected_names: set[str] = (saved_selected & existing_names) if user_settings["settings_exists"] else existing_names
        self.item_cards: list[BackupItemCard] = []
        self.snapshots: list[Path] = []
        self.worker: Worker | None = None
        self.scan_worker: ScanWorker | None = None
        self.scanned_items: list[ScannedItem] = []
        self.last_link_store_path = self.backup_root / "link-store"

        self._build_ui()
        self.refresh_all()

    def closeEvent(self, event) -> None:
        self._wait_for_thread(self.scan_worker)
        self._wait_for_thread(self.worker)
        super().closeEvent(event)

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.navigation = NavigationInterface(self, showMenuButton=False)
        self.navigation.setFixedWidth(168)
        root.addWidget(self.navigation)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        self.dashboard_page = self._build_dashboard_page()
        self.items_page = self._build_items_page()
        self.restore_page = self._build_restore_page()
        self.link_page = self._build_link_page()
        self.log_page = self._build_log_page()

        for page in [self.dashboard_page, self.items_page, self.restore_page, self.link_page, self.log_page]:
            self.stack.addWidget(page)

        self.navigation.addItem(
            routeKey="dashboard",
            icon=FluentIcon.HOME,
            text="总览",
            onClick=lambda: self.stack.setCurrentWidget(self.dashboard_page),
        )
        self.navigation.addItem(
            routeKey="items",
            icon=FluentIcon.CHECKBOX,
            text="备份项目",
            onClick=lambda: self.stack.setCurrentWidget(self.items_page),
        )
        self.navigation.addItem(
            routeKey="restore",
            icon=FluentIcon.SYNC,
            text="恢复",
            onClick=lambda: self.stack.setCurrentWidget(self.restore_page),
        )
        self.navigation.addItem(
            routeKey="link",
            icon=FluentIcon.LINK,
            text="Junction",
            onClick=lambda: self.stack.setCurrentWidget(self.link_page),
        )
        self.navigation.addItem(
            routeKey="log",
            icon=FluentIcon.DOCUMENT,
            text="日志",
            onClick=lambda: self.stack.setCurrentWidget(self.log_page),
            position=NavigationItemPosition.BOTTOM,
        )

    def _base_page(self) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        page.setObjectName("Page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        return page, layout

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("HeaderBand")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel(APP_TITLE)
        title.setObjectName("PageTitle")
        title_box.addWidget(title)
        path = CaptionLabel(str(self.backup_root))
        path.setObjectName("Muted")
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        title_box.addWidget(path)
        layout.addLayout(title_box, 1)

        open_dir = PushButton("打开目录")
        open_dir.setIcon(FluentIcon.FOLDER)
        open_dir.clicked.connect(self.open_backup_dir)
        refresh = PushButton("刷新")
        refresh.setIcon(FluentIcon.SYNC)
        refresh.clicked.connect(self.refresh_all)
        backup = PrimaryPushButton("立即备份")
        backup.setIcon(FluentIcon.SAVE)
        backup.clicked.connect(self.create_backup)
        layout.addWidget(open_dir)
        layout.addWidget(refresh)
        layout.addWidget(backup)
        return header

    def _build_dashboard_page(self) -> QWidget:
        page, layout = self._base_page()
        layout.addWidget(self._build_header())

        hero = QHBoxLayout()
        hero.setSpacing(12)
        layout.addLayout(hero)

        self.exists_metric = MetricCard("可备份项目", "0", "当前用户目录")
        self.selected_metric = MetricCard("已选择", "0", "用于立即备份和恢复")
        self.snapshot_metric = MetricCard("快照数", "0", "最近备份记录")
        self.schedule_metric = MetricCard("定时任务", "读取中", "每天 22:30")
        hero.addWidget(self.exists_metric)
        hero.addWidget(self.selected_metric)
        hero.addWidget(self.snapshot_metric)
        hero.addWidget(self.schedule_metric)

        body = QHBoxLayout()
        body.setSpacing(12)
        layout.addLayout(body, 1)

        left = QVBoxLayout()
        left.setSpacing(12)
        body.addLayout(left, 3)
        left.addWidget(self._build_next_action_card())
        left.addWidget(self._build_schedule_card())

        right = QVBoxLayout()
        right.setSpacing(12)
        body.addLayout(right, 2)
        right.addWidget(self._build_snapshot_card(), 1)
        right.addWidget(self._build_log_preview_card())
        return page

    def _build_items_page(self) -> QWidget:
        page, layout = self._base_page()
        layout.addWidget(self._section_title("备份项目", "选择要保护的用户目录、AI 会话和开发配置。"))

        item_card = CardWidget()
        item_layout = QVBoxLayout(item_card)
        item_layout.setContentsMargins(14, 12, 14, 14)
        item_layout.setSpacing(9)

        item_bar = QHBoxLayout()
        item_bar.addWidget(StrongBodyLabel("项目列表"))
        item_bar.addStretch()
        select_all = PushButton("全选")
        select_all.clicked.connect(lambda: self.set_all_items(True))
        select_none = PushButton("全不选")
        select_none.clicked.connect(lambda: self.set_all_items(False))
        backup = PrimaryPushButton("立即备份")
        backup.setIcon(FluentIcon.SAVE)
        backup.clicked.connect(self.create_backup)
        item_bar.addWidget(select_all)
        item_bar.addWidget(select_none)
        item_bar.addWidget(backup)
        item_layout.addLayout(item_bar)

        self.item_container = QWidget()
        self.item_layout = QVBoxLayout(self.item_container)
        self.item_layout.setContentsMargins(0, 0, 0, 0)
        self.item_layout.setSpacing(8)
        self.item_layout.addStretch()

        item_scroll = ScrollArea()
        item_scroll.setWidgetResizable(True)
        item_scroll.setFrameShape(QFrame.Shape.NoFrame)
        item_scroll.setWidget(self.item_container)
        item_layout.addWidget(item_scroll, 1)
        layout.addWidget(item_card, 1)
        return page

    def _build_next_action_card(self) -> CardWidget:
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        layout.addWidget(StrongBodyLabel("当前保护状态"))
        self.protection_summary = BodyLabel("读取中")
        layout.addWidget(self.protection_summary)
        self.protection_bar = ProgressBar()
        self.protection_bar.setRange(0, 100)
        layout.addWidget(self.protection_bar)
        row = QHBoxLayout()
        backup = PrimaryPushButton("立即备份")
        backup.setIcon(FluentIcon.SAVE)
        backup.clicked.connect(self.create_backup)
        items = PushButton("管理项目")
        items.setIcon(FluentIcon.CHECKBOX)
        items.clicked.connect(lambda: self.stack.setCurrentWidget(self.items_page))
        restore = PushButton("恢复快照")
        restore.setIcon(FluentIcon.SYNC)
        restore.clicked.connect(lambda: self.stack.setCurrentWidget(self.restore_page))
        row.addWidget(backup)
        row.addWidget(items)
        row.addWidget(restore)
        row.addStretch()
        layout.addLayout(row)
        return card

    def _build_log_preview_card(self) -> CardWidget:
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(9)
        bar = QHBoxLayout()
        bar.addWidget(StrongBodyLabel("最近日志"))
        bar.addStretch()
        open_log = PushButton("查看全部")
        open_log.clicked.connect(lambda: self.stack.setCurrentWidget(self.log_page))
        bar.addWidget(open_log)
        layout.addLayout(bar)
        self.inline_log = TextEdit()
        self.inline_log.setReadOnly(True)
        self.inline_log.setFixedHeight(118)
        layout.addWidget(self.inline_log)
        return card

    def _build_schedule_card(self) -> CardWidget:
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(9)

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
        row.addWidget(BodyLabel("每天"))
        self.schedule_time = LineEdit()
        self.schedule_time.setText("22:30")
        self.schedule_time.setFixedWidth(84)
        row.addWidget(self.schedule_time)
        create = PrimaryPushButton("创建/更新")
        create.clicked.connect(self.create_schedule)
        delete = PushButton("删除")
        delete.clicked.connect(self.delete_schedule)
        row.addWidget(create)
        row.addWidget(delete)
        layout.addLayout(row)

        self.schedule_status = CaptionLabel("状态：读取中")
        self.schedule_status.setObjectName("Muted")
        layout.addWidget(self.schedule_status)
        return card

    def _build_snapshot_card(self) -> CardWidget:
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(9)
        layout.addWidget(StrongBodyLabel("最近快照"))
        self.snapshot_list = ListWidget()
        layout.addWidget(self.snapshot_list, 1)
        return card

    def _build_restore_page(self) -> QWidget:
        page, layout = self._base_page()
        layout.addWidget(self._section_title("恢复快照", "恢复前会自动把当前目标目录备份到 restore-backups。"))

        body = QHBoxLayout()
        body.setSpacing(12)
        layout.addLayout(body, 1)

        list_card = CardWidget()
        list_layout = QVBoxLayout(list_card)
        list_layout.setContentsMargins(14, 12, 14, 14)
        list_layout.addWidget(StrongBodyLabel("快照列表"))
        self.restore_snapshot_list = ListWidget()
        self.restore_snapshot_list.currentRowChanged.connect(lambda _: self.refresh_restore_detail())
        list_layout.addWidget(self.restore_snapshot_list, 1)
        body.addWidget(list_card, 2)

        action_card = CardWidget()
        action_layout = QVBoxLayout(action_card)
        action_layout.setContentsMargins(14, 12, 14, 14)
        action_layout.setSpacing(10)
        action_layout.addWidget(StrongBodyLabel("恢复操作"))
        self.restore_selected_summary = BodyLabel("读取中")
        action_layout.addWidget(self.restore_selected_summary)
        action_layout.addWidget(CaptionLabel("目标路径为当前 Windows 用户目录，覆盖前会先生成恢复前备份。"))
        action_layout.addWidget(StrongBodyLabel("快照内容"))
        self.restore_snapshot_detail = TextEdit()
        self.restore_snapshot_detail.setReadOnly(True)
        self.restore_snapshot_detail.setMinimumHeight(170)
        action_layout.addWidget(self.restore_snapshot_detail, 1)
        action_layout.addStretch()
        restore = PrimaryPushButton("恢复选中快照")
        restore.setIcon(FluentIcon.SYNC)
        restore.clicked.connect(self.restore_selected)
        action_layout.addWidget(restore)
        body.addWidget(action_card, 1)
        return page

    def _build_link_page(self) -> QWidget:
        page, layout = self._base_page()
        layout.addWidget(self._section_title("Junction 链接迁移", "高级操作：先备份，再移动到 D 盘 link-store，最后创建 Junction。"))

        card = CardWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 14)
        card_layout.setSpacing(10)
        card_layout.addWidget(StrongBodyLabel("选择迁移项目"))

        row = QHBoxLayout()
        self.link_combo = ComboBox()
        self.link_combo.addItems([item.name for item in self.items])
        self.link_combo.currentTextChanged.connect(self.refresh_link_hint)
        row.addWidget(self.link_combo, 1)
        migrate = PrimaryPushButton("迁移到 D 盘并创建 Junction")
        migrate.setIcon(FluentIcon.LINK)
        migrate.clicked.connect(self.migrate_selected_link)
        row.addWidget(migrate)
        card_layout.addLayout(row)
        self.link_hint = CaptionLabel("")
        card_layout.addWidget(self.link_hint)
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
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(3)
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

    def refresh_items(self) -> None:
        if self.scan_worker and self.scan_worker.isRunning():
            return
        self.protection_summary.setText("正在扫描备份项目...")
        self.scan_worker = ScanWorker(self.service, self.items)
        self.scan_worker.finished_scan.connect(self.apply_scanned_items)
        self.scan_worker.failed.connect(self._show_error)
        self.scan_worker.start()

    def apply_scanned_items(self, scanned: list[ScannedItem]) -> None:
        self.scanned_items = scanned
        for card in self.item_cards:
            card.setParent(None)
        self.item_cards = []

        exists_count = 0
        for entry in scanned:
            if entry.exists:
                exists_count += 1
            card = BackupItemCard(entry, entry.item.name in self.selected_names)
            card.toggled.connect(self._set_item_selected)
            self.item_layout.insertWidget(self.item_layout.count() - 1, card)
            self.item_cards.append(card)

        self.exists_metric.set_value(str(exists_count))
        selected_count = len(self._selected_items())
        self.selected_metric.set_value(str(selected_count))
        percent = int(selected_count / exists_count * 100) if exists_count else 0
        self.protection_bar.setValue(percent)
        last_snapshot = self.snapshots[0].name if self.snapshots else "暂无"
        self.protection_summary.setText(f"已选择 {selected_count} / {exists_count} 个存在项目，最近快照：{last_snapshot}。")
        if hasattr(self, "restore_selected_summary"):
            self.restore_selected_summary.setText(f"将恢复当前勾选的 {selected_count} 个项目。")
        self.refresh_link_hint()
        self.refresh_restore_detail()

    def refresh_snapshots(self) -> None:
        self.snapshots = self.service.list_snapshots()
        for widget in [self.snapshot_list, self.restore_snapshot_list]:
            widget.clear()
            for snapshot in self.snapshots:
                widget.addItem(snapshot.name)
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
        self.schedule_switch.blockSignals(True)
        self.schedule_switch.setChecked(created)
        self.schedule_switch.blockSignals(False)

    def create_backup(self) -> None:
        selected = self._selected_items()
        if not selected:
            self._warn("请至少选择一个存在的备份项目。")
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
            self._warn("请至少选择一个存在的备份项目。")
            return
        if not is_valid_time(schedule_time):
            self._warn("请输入 HH:mm 格式的时间，例如 22:30。")
            return

        def job(log):
            config_path = Path(__file__).with_name("data") / "schedule.json"
            self.service.write_schedule_config(config_path, self.backup_root, selected_names)
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
            f"从快照恢复到 {self.home}\n\n快照：{snapshot.name}\n项目：{', '.join(selected_names)}\n\n{detail_text}恢复前会先备份当前目标目录。是否继续？",
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
        name = self.link_combo.currentText()
        item = next((candidate for candidate in self.items if candidate.name == name), None)
        if item is None or not item.source.exists():
            self._warn("项目不存在，不能迁移。")
            return
        store_path = self.backup_root / "link-store" / item.name
        if store_path.exists():
            self._warn("link-store 已存在同名项目，请先检查后再迁移。")
            return
        ok = QMessageBox.question(
            self,
            APP_TITLE,
            f"这是高级操作，会移动原目录并创建 Junction。\n\n项目：{item.name}\n源路径：{item.source}\n\n是否继续？",
        )
        if ok != QMessageBox.StandardButton.Yes:
            return

        def job(log):
            result = self.service.prepare_link_migration(item, self.backup_root / "link-store")
            self.service.create_junction(result.link_path, result.store_path)
            log(f"迁移完成：{result.link_path} -> {result.store_path}")
            log(f"迁移前备份：{result.pre_migration_backup_dir}")

        self._run_worker(job, refresh=True, success_text="Junction 迁移完成")

    def open_backup_dir(self) -> None:
        self.backup_root.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer", str(self.backup_root)])

    def refresh_link_hint(self) -> None:
        if not hasattr(self, "link_hint"):
            return
        name = self.link_combo.currentText() if hasattr(self, "link_combo") else ""
        if not name:
            self.link_hint.setText("请选择要迁移的项目。")
            return
        item = next((candidate for candidate in self.items if candidate.name == name), None)
        if item is None:
            self.link_hint.setText("项目不存在。")
            return
        store_path = self.backup_root / "link-store" / item.name
        if store_path.exists():
            self.link_hint.setText(f"目标已存在：{store_path}。请先检查，避免覆盖。")
        elif not item.source.exists():
            self.link_hint.setText(f"源路径不存在：{item.source}")
        else:
            self.link_hint.setText(f"将移动到：{store_path}，并在原位置创建 Junction。")

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
                lines.append(f"- {item.name} <- {item.source}")
        else:
            lines.append("包含项目：未读取到项目明细")
        lines.append("")
        available = ", ".join(detail.available_selected_names) if detail.available_selected_names else "无"
        missing = ", ".join(detail.missing_selected_names) if detail.missing_selected_names else "无"
        lines.append(f"可恢复：{available}")
        lines.append(f"快照缺少：{missing}")
        self.restore_snapshot_detail.setPlainText("\n".join(lines))

    def set_all_items(self, checked: bool) -> None:
        existing_names = self._existing_item_names()
        self.selected_names = set(existing_names) if checked else set()
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
        if self.scanned_items:
            self.apply_scanned_items(self.scanned_items)
        else:
            self.refresh_items()

    def _selected_items(self) -> list[BackupItem]:
        existing_names = self._existing_item_names()
        return [item for item in self.items if item.name in self.selected_names and item.name in existing_names]

    def persist_selected_items(self) -> None:
        existing_names = self._existing_item_names()
        write_user_settings(self.user_settings_path, [item.name for item in self.items if item.name in self.selected_names and item.name in existing_names])

    def _existing_item_names(self) -> set[str]:
        if self.scanned_items:
            return {entry.item.name for entry in self.scanned_items if entry.exists}
        return {item.name for item in self.items if item.source.exists()}

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
        self.inline_log.append(message)
        self.log.append(message)

    def _warn(self, text: str) -> None:
        InfoBar.warning(title="需要处理", content=text, parent=self, position=InfoBarPosition.TOP_RIGHT, duration=2600)

    def _info(self, text: str) -> None:
        InfoBar.info(title="提示", content=text, parent=self, position=InfoBarPosition.TOP_RIGHT, duration=2200)

    def _success(self, text: str) -> None:
        InfoBar.success(title="完成", content=text, parent=self, position=InfoBarPosition.TOP_RIGHT, duration=2600)

    def _show_error(self, text: str) -> None:
        self.append_log(text)
        InfoBar.error(title="任务失败", content=text.splitlines()[0], parent=self, position=InfoBarPosition.TOP_RIGHT, duration=5000)

    def _wait_for_thread(self, thread: QThread | None) -> None:
        if thread and thread.isRunning():
            thread.wait()


def main() -> int:
    app = QApplication(sys.argv)
    setTheme(Theme.LIGHT)
    app.setStyleSheet(STYLE)
    window = FluentBackupApp()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
