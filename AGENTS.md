# AGENTS.md

## 项目定位

- 本项目是 Windows 桌面 GUI 小工具，用于备份和恢复用户目录下的 AI/开发工具配置与会话数据。
- 项目目录：`D:\code\DaiMa\C盘备份软件`。
- 默认 GUI 使用 PySide6 + qfluentwidgets 实现；旧 Tkinter 和 PySide6 QSS 备用界面已删除，不再维护。
- 默认 UI 风格：跟随系统主题、蓝色主题色、侧边导航、微软商店风格窗口、紧凑组件密度。
- 默认备份目录：`D:\code\backup`

## 默认备份对象

- 默认扫描 `C:\Users\<当前用户>` 下现有的 `.` 前缀文件夹，例如 `.happy`、`.codex`、`.claude`、`.ssh`、`.vscode`。
- 如果用户目录不可扫描，回退到 `.claude`、`.codex`、`.happy`、`.ssh`。
- 普通文件和非 `.` 前缀目录不再固定作为默认项；需要备份时通过 Fluent 界面的自定义文件/文件夹功能添加。
- 如果旧配置仍保存 `.gitconfig`、`AppData/Roaming/npm` 等固定默认项，Fluent 启动时自动迁移为当前存在的点号文件夹。

## 安全规则

- 不在 GUI、日志或聊天中打印完整 token、key、SSH 私钥、认证 JSON 内容。
- Windows 上删除备份、测试目录或用户数据时必须优先移动到回收站；不要用 `Remove-Item -Recurse -Force` 永久删除用户数据，除非用户明确要求永久删除。
- 删除 `D:\code\backup` 这类目录时必须先列出子项并排除人工命名目录，例如包含“手工、手动、原来、manual、old、备份”的目录；不确定时单独询问。
- 恢复时如果目标路径已存在，必须先备份当前目标到 `恢复前备份`，再覆盖恢复。
- Junction/符号链接迁移只能作为高级功能手动触发；必须先备份、再移动到 D 盘 `迁移后的真实目录`、最后创建 Junction。
- 备份时跳过临时目录和易变锁文件，例如 `.codex\tmp`、`.codex\.tmp`、SQLite 的 `-shm` 文件。
- Windows 上复制目录优先用 `robocopy`，避免 `AppData\Roaming\npm\node_modules` 深层路径导致 `shutil.copytree` 失败。

## 项目记忆

- 成功经验记录到 `skills/good/SKILL.md`
- 失败路线记录到 `skills/bad/SKILL.md`

## GitHub 开源发布约定

- 公开仓库：`https://github.com/myjr2015/ai-session-backup`
- 远端默认使用：`origin https://github.com/myjr2015/ai-session-backup.git`
- 当前开源标准结构包含：`LICENSE`、`CONTRIBUTING.md`、`SECURITY.md`、`CODE_OF_CONDUCT.md`、`README.md`、`requirements.txt`、`pyproject.toml`、`api.example.txt`、`.github/ISSUE_TEMPLATE/`、`.github/pull_request_template.md`、`.github/workflows/tests.yml`。
- 发布到 GitHub 前必须检查工作区和敏感文件：
  - 先运行 `git status --short --branch` 和 `git diff`，只提交本次相关文件。
  - 确认 `api.txt`、`data/user-settings.json`、日志、截图、`.idea/`、`__pycache__/` 等仍被 `.gitignore` 排除。
  - 可用 `git check-ignore -v api.txt data/user-settings.json data/open-app-err.txt data/open-app-out.txt .idea/workspace.xml` 复查忽略来源。
- 本机 GitHub 登录和推送默认走全局登录脚本，不要打印 token：
  - `. 'D:\code\DaiMa\#全局登录脚本\Github.ps1' -ApiPath 'D:\code\DaiMa\#全局登录脚本\api.txt' -Quiet`
  - 如果普通 `git push` 触发 Git Credential Manager 卡住，使用：
    `git -c credential.helper="!gh auth git-credential" push`
  - 推送前可设置 `$env:GCM_INTERACTIVE='never'` 和 `$env:GIT_TERMINAL_PROMPT='0'`，避免交互弹窗阻塞自动流程。
- GitHub Actions 使用 Windows runner，CI 前本地至少运行：
  - `python -m py_compile backup_cli.py backup_core.py app_fluent.py`
  - `python -m unittest discover -s scripts/test -p 'test_*.py' -v`
  - 完整测试约 120 秒，工具超时要给到 10 分钟左右；不要把 120 秒命令超时误判为测试失败。
- CI 查看流程：
  - `gh run list --repo myjr2015/ai-session-backup --workflow tests --limit 5`
  - `gh run watch <run_id> --repo myjr2015/ai-session-backup --exit-status`
  - 失败时用 `gh run view <run_id> --repo myjr2015/ai-session-backup --log-failed` 看日志后再改。
- Windows GitHub Actions 的 stdout 编码可能不是 UTF-8；CLI 中文输出兜底必须按当前 `sys.stdout.encoding` 做安全转义，不要写死 UTF-8 再用 ASCII 解码。
- 公开发布名：中文软件名 `Ai会话备份`，英文仓库名 `ai-session-backup`，当前版本为 `V1.1.0`。
- Windows 便携版打包：
  - 入口脚本：`scripts/build_windows_release.py`
  - PowerShell 包装入口：`scripts/build_windows_release.ps1`
  - PyInstaller spec：`windows_portable.spec`
  - 输出：`release/ai-session-backup-v1.1.0-windows-portable.zip`
  - 打包时排除 PyQt5/PyQt6/PySide2、torch、pandas、scipy、matplotlib 等无关库，避免当前全局 Python 环境把无关依赖打进发布包。
- 中文路径和中文文件名发布包优先用 Python 脚本处理；不要用 Windows PowerShell 5.1 直接负责中文路径压缩和中文 spec 路径，容易因编码解析错导致构建后找不到输出。

## 定时任务

- 任务名：`Ai会话备份-定时备份`
- 入口：`定时备份入口.bat`
- 配置：`data/schedule.json`
- 默认时间：每天 `22:30`

## GUI 约定

- 默认启动脚本：`启动Ai会话备份.bat`，启动 `app_fluent.py`。
- 正式软件图标：`assets/app.ico`；窗口标题栏和 PyInstaller exe 都必须使用这个图标。
- 正式启动脚本必须用 `start "" /D ... pythonw.exe ...` 拉起 GUI 后立即 `exit /b 0`，避免用户双击 bat 后黑色 `cmd` 窗口一直常驻。
- 旧调试启动入口已删除；不要再恢复，避免和默认启动脚本重复并带出控制台窗口。
- 界面要兼顾美观和尺寸，Fluent 主界面默认 `720x540`，最小 `672x500`；避免回到大而笨重的表格布局。
- Fluent 主界面采用“总览 / 备份 / 恢复 / 迁移 / 云端 / 任务 / 环境 / 日志”分区；不要再把所有功能塞到同一页。
- 主窗口使用 qfluentwidgets `MSFluentWindow` 微软商店风格窗口壳和内置侧边导航；不要再手写窄导航按钮。
- 旧 `NavigationInterface.addItem(onClick=...)` 回调会收到 `checked` 布尔参数，如果后续演示器或小工具仍使用该控件，绑定页面时必须显式忽略该参数，例如 `lambda checked=False, target=page: ...`，避免把 `bool` 传给页面切换。
- Fluent 排版采用紧凑工具型密度：优先用 4/8px 间距节奏、最小宽度和自适应布局，避免为简单工具堆固定长宽。
- Fluent 总览页采用窄屏单列工作台：顶部配置区，当前保护状态、定时备份、状态摘要依次排列；不要再放最近快照和最近日志预览。
- 备份、恢复、迁移、任务、环境、日志页必须保持完整工作区宽度；工具栏和操作按钮使用自适应/换行布局，避免窄窗口横向挤压。
- Fluent 页面操作按钮使用 qfluentwidgets 默认 `PushButton` / `PrimaryPushButton` 风格；只允许用项目 helper 控制紧凑高度和自适应宽度，不再手写按钮颜色、边框和 hover QSS。
- “备份”页工具栏按“选择 / 自定义”分组，避免窄窗口下按钮挤压。
- “备份”页必须保留“立即备份”主操作，选完清单后不需要回到总览页执行备份。
- “备份”页默认按大小从大到小排序，排序下拉显示“从大到小 / 从小到大 / 最近更新”；列表行保持单行信息，只有名称使用粗体。
- “备份”和“迁移”列表右键菜单只保留“打开当前目录”，不要让可选文本触发 Qt 默认英文菜单。
- “备份”页单项勾选后必须保持当前滚动位置，不能因为刷新列表跳回顶部或跳到其他内容。
- “迁移”页使用和“备份”页一致的卡片、排序和分组工具栏布局；列表默认按“已迁移”排序，排序下拉显示“已迁移 / 从大到小 / 从小到大 / 最近更新”；不要再改回单选下拉框。
- `.vscode` 已通过真实迁移和取消迁移验证：迁移时 D 盘 `迁移后的真实目录\.vscode` 保存真实目录，C 盘用户目录 `.vscode` 为 Junction 引用；取消迁移后 C 盘 `.vscode` 恢复为普通目录。
- 备份创建后必须校验快照内文件和目录是否复制完整；Windows 子进程复制必须隐藏控制台窗口，避免备份时终端闪烁。
- “任务”页用于打开 Windows 任务计划程序；“环境”页用于备份当前 Path 到 `环境变量Path备份`，并以管理员身份打开系统环境变量入口提示用户检查 Path；暂不做 Path 恢复。
- “云端”页用于 Cloudflare R2 加密增量备份；真实测试前先运行全局 `Cloudflare_R2.ps1` 登录脚本，再从环境变量填入配置。云端备份必须先加密文件对象并最后上传 manifest。
- Fluent 启动或保存备份目录时会把旧英文维护目录 `restore-backups`、`link-store`、`link-migration-backups`、`environment-path` 合并到中文维护目录；旧英文名只作为兼容输入，不再作为默认展示。
- 页面内部不要重复放“管理项目 / 恢复快照 / 查看全部”等导航跳转；已有左侧导航栏，页内只保留当前页必要操作。
- 讨论主题、主题色、导航栏风格、窗口风格和组件密度时，优先用 `style_demo_fluent.py` 本地演示器做选择；当前已确认默认采用“跟随系统 / 蓝色 / 侧边导航 / 微软商店风格 / 紧凑”，后续正式界面默认沿用这套标准。
- 修改 Fluent UI 后必须运行布局回归测试，并可用 `python scripts/capture_ui_snapshots.py` 生成 `data/ui-snapshots/` 截图人工检查 `720x540` 和 `672x500`。
- 日志只放到底部导航的日志页；总览页不要再放日志预览。
- 默认快照目录名使用 `YYYY-MM-DD_HH-MM-SS`；同名时由核心服务追加 `-01`、`-02`。
- Fluent 界面的备份选择保存在 `data/user-settings.json`；空列表表示用户明确全不选，不要自动恢复成全选。
- 自定义文件/文件夹备份内容也保存在 `data/user-settings.json` 的 `custom_items`，快照内路径使用 `自定义/<名称>`。
- Fluent 界面的备份目录和定时时间也保存在 `data/user-settings.json`；任何保存配置、勾选、自定义项目变更都不能清空这两个设置。
- Fluent 界面的勾选项、自定义项目和备份目录变更必须同步写入 `data/schedule.json`，保证已有计划任务按最新配置执行。
- 恢复页必须显示快照 `manifest.json` 明细，包含快照内容、当前勾选内容中可恢复和缺失的内容。
- 公共配置统一放在 `project_config.py`；CLI 和 GUI 不要从已删除的旧界面模块导入默认项目或任务名。
- Fluent 备份扫描使用后台 `ScanWorker`；不要改回主线程递归扫描，避免 `.codex`、`npm` 目录较大时界面卡顿。
- 快照 `manifest.json` 必须保留敏感标记；新增敏感备份对象时同步更新 `project_config.py` 的 `BackupItem.sensitive`。
- 自定义项目恢复必须优先使用 manifest 里的 `restore_target` 原始路径；默认项目继续按当前用户目录恢复。
