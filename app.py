from __future__ import annotations

import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from backup_core import BackupItem, BackupService
from project_config import (
    APP_TITLE,
    SCHEDULE_TASK_NAME,
    build_sensitive_backup_warning,
    default_items,
    get_backup_root,
    load_config,
)


def format_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


class BackupApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("980x640")
        self.minsize(900, 560)

        config = load_config()
        self.home = Path.home()
        self.backup_root = get_backup_root(config)
        self.service = BackupService(self.backup_root)
        self.items = default_items(self.home)
        self.item_vars: dict[str, tk.BooleanVar] = {}

        self._build_ui()
        self.refresh_all()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, padding=12)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.columnconfigure(1, weight=1)

        ttk.Label(header, text=APP_TITLE, font=("Microsoft YaHei UI", 16, "bold")).grid(row=0, column=0, sticky="w")
        self.backup_label = ttk.Label(header, text=str(self.backup_root))
        self.backup_label.grid(row=0, column=1, sticky="e")

        left = ttk.LabelFrame(self, text="备份项目", padding=10)
        left.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=(0, 8))
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)

        columns = ("selected", "name", "status", "size", "modified", "path")
        self.item_tree = ttk.Treeview(left, columns=columns, show="headings", height=12)
        self.item_tree.heading("selected", text="选择")
        self.item_tree.heading("name", text="名称")
        self.item_tree.heading("status", text="状态")
        self.item_tree.heading("size", text="大小")
        self.item_tree.heading("modified", text="最后修改")
        self.item_tree.heading("path", text="路径")
        self.item_tree.column("selected", width=54, anchor="center", stretch=False)
        self.item_tree.column("name", width=150, stretch=False)
        self.item_tree.column("status", width=70, anchor="center", stretch=False)
        self.item_tree.column("size", width=90, anchor="e", stretch=False)
        self.item_tree.column("modified", width=150, stretch=False)
        self.item_tree.column("path", width=360)
        self.item_tree.grid(row=0, column=0, sticky="nsew")
        self.item_tree.bind("<Button-1>", self._toggle_item)

        item_scroll = ttk.Scrollbar(left, orient="vertical", command=self.item_tree.yview)
        item_scroll.grid(row=0, column=1, sticky="ns")
        self.item_tree.configure(yscrollcommand=item_scroll.set)

        buttons = ttk.Frame(left)
        buttons.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(buttons, text="刷新", command=self.refresh_all).pack(side="left")
        ttk.Button(buttons, text="立即备份", command=self.create_backup).pack(side="left", padx=8)
        ttk.Button(buttons, text="全选", command=lambda: self._set_all(True)).pack(side="left")
        ttk.Button(buttons, text="全不选", command=lambda: self._set_all(False)).pack(side="left", padx=8)

        right = ttk.LabelFrame(self, text="备份快照", padding=10)
        right.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=(0, 8))
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self.snapshot_list = tk.Listbox(right, height=12)
        self.snapshot_list.grid(row=0, column=0, sticky="nsew")
        snapshot_scroll = ttk.Scrollbar(right, orient="vertical", command=self.snapshot_list.yview)
        snapshot_scroll.grid(row=0, column=1, sticky="ns")
        self.snapshot_list.configure(yscrollcommand=snapshot_scroll.set)

        restore_buttons = ttk.Frame(right)
        restore_buttons.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(restore_buttons, text="刷新快照", command=self.refresh_snapshots).pack(side="left")
        ttk.Button(restore_buttons, text="恢复选中快照", command=self.restore_selected).pack(side="left", padx=8)

        schedule = ttk.LabelFrame(right, text="定时备份", padding=8)
        schedule.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        schedule.columnconfigure(1, weight=1)
        ttk.Label(schedule, text="每天时间").grid(row=0, column=0, sticky="w")
        self.schedule_time_var = tk.StringVar(value="22:30")
        ttk.Entry(schedule, textvariable=self.schedule_time_var, width=8).grid(row=0, column=1, sticky="w", padx=8)
        ttk.Button(schedule, text="创建/更新", command=self.create_schedule).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(schedule, text="删除", command=self.delete_schedule).grid(row=0, column=3)
        self.schedule_status = ttk.Label(schedule, text="")
        self.schedule_status.grid(row=1, column=0, columnspan=4, sticky="w", pady=(6, 0))

        links = ttk.LabelFrame(right, text="链接迁移（高级）", padding=8)
        links.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        links.columnconfigure(0, weight=1)
        self.link_item_var = tk.StringVar(value=".happy")
        self.link_combo = ttk.Combobox(links, textvariable=self.link_item_var, values=[item.name for item in self.items], state="readonly")
        self.link_combo.grid(row=0, column=0, sticky="ew")
        ttk.Button(links, text="迁移到D盘并创建Junction", command=self.migrate_selected_link).grid(row=0, column=1, padx=(8, 0))
        ttk.Label(links, text="会先备份，再移动到备份目录下的 link-store，最后在用户目录创建 Junction。").grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        log_frame = ttk.LabelFrame(self, text="日志", padding=10)
        log_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=12, pady=(0, 12))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        self.log_text = tk.Text(log_frame, height=8, wrap="word")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        self.log_text.configure(state="disabled")

    def refresh_all(self) -> None:
        self.refresh_items()
        self.refresh_snapshots()
        self.refresh_schedule_status()

    def refresh_items(self) -> None:
        for row in self.item_tree.get_children():
            self.item_tree.delete(row)

        scanned = self.service.scan_items(self.items)
        for entry in scanned:
            item = entry.item
            if item.name not in self.item_vars:
                self.item_vars[item.name] = tk.BooleanVar(value=entry.exists)
            selected = "✓" if self.item_vars[item.name].get() else ""
            modified = entry.last_write_time.strftime("%Y-%m-%d %H:%M:%S") if entry.last_write_time else ""
            values = (
                selected,
                item.name,
                "存在" if entry.exists else "缺失",
                format_size(entry.size_bytes),
                modified,
                str(item.source),
            )
            self.item_tree.insert("", "end", iid=item.name, values=values)

    def refresh_snapshots(self) -> None:
        self.snapshot_list.delete(0, tk.END)
        self.snapshots = self.service.list_snapshots()
        for snapshot in self.snapshots:
            self.snapshot_list.insert(tk.END, snapshot.name)

    def create_backup(self) -> None:
        selected = self._selected_items()
        if not selected:
            messagebox.showwarning(APP_TITLE, "请至少选择一个存在的备份项目。")
            return
        warning = build_sensitive_backup_warning(selected)
        message = f"将备份 {len(selected)} 个项目到：\n{self.backup_root}\n\n是否开始？"
        if warning:
            message = f"{warning}\n\n{message}"
        if not messagebox.askyesno(APP_TITLE, message):
            return
        self._run_background(lambda: self._create_backup_worker(selected))

    def restore_selected(self) -> None:
        selection = self.snapshot_list.curselection()
        if not selection:
            messagebox.showwarning(APP_TITLE, "请先选择一个备份快照。")
            return
        selected_items = [item.name for item in self._selected_items()]
        if not selected_items:
            messagebox.showwarning(APP_TITLE, "请至少选择一个要恢复的项目。")
            return
        snapshot = self.snapshots[selection[0]]
        detail = self.service.read_snapshot_detail(snapshot, selected_items)
        detail_lines = []
        if detail.error:
            detail_lines.append(f"快照详情：{detail.error}")
        if detail.missing_selected_names:
            detail_lines.append(f"快照缺少项目：{', '.join(detail.missing_selected_names)}")
        sensitive_names = [
            item.name
            for item in detail.items
            if item.name in selected_items and item.sensitive_plaintext
        ]
        if sensitive_names:
            detail_lines.append(f"敏感明文项目：{', '.join(sensitive_names)}")
        detail_text = "\n".join(detail_lines)
        if detail_text:
            detail_text += "\n\n"
        ok = messagebox.askyesno(
            APP_TITLE,
            f"将从快照恢复到 {self.home}\n\n快照：{snapshot.name}\n项目：{', '.join(selected_items)}\n\n{detail_text}恢复前会先备份当前目标目录。是否继续？",
        )
        if not ok:
            return
        self._run_background(lambda: self._restore_worker(snapshot, selected_items))

    def create_schedule(self) -> None:
        selected = [item.name for item in self._selected_items()]
        if not selected:
            messagebox.showwarning(APP_TITLE, "请至少选择一个存在的备份项目。")
            return
        schedule_time = self.schedule_time_var.get().strip()
        if not self._valid_time(schedule_time):
            messagebox.showwarning(APP_TITLE, "请输入 HH:mm 格式的时间，例如 22:30。")
            return
        self._run_background(lambda: self._create_schedule_worker(selected, schedule_time))

    def delete_schedule(self) -> None:
        self._run_background(self._delete_schedule_worker)

    def migrate_selected_link(self) -> None:
        item = next((candidate for candidate in self.items if candidate.name == self.link_item_var.get()), None)
        if item is None:
            return
        if not item.source.exists():
            messagebox.showwarning(APP_TITLE, f"项目不存在：{item.source}")
            return
        ok = messagebox.askyesno(
            APP_TITLE,
            f"这是高级操作，会移动原目录并创建 Junction。\n\n项目：{item.name}\n源路径：{item.source}\n\n请确认已经理解：之后数据会实际写入 D 盘 link-store。是否继续？",
        )
        if not ok:
            return
        self._run_background(lambda: self._migrate_link_worker(item))

    def _create_backup_worker(self, selected: list[BackupItem]) -> None:
        self._log("开始备份...")
        result = self.service.create_snapshot(selected)
        self._log(f"备份完成：{result.path}")
        if result.skipped_items:
            self._log(f"跳过缺失项目：{', '.join(result.skipped_items)}")
        self.after(0, self.refresh_snapshots)

    def _restore_worker(self, snapshot: Path, selected_items: list[str]) -> None:
        self._log(f"开始恢复：{snapshot}")
        result = self.service.restore_snapshot(snapshot, self.home, selected_items)
        self._log(f"恢复完成：{', '.join(result.restored_items)}")
        self._log(f"恢复前备份：{result.pre_restore_backup_dir}")
        if result.skipped_items:
            self._log(f"跳过快照中不存在的项目：{', '.join(result.skipped_items)}")
        self.after(0, self.refresh_items)

    def _create_schedule_worker(self, selected_names: list[str], schedule_time: str) -> None:
        self._log("开始创建定时备份任务...")
        config_path = Path(__file__).with_name("data") / "schedule.json"
        self.service.write_schedule_config(config_path, self.backup_root, selected_names)
        launcher = Path(__file__).with_name("定时备份入口.bat")
        subprocess.run(
            [
                "schtasks",
                "/Create",
                "/TN",
                SCHEDULE_TASK_NAME,
                "/SC",
                "DAILY",
                "/ST",
                schedule_time,
                "/TR",
                str(launcher),
                "/F",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self._log(f"定时备份任务已创建：每天 {schedule_time}")
        self.after(0, self.refresh_schedule_status)

    def _delete_schedule_worker(self) -> None:
        result = subprocess.run(
            ["schtasks", "/Delete", "/TN", SCHEDULE_TASK_NAME, "/F"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            self._log("定时备份任务已删除。")
        else:
            self._log("没有找到可删除的定时备份任务。")
        self.after(0, self.refresh_schedule_status)

    def _migrate_link_worker(self, item: BackupItem) -> None:
        self._log(f"开始链接迁移：{item.name}")
        link_store = self.backup_root / "link-store"
        result = self.service.prepare_link_migration(item, link_store)
        self.service.create_junction(result.link_path, result.store_path)
        self._log(f"迁移完成：{result.link_path} -> {result.store_path}")
        self._log(f"迁移前备份：{result.pre_migration_backup_dir}")
        self.after(0, self.refresh_items)

    def refresh_schedule_status(self) -> None:
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", SCHEDULE_TASK_NAME, "/FO", "LIST"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            self.schedule_status.configure(text="状态：已创建")
        else:
            self.schedule_status.configure(text="状态：未创建")

    def _selected_items(self) -> list[BackupItem]:
        selected = []
        for item in self.items:
            if self.item_vars.get(item.name, tk.BooleanVar(value=False)).get() and item.source.exists():
                selected.append(item)
        return selected

    def _toggle_item(self, event) -> None:
        region = self.item_tree.identify("region", event.x, event.y)
        column = self.item_tree.identify_column(event.x)
        if region != "cell" or column != "#1":
            return
        row_id = self.item_tree.identify_row(event.y)
        if not row_id:
            return
        var = self.item_vars[row_id]
        var.set(not var.get())
        self.refresh_items()

    def _valid_time(self, value: str) -> bool:
        parts = value.split(":")
        if len(parts) != 2:
            return False
        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except ValueError:
            return False
        return 0 <= hour <= 23 and 0 <= minute <= 59

    def _set_all(self, value: bool) -> None:
        for item in self.items:
            self.item_vars.setdefault(item.name, tk.BooleanVar(value=value)).set(value)
        self.refresh_items()

    def _run_background(self, func) -> None:
        thread = threading.Thread(target=self._safe_run, args=(func,), daemon=True)
        thread.start()

    def _safe_run(self, func) -> None:
        try:
            func()
        except Exception as exc:
            self._log(f"操作失败：{exc}")
            self.after(0, lambda: messagebox.showerror(APP_TITLE, str(exc)))

    def _log(self, message: str) -> None:
        def append() -> None:
            self.log_text.configure(state="normal")
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state="disabled")

        self.after(0, append)


if __name__ == "__main__":
    BackupApp().mainloop()
