from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


APP_NAME = "C盘文件备份迁移"
APP_VERSION = "V0.0.1"
ZIP_NAME = f"{APP_NAME}-{APP_VERSION}-windows-portable.zip"


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def zip_directory(source_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source_dir))


def write_release_readme(dist_dir: Path) -> None:
    text = f"""\
{APP_NAME} {APP_VERSION}

运行方式：
1. 解压整个文件夹。
2. 双击 {APP_NAME}.exe。
3. 默认备份目录是 D:\\code\\backup，可在软件总览页修改。

注意：
- 这是早期测试版。
- .codex、.happy、.claude、.ssh 等目录可能包含 token、SSH 私钥或 AI 会话数据。
- 当前版本是本地明文备份，不要把备份快照上传到公开位置。
"""
    (dist_dir / "使用说明.txt").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="构建 Windows 便携发布包")
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    dist_dir = repo / "dist" / APP_NAME
    release_dir = repo / "release"
    zip_path = release_dir / ZIP_NAME

    if not args.skip_tests:
        run([sys.executable, "-m", "py_compile", "backup_cli.py", "backup_core.py", "app_fluent.py", "project_config.py"])
        run([sys.executable, "-m", "unittest", "discover", "-s", "scripts/test", "-p", "test_*.py", "-v"])

    remove_path(repo / "build")
    remove_path(dist_dir)
    remove_path(zip_path)
    release_dir.mkdir(parents=True, exist_ok=True)

    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "windows_portable.spec"])
    if not dist_dir.exists():
        raise FileNotFoundError(f"PyInstaller 输出目录不存在：{dist_dir}")

    write_release_readme(dist_dir)
    zip_directory(dist_dir, zip_path)
    print(zip_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
