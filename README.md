# AI配置备份助手

Windows GUI 小工具，用于备份和恢复用户目录里的点号配置目录、AI 会话和自定义文件/文件夹。

项目目录：

```text
D:\code\DaiMa\C盘备份软件
```

默认备份目录：

```text
D:\code\backup
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

运行：

```powershell
pythonw app_fluent.py
```

也可以直接双击：

```text
启动AI配置备份助手.bat
```

Fluent 风格界面使用 PySide6 + qfluentwidgets，适合 Windows 11 风格的紧凑操作：
默认只保留 `启动AI配置备份助手.bat` 作为正式入口，脚本会分离启动 `pythonw.exe`，避免黑色控制台窗口常驻。

本地风格演示器用于比较主题、主题色、导航栏、窗口和组件密度：

```powershell
python style_demo_fluent.py
```

也可以直接双击：

```text
启动Fluent风格演示器.bat
```

测试：

```powershell
python -m unittest discover -s scripts/test -p "test_*.py"
```

## 参与贡献

- Bug 和功能建议请提交 GitHub Issues。
- 代码改动请提交 Pull Request，并说明修改内容、影响和验证结果。
- 不要上传 `.happy`、`.codex`、`.claude`、`.ssh`、备份快照或任何包含 token/私钥的文件。
- 贡献前请先阅读 `CONTRIBUTING.md` 和 `SECURITY.md`。

## 第一版范围

- 默认勾选并备份用户目录下现有的 `.` 前缀文件夹，例如 `.happy`、`.codex`、`.claude`、`.ssh`、`.vscode`
- Fluent 界面的“备份”页可自助添加任意文件或文件夹作为自定义备份
- `开发环境恢复安装清单.md` 记录恢复 Windows 系统后需要重装和验证的语言 SDK、CLI 和 AI 工具
- 每次备份创建一个日期快照目录，格式为 `YYYY-MM-DD_HH-MM-SS`
- 恢复前自动把当前目标目录备份到 `恢复前备份`
- 默认跳过 `.tmp`、`tmp`、`*.sqlite-shm`、`*.db-shm`、`*.lock` 等临时/易变文件
- `.happy`、`.codex`、`.claude`、`.ssh` 等点号文件夹会按原目录明文备份，GUI 会在备份和恢复确认前提示风险
- 快照同名时自动追加序号，避免同秒重复备份失败
- 快照 `manifest.json` 会记录 `contains_sensitive_plaintext` 和每个项目的 `sensitive_plaintext`
- 快照列表会自动隐藏 `恢复前备份`、`迁移后的真实目录`、`迁移前备份`、`取消迁移前备份`、`环境变量Path备份`
- Junction 迁移前会检查 `迁移后的真实目录` 是否已有同名目录，并在移动失败时尽量回滚
- Fluent 界面会记住用户选择的备份内容、自定义内容、备份目录和定时时间，配置保存在 `data/user-settings.json`
- 如果旧配置仍保存 `.gitconfig`、`AppData/Roaming/npm` 等固定默认项，Fluent 启动时会自动切换为当前用户目录下现有的点号文件夹。
- 恢复页会读取快照里的 `manifest.json`，显示快照包含内容、当前勾选内容中可恢复和缺失的部分

## 界面

- 默认 GUI：`app_fluent.py`
- 技术：PySide6 + qfluentwidgets
- 默认 UI 风格：跟随系统主题、蓝色主题色、侧边导航、微软商店风格窗口、紧凑组件密度
- 窗口默认尺寸：`720x540`
- 最小尺寸：`672x500`
- 布局：使用 qfluentwidgets `MSFluentWindow` 窗口壳和侧边导航，总览 / 备份 / 恢复 / 迁移 / 任务计划 / 环境 / 日志 分页
- 左侧导航使用 qfluentwidgets 默认行为，不再手写导航按钮样式。
- 排版密度采用紧凑工具型方案：减少固定宽高，页面和卡片间距按 4/8px 节奏收紧。
- 总览页顶部集中保存备份目录和配置；下面只保留当前保护状态、定时备份和状态摘要，最近快照和日志放到对应独立页面
- 备份、恢复、迁移、任务、环境、日志页保持完整工作区宽度；按钮区在窄窗口下自动换行
- 页面操作按钮使用 qfluentwidgets 默认 `PushButton` / `PrimaryPushButton` 风格，只保留紧凑高度和自适应宽度。
- “备份”页支持全选、全不选和单项勾选；单项勾选后保持当前位置，不会跳到别处，重新打开软件后会沿用上次选择
- “备份”页工具栏直接提供“立即备份”，选完清单后不需要回到总览页执行
- “备份”页支持“添加文件夹”“添加文件”“删除已勾选自定义”；自定义内容会显示为 `自定义/<名称>`
- “备份”页默认按大小从大到小排列，排序下拉显示“从大到小 / 从小到大 / 最近更新”；列表行只让名称加粗，路径、大小、时间跟在同一行显示
- “备份”页工具栏按“选择 / 自定义”分组，减少按钮堆在一行的挤压
- “备份”和“迁移”列表右键菜单只保留“打开当前目录”，避免 Qt 默认英文复制菜单干扰
- 总览页顶部可直接修改备份保存目录，点击“保存”后下次启动继续使用同一目录
- 定时备份时间会随配置保存，下次启动继续显示上次填写的时间；输入框失焦也会自动保存
- “任务计划”页可打开 Windows 任务计划程序，方便检查定时备份任务
- “环境”页可先把 Path 备份到 `环境变量Path备份`，再用管理员权限打开系统环境变量入口，方便检查和编辑 Path
- “迁移”页采用和“备份”页一致的列表、排序和分组工具栏布局，默认按“已迁移”排列并高亮已迁移目录
- 已用真实 `.vscode` 验证：可备份到 `D:\code\backup`，可从快照恢复，迁移后真实目录位于 `D:\code\backup\迁移后的真实目录\.vscode`，取消迁移后 C 盘用户目录会恢复成普通目录
- 恢复页选择快照后会显示 `manifest.json` 明细，避免不知道快照里实际包含哪些内容
- 备份扫描在后台线程执行，避免启动或刷新时界面卡顿

## UI 排版检查

自动化测试会检查 Fluent 界面在 `720x540`、`672x500` 等紧凑尺寸下的关键控件，并约束默认窗口和最小窗口尺寸，避免导航、备份目录输入框、定时时间、备份页和恢复页出现 0 宽高或明显遮挡。

生成截图用于人工对比：

```powershell
python scripts/capture_ui_snapshots.py
```

默认输出到：

```text
data/ui-snapshots/
```

截图目录不加入 Git，主要用于本地检查排版变化。

## 代码结构

- `project_config.py`：项目标题、计划任务名、默认备份项目、配置读取和备份目录解析
- `backup_core.py`：后台扫描、快照、恢复、Junction 迁移、计划配置和快照 manifest 读取
- `backup_cli.py`：定时任务和命令行备份入口，不依赖旧 GUI
- `app_fluent.py`：当前默认 Fluent GUI，使用跟随系统、蓝色、侧边导航、微软商店风格窗口和紧凑密度
- `style_demo_fluent.py`：本地 Fluent 风格演示器，用于选择主题、导航、窗口和组件密度
- `scripts/capture_ui_snapshots.py`：生成 Fluent 主界面截图，用于排版回归检查

## 自定义备份

在 Fluent 界面的“备份”页，可以点击“添加文件夹”或“添加文件”选择任意路径。自定义内容会保存到：

```text
data/user-settings.json
```

保存结构包含：

```json
{
  "selected_items": ["自定义/示例目录"],
  "backup_root": "D:\\code\\backup",
  "schedule_time": "22:30",
  "custom_items": [
    {
      "name": "示例目录",
      "path": "D:\\example\\示例目录",
      "sensitive": true
    }
  ]
}
```

快照中自定义内容统一放在 `自定义/<名称>` 下，`manifest.json` 会记录原始路径。恢复时默认恢复到原始路径；如果目标已存在，会先备份到 `恢复前备份` 再覆盖。

## 环境变量 Path 备份

在 Fluent 界面的“环境”页点击“备份 Path”，会把当前 Path 导出到：

```text
D:\code\backup\环境变量Path备份\<时间戳>\
```

每次导出包含：

```text
path.json  结构化数据，包含用户 Path、系统 Path、当前进程 Path
path.txt   人工查看版本，一行一个路径
```

当前只做备份，不自动恢复 Path。

## 敏感数据说明

`.happy`、`.codex`、`.claude`、`.ssh` 等点号文件夹可能包含 token、SSH 私钥、认证状态或 AI 会话数据。当前版本按原目录明文备份到本地快照目录，不会在 GUI、日志或聊天中打印完整密钥，但备份文件本身没有加密。

不要把快照目录直接上传到公开网盘、公开仓库或不可信服务器。如果后续需要离机保存，优先增加压缩包加密或 R2 私有桶上传流程。

## 定时备份

GUI 里可以创建或删除 Windows 计划任务：

```text
AI配置备份助手-定时备份
```

当前已创建默认任务：每天 `22:30` 运行 `定时备份入口.bat`，按 `data/schedule.json` 里的内容备份。Fluent 界面里的勾选项、自定义内容和备份目录变更会同步写入这个计划配置。“任务计划”页可以直接打开 Windows 任务计划程序查看启用状态和上次运行结果。

手动验证：

```powershell
python backup_cli.py scheduled-backup --config .\data\schedule.json
```

## 迁移

GUI 的“迁移”页会执行：

```text
1. 先把原目录备份到 `迁移前备份`
2. 把原目录移动到 D 盘备份目录下的 `迁移后的真实目录`
3. 在原路径创建 Junction
```

这个功能不会自动执行，必须手动点按钮确认。已经迁移的目录会在列表里显示“已迁移”，可以点“取消迁移”把 D 盘真实目录移动回 C 盘原位置。

界面底部会解释常见术语：

```text
- Junction：Windows 的目录链接，看起来还在原位置，实际数据指向 D 盘里的目录
- 迁移后的真实目录：迁移后的真实保存位置，默认放在备份目录下面
- 恢复前备份：恢复前自动保存原目录副本的位置，用来出错时回退
- 取消迁移前备份：取消迁移前自动保存 D 盘真实目录副本的位置，用来出错时回退
```

安全检查：

```text
- 源路径不存在：禁止迁移
- `迁移后的真实目录` 已有同名项目：禁止迁移
- Junction 位置已存在：禁止创建
- 迁移前会生成 `迁移前备份`
- 取消迁移前会生成 `取消迁移前备份`

旧版本已经创建过的英文维护目录会在启动 Fluent 界面或保存备份目录时自动合并到中文目录；如果旧 Junction 指向旧目录，整理时会重新指向新的中文目录。
```
