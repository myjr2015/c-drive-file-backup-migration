# AI配置备份助手

Windows GUI 小工具，用于备份和恢复用户目录里的 Happy、Codex、Claude、SSH 和 npm 配置。

项目目录：

```text
D:\code\DaiMa\C盘备份软件
```

默认备份目录：

```text
D:\code\DaiMa\#全局备份\AI会话备份
```

运行：

```powershell
python app_fluent.py
```

也可以直接双击：

```text
启动AI配置备份助手.bat
```

当前默认启动的是 Fluent 风格界面。旧版 Tkinter 界面保留为备用：

```text
启动旧版Tkinter界面.bat
```

Fluent 风格界面使用 PySide6 + qfluentwidgets，适合 Windows 11 风格的紧凑操作：

```powershell
python app_fluent.py
```

也可以直接双击：

```text
启动Fluent界面.bat
```

测试：

```powershell
python -m unittest discover -s scripts/test
```

## 第一版范围

- 勾选并备份用户目录下的 `.happy`、`.codex`、`.claude`、`.ssh`、`.gitconfig`、`AppData\Roaming\npm`、`AppData\Roaming\npm-cache`
- `开发环境恢复安装清单.md` 记录恢复 Windows 系统后需要重装和验证的语言 SDK、CLI 和 AI 工具
- 每次备份创建一个日期快照目录，格式为 `YYYY-MM-DD_HH-MM-SS`
- 恢复前自动把当前目标目录备份到 `restore-backups`
- 默认跳过 `.tmp`、`tmp`、`*.sqlite-shm`、`*.db-shm`、`*.lock` 等临时/易变文件
- `.happy`、`.codex`、`.claude`、`.ssh`、`.gitconfig` 这类敏感项目会按原目录明文备份，GUI 会在备份和恢复确认前提示风险
- 快照同名时自动追加序号，避免同秒重复备份失败
- 快照 `manifest.json` 会记录 `contains_sensitive_plaintext` 和每个项目的 `sensitive_plaintext`
- 快照列表会自动隐藏 `restore-backups`、`link-store`、`link-migration-backups`
- Junction 迁移前会检查 link-store 是否已有同名目录，并在移动失败时尽量回滚
- Fluent 界面会记住用户选择的备份项目，配置保存在 `data/user-settings.json`
- 恢复页会读取快照里的 `manifest.json`，显示快照包含项目、当前勾选项目中可恢复和缺失的项目

## 界面

- 默认 GUI：`app_fluent.py`
- 技术：PySide6 + qfluentwidgets
- 备用 Qt GUI：`app_qt.py`，技术：PySide6 + QSS
- 窗口默认尺寸：`980x620`
- 最小尺寸：`860x540`
- 布局：左侧导航、总览仪表盘、独立备份项目页、恢复页、Junction 页、日志页
- 总览页只放保护状态、快捷操作、定时备份、快照和日志预览；备份项目不再挤在首页
- 备份项目页支持全选、全不选和单项勾选；重新打开软件后会沿用上次选择
- 恢复页选择快照后会显示 `manifest.json` 明细，避免不知道快照里实际包含哪些项目
- 备份项目扫描在后台线程执行，避免启动或刷新时界面卡顿

## 代码结构

- `project_config.py`：项目标题、计划任务名、默认备份项目、配置读取和备份目录解析
- `backup_core.py`：后台扫描、快照、恢复、Junction 迁移、计划配置和快照 manifest 读取
- `backup_cli.py`：定时任务和命令行备份入口，不依赖旧 GUI
- `app_fluent.py`：当前默认 Fluent GUI
- `app_qt.py` / `app.py`：备用 GUI

## 敏感数据说明

`.happy`、`.codex`、`.claude`、`.ssh`、`.gitconfig` 可能包含 token、SSH 私钥、认证状态或 AI 会话数据。当前版本按原目录明文备份到本地快照目录，不会在 GUI、日志或聊天中打印完整密钥，但备份文件本身没有加密。

不要把快照目录直接上传到公开网盘、公开仓库或不可信服务器。如果后续需要离机保存，优先增加压缩包加密或 R2 私有桶上传流程。

## 定时备份

GUI 里可以创建或删除 Windows 计划任务：

```text
AI配置备份助手-定时备份
```

当前已创建默认任务：每天 `22:30` 运行 `定时备份入口.bat`，按 `data/schedule.json` 里的项目备份。

手动验证：

```powershell
python backup_cli.py scheduled-backup --config .\data\schedule.json
```

## 链接迁移

GUI 右侧“链接迁移（高级）”会执行：

```text
1. 先把原目录备份到 link-migration-backups
2. 把原目录移动到 D 盘备份目录下的 link-store
3. 在原路径创建 Junction
```

这个功能不会自动执行，必须手动点按钮确认。

安全检查：

```text
- 源路径不存在：禁止迁移
- link-store 已有同名项目：禁止迁移
- Junction 位置已存在：禁止创建
- 迁移前会生成 link-migration-backups
```
