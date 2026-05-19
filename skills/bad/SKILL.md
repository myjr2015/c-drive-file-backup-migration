---
name: bad
description: 本项目失败路线、风险和不要重复尝试的方案。
---

# bad

## 风险

- 不要只备份 `.happy`；Happy 负责手机端会话索引和映射，Codex 真实会话与状态还在 `.codex`。
- 不要默认使用 Junction/符号链接迁移作为第一版方案；恢复系统后容易出现 C 盘新目录和 D 盘旧目录分叉。
- 当前本机没有 .NET SDK，不能直接创建并编译 WPF 项目。
- 不要用 Python `shutil.copytree` 直接复制 `AppData\Roaming\npm\node_modules` 这类深层目录；真实备份时已遇到 `[WinError 3] 系统找不到指定的路径`，改用 `robocopy`。
- 不要在 `schtasks /TR` 里塞复杂嵌套 PowerShell 引号；已验证容易被解析错。计划任务应固定调用 `定时备份入口.bat`，具体备份项目写入 `data/schedule.json`。
- 原生 Tkinter 界面又大又粗糙，不要继续在旧界面上做主要美化；默认维护 PySide6 版 `app_qt.py`。
- 不要只换 UI 框架而复用同一套拥挤布局；之前 Tkinter、Qt、Fluent、WPF 看起来差不多，就是因为信息架构没变。后续主线应维护 `app_fluent.py` 的分页面结构。
- 不要把 `restore-backups`、`link-store`、`link-migration-backups` 当作普通快照展示或恢复。
- 不要在 link-store 已存在同名目录时继续 Junction 迁移；这通常表示以前迁移过或有残留，必须先人工检查。
- 不要把 `data/user-settings.json` 里空的 `selected_items` 当成首次启动；空列表可能表示用户明确选择“全不选”，必须通过 `settings_exists` 区分。
- 不要让 `backup_cli.py` 或新版 GUI 从旧 Tkinter `app.py` 导入公共配置；公共配置必须从 `project_config.py` 读取，避免命令行入口意外加载 GUI 依赖。
- 不要让 Fluent 窗口关闭时遗留正在运行的 `QThread`；测试可能表面 OK 但 Python 进程用 Qt 崩溃码退出。
- 不要把敏感项目的快照当成加密备份；当前只是明文落盘并在 GUI/manifest 中标记风险。
- 不要把 `.happy`、`.codex`、`.claude`、`.ssh`、`.gitconfig` 快照当成脱敏备份；它们可能包含 token、SSH 私钥或认证状态，上传、同步、分享前必须确认位置可信。
