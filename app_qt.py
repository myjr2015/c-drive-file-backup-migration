from __future__ import annotations

import subprocess
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from backup_core import BackupItem, BackupService
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
QMainWindow, QWidget {
    background: #f5f7fb;
    color: #1f2937;
    font-family: "Microsoft YaHei UI", "Segoe UI";
    font-size: 13px;
}
QFrame#Sidebar {
    background: #ffffff;
    border-right: 1px solid #e5e7eb;
}
QPushButton {
    border: 1px solid #d8dee9;
    border-radius: 8px;
    padding: 7px 12px;
    background: #ffffff;
}
QPushButton:hover {
    background: #f0f5ff;
    border-color: #9bbcff;
}
QPushButton#PrimaryButton {
    background: #2563eb;
    border-color: #2563eb;
    color: white;
    font-weight: 600;
}
QPushButton#DangerButton {
    color: #b91c1c;
}
QFrame#Card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
}
QFrame#ItemCard {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
}
QFrame#ItemCard[missing="true"] {
    background: #f8fafc;
}
QLabel#Title {
    font-size: 22px;
    font-weight: 700;
}
QLabel#SectionTitle {
    font-size: 16px;
    font-weight: 700;
}
QLabel#Muted {
    color: #6b7280;
}
QLineEdit, QComboBox, QListWidget, QTextEdit {
    background: #ffffff;
    border: 1px solid #d8dee9;
    border-radius: 8px;
    padding: 6px;
}
QListWidget {
    padding: 4px;
}
QTextEdit {
    font-family: "Cascadia Mono", Consolas;
    font-size: 12px;
}
QCheckBox {
    spacing: 8px;
}
"""


class Worker(QThread):
    log = Signal(str)
    failed = Signal(str)
    finished_ok = Signal()

    def __init__(self, func):
        super().__init__()
        self.func = func

    def run(self) -> None:
        try:
            self.func(self.log.emit)
        except Exception as exc:
            self.failed.emit(f"{exc}\n{traceback.format_exc(limit=2)}")
        else:
            self.finished_ok.emit()


class ItemCard(QFrame):
    def __init__(self, scanned, checked: bool):
        super().__init__()
        self.item = scanned.item
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(checked and scanned.exists)
        self.checkbox.setEnabled(scanned.exists)
        self.setObjectName("ItemCard")
        self.setProperty("missing", "true" if not scanned.exists else "false")

        layout = QGridLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(3)
        layout.addWidget(self.checkbox, 0, 0, 2, 1)

        name = QLabel(scanned.item.name)
        name.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.DemiBold))
        layout.addWidget(name, 0, 1)

        status = "存在" if scanned.exists else "缺失"
        detail = f"{status} · {format_size(scanned.size_bytes)}"
        if scanned.last_write_time:
            detail += f" · {scanned.last_write_time.strftime('%Y-%m-%d %H:%M')}"
        muted = QLabel(detail)
        muted.setObjectName("Muted")
        layout.addWidget(muted, 0, 2, alignment=Qt.AlignmentFlag.AlignRight)

        path = QLabel(str(scanned.item.source))
        path.setObjectName("Muted")
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(path, 1, 1, 1, 2)
        layout.setColumnStretch(1, 1)


class BackupQtApp(QMainWindow):
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
        self.selected_names: set[str] = {item.name for item in self.items if item.source.exists()}
        self.item_cards: list[ItemCard] = []
        self.snapshots: list[Path] = []
        self.worker: Worker | None = None

        root = QWidget()
        self.setCentralWidget(root)
        main = QHBoxLayout(root)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        main.addWidget(self._build_sidebar())
        self.stack = QStackedWidget()
        main.addWidget(self.stack, 1)

        self.stack.addWidget(self._build_dashboard())
        self.stack.addWidget(self._build_restore_page())
        self.stack.addWidget(self._build_link_page())

        self.refresh_all()

    def _build_sidebar(self) -> QWidget:
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(178)
        layout = QVBoxLayout(side)
        layout.setContentsMargins(14, 18, 14, 14)
        layout.setSpacing(8)

        title = QLabel("AI备份")
        title.setFont(QFont("Microsoft YaHei UI", 18, QFont.Weight.Bold))
        layout.addWidget(title)

        subtitle = QLabel("配置与会话")
        subtitle.setObjectName("Muted")
        layout.addWidget(subtitle)
        layout.addSpacing(14)

        for text, index in [("总览", 0), ("恢复", 1), ("链接迁移", 2)]:
            button = QPushButton(text)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.clicked.connect(lambda checked=False, i=index: self.stack.setCurrentIndex(i))
            layout.addWidget(button)

        layout.addStretch()
        open_dir = QPushButton("打开备份目录")
        open_dir.clicked.connect(self.open_backup_dir)
        layout.addWidget(open_dir)
        return side

    def _build_dashboard(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel(APP_TITLE)
        title.setObjectName("Title")
        title_box.addWidget(title)
        path = QLabel(str(self.backup_root))
        path.setObjectName("Muted")
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        title_box.addWidget(path)
        header.addLayout(title_box, 1)

        backup_btn = QPushButton("立即备份")
        backup_btn.setObjectName("PrimaryButton")
        backup_btn.clicked.connect(self.create_backup)
        header.addWidget(backup_btn)
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.refresh_all)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        content = QHBoxLayout()
        content.setSpacing(12)
        layout.addLayout(content, 1)

        item_card = self._card("备份项目")
        item_layout = item_card.layout()
        controls = QHBoxLayout()
        all_btn = QPushButton("全选")
        all_btn.clicked.connect(lambda: self.set_all_items(True))
        none_btn = QPushButton("全不选")
        none_btn.clicked.connect(lambda: self.set_all_items(False))
        controls.addWidget(all_btn)
        controls.addWidget(none_btn)
        controls.addStretch()
        item_layout.addLayout(controls)

        self.item_container = QWidget()
        self.item_layout = QVBoxLayout(self.item_container)
        self.item_layout.setContentsMargins(0, 0, 0, 0)
        self.item_layout.setSpacing(8)
        self.item_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.item_container)
        item_layout.addWidget(scroll, 1)
        content.addWidget(item_card, 3)

        right = QVBoxLayout()
        content.addLayout(right, 2)
        right.addWidget(self._build_schedule_card())
        right.addWidget(self._build_snapshot_card(), 1)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(118)
        layout.addWidget(self.log)
        return page

    def _build_schedule_card(self) -> QFrame:
        card = self._card("定时备份")
        layout = card.layout()
        row = QHBoxLayout()
        self.schedule_time = QLineEdit("22:30")
        self.schedule_time.setFixedWidth(88)
        row.addWidget(QLabel("每天"))
        row.addWidget(self.schedule_time)
        create = QPushButton("创建/更新")
        create.clicked.connect(self.create_schedule)
        delete = QPushButton("删除")
        delete.setObjectName("DangerButton")
        delete.clicked.connect(self.delete_schedule)
        row.addWidget(create)
        row.addWidget(delete)
        layout.addLayout(row)
        self.schedule_status = QLabel("状态：读取中")
        self.schedule_status.setObjectName("Muted")
        layout.addWidget(self.schedule_status)
        return card

    def _build_snapshot_card(self) -> QFrame:
        card = self._card("最近快照")
        layout = card.layout()
        self.snapshot_list = QListWidget()
        layout.addWidget(self.snapshot_list, 1)
        return card

    def _build_restore_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)
        title = QLabel("恢复")
        title.setObjectName("Title")
        layout.addWidget(title)
        hint = QLabel("选择一个快照和要恢复的项目。恢复前会自动备份当前 C 盘目标目录。")
        hint.setObjectName("Muted")
        layout.addWidget(hint)
        self.restore_snapshot_list = QListWidget()
        layout.addWidget(self.restore_snapshot_list, 1)
        restore = QPushButton("恢复选中快照")
        restore.setObjectName("PrimaryButton")
        restore.clicked.connect(self.restore_selected)
        layout.addWidget(restore, alignment=Qt.AlignmentFlag.AlignRight)
        return page

    def _build_link_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)
        title = QLabel("链接迁移")
        title.setObjectName("Title")
        layout.addWidget(title)
        hint = QLabel("高级操作：先备份，再移动到 D 盘 link-store，最后在原位置创建 Junction。")
        hint.setObjectName("Muted")
        layout.addWidget(hint)
        card = self._card("选择项目")
        card_layout = card.layout()
        row = QHBoxLayout()
        self.link_combo = QComboBox()
        self.link_combo.addItems([item.name for item in self.items])
        row.addWidget(self.link_combo, 1)
        migrate = QPushButton("迁移到 D 盘并创建 Junction")
        migrate.setObjectName("DangerButton")
        migrate.clicked.connect(self.migrate_selected_link)
        row.addWidget(migrate)
        card_layout.addLayout(row)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _card(self, title_text: str) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)
        title = QLabel(title_text)
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        return card

    def refresh_all(self) -> None:
        self.refresh_items()
        self.refresh_snapshots()
        self.refresh_schedule_status()

    def refresh_items(self) -> None:
        for card in self.item_cards:
            card.setParent(None)
        self.item_cards = []
        scanned = self.service.scan_items(self.items)
        for entry in scanned:
            card = ItemCard(entry, entry.item.name in self.selected_names)
            card.checkbox.toggled.connect(lambda checked, name=entry.item.name: self._set_item_selected(name, checked))
            self.item_layout.insertWidget(self.item_layout.count() - 1, card)
            self.item_cards.append(card)

    def refresh_snapshots(self) -> None:
        self.snapshots = self.service.list_snapshots()
        for widget in [self.snapshot_list, self.restore_snapshot_list]:
            widget.clear()
            for snapshot in self.snapshots:
                item = QListWidgetItem(snapshot.name)
                item.setToolTip(str(snapshot))
                widget.addItem(item)

    def refresh_schedule_status(self) -> None:
        result = subprocess.run(["schtasks", "/Query", "/TN", SCHEDULE_TASK_NAME, "/FO", "LIST"], capture_output=True, text=True)
        self.schedule_status.setText("状态：已创建" if result.returncode == 0 else "状态：未创建")

    def create_backup(self) -> None:
        selected = self._selected_items()
        if not selected:
            QMessageBox.warning(self, APP_TITLE, "请至少选择一个存在的备份项目。")
            return
        warning = build_sensitive_backup_warning(selected)
        message = f"将备份 {len(selected)} 个项目到：\n{self.backup_root}\n\n是否开始？"
        if warning:
            message = f"{warning}\n\n{message}"
        ok = QMessageBox.question(self, APP_TITLE, message)
        if ok != QMessageBox.StandardButton.Yes:
            return

        def job(log):
            log("开始备份...")
            result = self.service.create_snapshot(selected)
            log(f"备份完成：{result.path}")

        self._run_worker(job, refresh=True)

    def create_schedule(self) -> None:
        selected_names = [item.name for item in self._selected_items()]
        schedule_time = self.schedule_time.text().strip()
        if not selected_names:
            QMessageBox.warning(self, APP_TITLE, "请至少选择一个存在的备份项目。")
            return
        if not is_valid_time(schedule_time):
            QMessageBox.warning(self, APP_TITLE, "请输入 HH:mm 格式的时间，例如 22:30。")
            return

        def job(log):
            config_path = Path(__file__).with_name("data") / "schedule.json"
            self.service.write_schedule_config(config_path, self.backup_root, selected_names)
            launcher = Path(__file__).with_name("定时备份入口.bat")
            subprocess.run(["schtasks", "/Create", "/TN", SCHEDULE_TASK_NAME, "/SC", "DAILY", "/ST", schedule_time, "/TR", str(launcher), "/F"], check=True, capture_output=True, text=True)
            log(f"定时备份任务已创建：每天 {schedule_time}")

        self._run_worker(job, refresh=True)

    def delete_schedule(self) -> None:
        def job(log):
            result = subprocess.run(["schtasks", "/Delete", "/TN", SCHEDULE_TASK_NAME, "/F"], capture_output=True, text=True)
            log("定时备份任务已删除。" if result.returncode == 0 else "没有找到可删除的定时备份任务。")

        self._run_worker(job, refresh=True)

    def restore_selected(self) -> None:
        row = self.restore_snapshot_list.currentRow()
        if row < 0 or row >= len(self.snapshots):
            QMessageBox.warning(self, APP_TITLE, "请先选择一个备份快照。")
            return
        selected_names = [item.name for item in self._selected_items()]
        if not selected_names:
            QMessageBox.warning(self, APP_TITLE, "请至少选择一个要恢复的项目。")
            return
        snapshot = self.snapshots[row]
        detail = self.service.read_snapshot_detail(snapshot, selected_names)
        detail_lines = []
        if detail.error:
            detail_lines.append(f"快照详情：{detail.error}")
        if detail.missing_selected_names:
            detail_lines.append(f"快照缺少项目：{', '.join(detail.missing_selected_names)}")
        sensitive_names = [
            item.name
            for item in detail.items
            if item.name in selected_names and item.sensitive_plaintext
        ]
        if sensitive_names:
            detail_lines.append(f"敏感明文项目：{', '.join(sensitive_names)}")
        detail_text = "\n".join(detail_lines)
        if detail_text:
            detail_text += "\n\n"
        ok = QMessageBox.question(self, APP_TITLE, f"从快照恢复到 {self.home}\n\n快照：{snapshot.name}\n项目：{', '.join(selected_names)}\n\n{detail_text}恢复前会先备份当前目标目录。是否继续？")
        if ok != QMessageBox.StandardButton.Yes:
            return

        def job(log):
            result = self.service.restore_snapshot(snapshot, self.home, selected_names)
            log(f"恢复完成：{', '.join(result.restored_items)}")
            log(f"恢复前备份：{result.pre_restore_backup_dir}")

        self._run_worker(job, refresh=True)

    def migrate_selected_link(self) -> None:
        name = self.link_combo.currentText()
        item = next((candidate for candidate in self.items if candidate.name == name), None)
        if item is None or not item.source.exists():
            QMessageBox.warning(self, APP_TITLE, "项目不存在，不能迁移。")
            return
        ok = QMessageBox.question(self, APP_TITLE, f"这是高级操作，会移动原目录并创建 Junction。\n\n项目：{item.name}\n源路径：{item.source}\n\n是否继续？")
        if ok != QMessageBox.StandardButton.Yes:
            return

        def job(log):
            result = self.service.prepare_link_migration(item, self.backup_root / "link-store")
            self.service.create_junction(result.link_path, result.store_path)
            log(f"迁移完成：{result.link_path} -> {result.store_path}")
            log(f"迁移前备份：{result.pre_migration_backup_dir}")

        self._run_worker(job, refresh=True)

    def open_backup_dir(self) -> None:
        self.backup_root.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer", str(self.backup_root)])

    def set_all_items(self, checked: bool) -> None:
        for card in self.item_cards:
            if card.checkbox.isEnabled():
                card.checkbox.setChecked(checked)

    def _set_item_selected(self, name: str, checked: bool) -> None:
        if checked:
            self.selected_names.add(name)
        else:
            self.selected_names.discard(name)

    def _selected_items(self) -> list[BackupItem]:
        return [item for item in self.items if item.name in self.selected_names and item.source.exists()]

    def _run_worker(self, func, refresh: bool) -> None:
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, APP_TITLE, "当前已有任务在运行。")
            return
        self.worker = Worker(func)
        self.worker.log.connect(self.append_log)
        self.worker.failed.connect(lambda text: QMessageBox.critical(self, APP_TITLE, text))
        if refresh:
            self.worker.finished_ok.connect(self.refresh_all)
        self.worker.start()

    def append_log(self, message: str) -> None:
        self.log.append(message)


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    window = BackupQtApp()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
