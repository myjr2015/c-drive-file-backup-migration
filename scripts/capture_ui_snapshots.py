from __future__ import annotations

import os
import sys
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import QSize  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app_fluent import STYLE, FluentBackupApp, apply_default_ui_theme  # noqa: E402


SNAPSHOT_SPECS = [
    ("dashboard", QSize(720, 540)),
    ("items", QSize(720, 540)),
    ("restore", QSize(720, 540)),
    ("link", QSize(720, 540)),
    ("task", QSize(720, 540)),
    ("environment", QSize(720, 540)),
    ("dashboard", QSize(672, 500)),
    ("items", QSize(672, 500)),
    ("link", QSize(672, 500)),
    ("task", QSize(672, 500)),
    ("environment", QSize(672, 500)),
]


def capture_ui_snapshots(output_dir: Path | str = Path("data") / "ui-snapshots") -> list[Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication([])
    apply_default_ui_theme()
    app.setStyleSheet(STYLE)
    window = FluentBackupApp()
    saved_paths: list[Path] = []
    try:
        window._wait_for_thread(window.scan_worker)
        app.processEvents()
        for page_name, size in SNAPSHOT_SPECS:
            page = getattr(window, f"{page_name}_page")
            window._set_current_page(page)
            window.resize(size)
            app.processEvents()
            pixmap = window.grab()
            file_path = output_path / f"{page_name}-{size.width()}x{size.height()}.png"
            if not pixmap.save(str(file_path)):
                raise RuntimeError(f"截图保存失败：{file_path}")
            saved_paths.append(file_path)
    finally:
        window.close()
        if QApplication.instance() is app:
            app.quit()
    return saved_paths


def main() -> int:
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data") / "ui-snapshots"
    for file_path in capture_ui_snapshots(output_dir):
        print(file_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
