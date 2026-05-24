---
name: good
description: 本项目已验证成功的备份、恢复、打包和 GUI 工作流。
---

# good

## 已验证可用

- 项目第一版采用 Python Tkinter，避免当前本机只有 .NET Runtime、没有 .NET SDK 导致 WPF 无法编译的问题。
- 2026-05-19 已验证 Windows 计划任务可用：`AI配置备份助手-定时备份` 每天 `22:30` 运行 `定时备份入口.bat`。
- 2026-05-19 已验证 `backup_cli.py scheduled-backup --config data/schedule.json` 可完成真实备份，输出快照目录：`D:\code\DaiMa\#全局备份\AI会话备份\2026-05-19-022112`。
- Windows 上备份深层目录使用 `robocopy` 更稳，已用于目录复制；`robocopy` 退出码小于 8 视为成功。
- 2026-05-19 已验证 PySide6 已安装，可用于新版紧凑 GUI；`app_qt.py` 可导入和编译，启动脚本已切到 Qt 版。
- 2026-05-19 已将 Fluent 主界面重做为 Windows 设置页式信息架构：总览页只放状态和快捷操作，备份项目、恢复、Junction、日志拆成独立页面；`app_fluent.py` 编译和 offscreen 初始化均已验证。
- 2026-05-19 已补强备份/恢复/Junction 安全逻辑：快照同名自动追加序号，快照列表过滤内部维护目录，Junction 迁移前检查迁移目标冲突，移动失败时尽量回滚。
- 2026-05-19 已验证真实定时备份入口仍可用，生成快照：`D:\code\DaiMa\#全局备份\AI会话备份\2026-05-19-194941`。
- 2026-05-19 已将默认快照命名改为 `YYYY-MM-DD_HH-MM-SS`，同名时追加 `-01`、`-02`；Fluent 界面已支持把备份项目选择保存到 `data/user-settings.json`，包括“全不选”也能在重开后保持。
- 2026-05-19 项目已从 `D:\code\DaiMa\AI配置备份工具` 迁移到 `D:\code\DaiMa\C盘备份软件`，Windows 计划任务 `AI配置备份助手-定时备份` 的入口已更新到新目录。
- 2026-05-19 已从 `中转站` 迁入 `开发环境恢复安装清单.md`，该文档用于 Windows 恢复系统后重装和验证 Python、Node.js、.NET、Go、Rust、Java、Git、GitHub CLI、Docker、Codex、Happy、Claude Code 等环境。
- 2026-05-19 已抽出 `project_config.py` 作为公共配置模块，`backup_cli.py` 不再导入旧 Tkinter `app.py`；Fluent 恢复页已显示快照 manifest 明细和缺失项目提示。
- 2026-05-19 已验证 Fluent 项目扫描可通过后台 `ScanWorker` 执行，窗口关闭时等待线程结束可避免 offscreen 单测通过但进程崩溃退出。
- 2026-05-19 快照 manifest 已记录 `contains_sensitive_plaintext` 和单项 `sensitive_plaintext`，GUI 备份/恢复确认会提示敏感明文项目。
- 2026-05-20 已新增自定义文件/文件夹备份项目：配置保存在 `data/user-settings.json` 的 `custom_items`，快照内路径为 `自定义/<名称>`，恢复时按 manifest 的 `restore_target` 回到原始路径。
- 2026-05-20 Fluent 界面已支持保存备份目录和定时时间到 `data/user-settings.json`；损坏的设置 JSON 会降级为空设置，不再阻止 GUI 启动。
- 2026-05-20 Fluent 配置变更会同步写入 `data/schedule.json`，已有计划任务入口继续读取同一个计划配置；普通 CLI 备份也可通过 `--settings` 读取自定义项目。
- 2026-05-20 已补齐 Qt/Tk 备用界面的配置同步：保存用户设置时也写 `data/schedule.json`；新增测试防止真实计划配置被临时测试路径污染。
- 2026-05-20 三套 GUI 保存配置时都会校验定时时间；非法 `HH:mm` 不会覆盖 `data/user-settings.json` 里的上次有效时间。
- 2026-05-20 已新增 Fluent UI 截图回归脚本 `scripts/capture_ui_snapshots.py`；可生成 `data/ui-snapshots/` 下的总览、备份项目、恢复页截图，并用单测检查关键控件尺寸。
- 2026-05-20 Fluent 总览页已按方案 3 重排为工作台：顶部配置区和分区状态摘要；备份项目和恢复页保持完整工作区宽度，`test_fluent_solution_three_layout_has_workbench_structure` 已覆盖该结构。
- 2026-05-20 Fluent 左侧导航已改为窄栏，小图标紧贴文字，释放中间工作区宽度；布局测试已覆盖导航宽度和图标存在。
- 2026-05-20 Fluent 排版已改为紧凑工具型密度：页面和卡片边距按 4/8px 节奏收紧，减少固定长宽。
- 2026-05-20 Fluent 紧凑布局保持约 `81px` 左侧导航和单行路径项目卡片。
- 2026-05-20 默认备份对象已改为扫描当前用户目录下现有的 `.` 前缀文件夹；普通文件和非点前缀目录通过自定义项目添加。
- 2026-05-20 Fluent 项目页“全选”会选中自定义项用于批量删除，备份和定时任务仍只执行存在的项目。
- 2026-05-20 Fluent 备份项目页已支持按大小从大到小、大小从小到大、最近更新排序；项目行采用“粗体名称 + 普通详情”的单行展示。
- 2026-05-21 默认备份目录已统一为 `D:\code\backup`；Fluent 主界面默认 `720x540`、最小 `672x500`，总览页改为单列排列；备份项目页和 Junction 页按钮区用 `FlowLayout` 支持窄窗口换行。
- 2026-05-21 Fluent 总览页已移除“最近快照”和“最近日志”预览，只保留当前保护状态、定时备份和状态摘要，减少冗余和高度占用。
- 2026-05-21 Fluent 页面操作按钮已回到 qfluentwidgets 默认 `PushButton` / `PrimaryPushButton` 风格；项目只保留紧凑高度和自适应宽度 helper，不再手写按钮颜色。
- 2026-05-21 Fluent 左侧导航已改回 qfluentwidgets 标准 `NavigationInterface`，避免自制窄导航和默认 Fluent 风格不一致。
- 2026-05-21 Fluent 链接页底部保留 `LinkTermsCard` 术语说明，用普通用户能看懂的语言解释 Junction、迁移后的真实目录、恢复前备份和迁移流程。
- 2026-05-21 Fluent 左侧导航已扩展为“总览 / 备份 / 恢复 / 迁移 / 任务 / 环境 / 日志”；任务页打开任务计划程序，环境页用管理员权限打开系统环境变量入口检查 Path。
- 2026-05-21 Fluent 备份项目勾选会在重建卡片前后保留 `item_scroll` 垂直滚动条位置，避免勾选后跳到其他位置。
- 2026-05-21 Fluent 用户可见页面标题已统一为“备份”和“迁移”，保留 Junction 作为迁移页术语说明；`test_main_page_copy_uses_user_facing_navigation_names` 已覆盖旧文案回归。
- 2026-05-21 备份后会校验快照内非临时文件是否复制完整；Windows `robocopy` 使用隐藏窗口参数，避免备份时控制台闪烁。
- 2026-05-21 Fluent 迁移页改为简洁多选列表，排序跟随“备份”页大小/最近更新排序；任务计划入口改为 PowerShell `Start-Process ... -Verb RunAs` 打开，避免 WinError 740。
- 2026-05-21 Fluent 迁移页已改成和备份页一致的卡片、排序和分组工具栏布局，默认按最近更新排序；操作按钮高度收紧到 28px。
- 2026-05-21 已将 Fluent 主界面方向调整为“默认风格优先”：删除自定义淡蓝按钮、勾选框配色和手写导航样式，保留业务布局结构。
- 2026-05-21 已修复 qfluentwidgets 标准导航点击不切页问题：`NavigationInterface.addItem(onClick=...)` 需要显式接收并忽略 `checked` 参数；`test_fluent_navigation_clicks_switch_pages` 已覆盖所有导航项点击切换。
- 2026-05-21 Fluent 环境页已支持“备份 Path”，导出到备份目录的 `环境变量Path备份/<时间戳>/path.json` 和 `path.txt`；当前只备份，不做自动恢复。
- 2026-05-23 已删除 Tkinter 旧界面和 PySide6 QSS 备用界面，只保留 PySide6 + qfluentwidgets 主线，减少维护面。
- 2026-05-23 已新增 `style_demo_fluent.py` 本地 Fluent 风格演示器，可独立比较主题、主题色、导航栏风格、窗口风格和组件密度，确认后再迁移到正式界面。
- 2026-05-24 已确认 Fluent 默认 UI 标准：跟随系统主题、蓝色主题色、侧边导航、微软商店风格窗口、紧凑组件密度；`app_fluent.py` 已切到 `MSFluentWindow` 窗口壳。
- 2026-05-24 已用真实 `.vscode` 验证软件目标链路：备份到 `D:\code\backup\real-vscode-test`、隔离恢复成功、迁移到 `D:\code\backup\迁移后的真实目录\.vscode`，`C:\Users\myjr2\.vscode` 变为 Junction 且可正常读取。
- 2026-05-24 Fluent 备份页已保留“立即备份”主操作，备份/迁移列表右键菜单只保留“打开当前目录”。
- 2026-05-24 已验证“取消迁移”可把真实 `.vscode` 从 D 盘迁回 `C:\Users\myjr2\.vscode` 普通目录，并生成 `D:\code\backup\取消迁移前备份` 回退副本。
- 2026-05-24 内部维护目录默认改为中文名：`恢复前备份`、`迁移后的真实目录`、`迁移前备份`、`取消迁移前备份`、`环境变量Path备份`；旧英文目录启动时会自动合并到中文目录并保持兼容。
- 2026-05-24 Fluent 迁移页已用 `BackupService.get_link_migration_status()` 统一判断 `未迁移 / 已迁移 / 异常`，列表直接显示状态，已迁移项可取消迁移，异常项禁用迁移和取消迁移并提示手动检查。
- 2026-05-24 迁移页窗口变高的主要原因是标题说明、列表最小高度和底部多行术语卡叠加；已改成紧凑术语说明条，并由 `test_link_page_uses_compact_terms_bar_without_forcing_tall_window` 覆盖。
- 2026-05-20 旧固定默认选择如果包含 `.gitconfig`、`AppData/Roaming/npm` 或 `npm-cache`，Fluent 启动时会迁移为当前存在的点号文件夹；手动只选 `.ssh` 这类配置不迁移。
- 2026-05-24 已修复 `MSFluentWindow` 从总览切到备份/迁移/任务计划/环境后真实鼠标拖动窗口会从 `720x540` 被抬高到约 `720x667` 的问题：拖动走 Windows 原生 `SC_MOVE`，需要在 `WM_GETMINMAXINFO` 固定最小跟踪尺寸，并在 `WM_WINDOWPOSCHANGING` 阶段锁住系统移动开始时的宽高；真实拖动验证所有导航页均保持 `720x540`。
- 2026-05-24 Fluent 迁移页已新增“已迁移”排序并设为默认：已迁移排前、异常排中、未迁移排后，已迁移卡片用浅蓝边框和背景高亮，`test_link_sort_migrated_first_and_highlights_migrated_cards` 覆盖排序和高亮。
- 2026-05-24 任务栏出现很多 `pythonw` 的根因不是多个进程或线程，而是同一 `pythonw.exe` 里残留多个可见 Qt 顶层小窗口；已将 InfoBar 改为单活动通知，新的提示出现前关闭旧提示，并补充只隐藏当前进程内标题为 `pythonw`、类名含 `QWindowIcon`、尺寸很小的残留窗口清理。
- 2026-05-24 `启动AI配置备份助手.bat` 已改为 `start "" /D "%~dp0" pythonw.exe app_fluent.py` 后立即 `exit /b 0`，真实验证双击入口只留下 `pythonw.exe app_fluent.py`，不再常驻项目相关 `cmd.exe`。
- 2026-05-24 已将项目整理为 GitHub 开源仓库 `myjr2015/ai-config-backup-helper`：包含 MIT 许可证、贡献说明、Issue/PR 模板、Security 文档和 Windows GitHub Actions 测试。
- 2026-05-24 GitHub Actions 的 Windows 控制台可能不是 UTF-8；CLI 中文输出兜底应使用当前 `sys.stdout.encoding` 加 `backslashreplace`，本地 `python -m unittest discover -s scripts/test -p 'test_*.py' -v` 已验证 97 个测试通过。
