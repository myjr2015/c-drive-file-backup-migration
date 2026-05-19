# AGENTS.md

## 项目定位

- 本项目是 Windows 桌面 GUI 小工具，用于备份和恢复用户目录下的 AI/开发工具配置与会话数据。
- 项目目录：`D:\code\DaiMa\C盘备份软件`；旧目录 `D:\code\DaiMa\AI配置备份工具` 已迁移，不要再作为主线维护。
- 默认 GUI 使用 PySide6 + qfluentwidgets 实现，保留 PySide6 QSS 版和 Tkinter 旧界面作为备用。
- 默认备份目录：`D:\code\DaiMa\#全局备份\AI会话备份`

## 默认备份对象

- `C:\Users\<当前用户>\.happy`
- `C:\Users\<当前用户>\.codex`
- `C:\Users\<当前用户>\.claude`
- `C:\Users\<当前用户>\.ssh`
- `C:\Users\<当前用户>\.gitconfig`
- `C:\Users\<当前用户>\AppData\Roaming\npm`
- `C:\Users\<当前用户>\AppData\Roaming\npm-cache`

## 安全规则

- 不在 GUI、日志或聊天中打印完整 token、key、SSH 私钥、认证 JSON 内容。
- 恢复时如果目标路径已存在，必须先备份当前目标到 `restore-backups`，再覆盖恢复。
- Junction/符号链接迁移只能作为高级功能手动触发；必须先备份、再移动到 D 盘 link-store、最后创建 Junction。
- 备份时跳过临时目录和易变锁文件，例如 `.codex\tmp`、`.codex\.tmp`、SQLite 的 `-shm` 文件。
- Windows 上复制目录优先用 `robocopy`，避免 `AppData\Roaming\npm\node_modules` 深层路径导致 `shutil.copytree` 失败。

## 项目记忆

- 成功经验记录到 `skills/good/SKILL.md`
- 失败路线记录到 `skills/bad/SKILL.md`

## 定时任务

- 任务名：`AI配置备份助手-定时备份`
- 入口：`定时备份入口.bat`
- 配置：`data/schedule.json`
- 默认时间：每天 `22:30`

## GUI 约定

- 默认启动脚本：`启动AI配置备份助手.bat`，启动 `app_fluent.py`。
- Qt QSS 备用界面：`app_qt.py`。
- 旧版备用脚本：`启动旧版Tkinter界面.bat`，启动 `app.py`。
- 界面要兼顾美观和尺寸，默认 `980x620`，最小 `860x540`；避免回到大而笨重的表格布局。
- Fluent 主界面采用“总览 / 备份项目 / 恢复 / Junction / 日志”分区；不要再把所有功能塞到同一页。
- 日志默认只在总览显示预览，完整日志放到底部导航的日志页。
- 默认快照目录名使用 `YYYY-MM-DD_HH-MM-SS`；同名时由核心服务追加 `-01`、`-02`。
- Fluent 界面的备份项目选择保存在 `data/user-settings.json`；空列表表示用户明确全不选，不要自动恢复成全选。
- 恢复页必须显示快照 `manifest.json` 明细，包含快照项目、当前勾选项目中可恢复和缺失的项目。
- 公共配置统一放在 `project_config.py`；CLI 和 GUI 不要再从旧 Tkinter `app.py` 导入默认项目或任务名。
- Fluent 备份项目扫描使用后台 `ScanWorker`；不要改回主线程递归扫描，避免 `.codex`、`npm` 目录较大时界面卡顿。
- 快照 `manifest.json` 必须保留敏感标记；新增敏感备份对象时同步更新 `project_config.py` 的 `BackupItem.sensitive`。
