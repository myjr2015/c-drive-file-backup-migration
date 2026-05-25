# C盘文件备份迁移

Windows 桌面工具，用来备份和迁移用户目录下的配置文件夹，重点保护 AI 工具会话、开发工具配置、SSH 配置、编辑器配置等容易被 C 盘重装或系统恢复影响的数据。

这个项目的 GitHub 英文名是 **C Drive File Backup Migration**。

## 为什么需要它

很多开发工具、AI 工具和命令行工具最早来自 Linux / Unix 生态，习惯把配置和会话数据放在用户目录下的点号文件夹里，例如：

```text
C:\Users\<用户名>\.codex
C:\Users\<用户名>\.happy
C:\Users\<用户名>\.claude
C:\Users\<用户名>\.ssh
C:\Users\<用户名>\.vscode
```

这些目录在 Windows 上看起来不显眼，但里面可能保存：

- AI 对话、会话索引、登录状态
- CLI 工具配置
- SSH key 和连接配置
- 编辑器、插件和开发工具配置
- 本地缓存、历史记录和恢复系统后很难重新补齐的状态

Windows 重装系统、恢复系统、换机器、C 盘损坏或误清理时，这些目录经常一起丢失。`C盘文件备份迁移` 的目标很简单：让这些文件默认被看见、被备份，并且在需要时可以迁移到 D 盘长期保存。

## 两种用法

### 1. 保守用法：定时备份 C 盘配置

这是默认推荐方式。软件会扫描当前用户目录下现有的 `.` 前缀文件夹，默认显示在“备份”页里。你可以勾选要保护的目录，也可以手动添加普通文件或文件夹。

备份会生成一个快照目录，默认保存到：

```text
D:\code\backup
```

快照名使用：

```text
YYYY-MM-DD_HH-MM-SS
```

这种方式不会改变 C 盘原始目录结构，适合先观察、先备份、先确认数据是否能恢复。

### 2. 迁移用法：真实数据放到 D 盘，C 盘只保留链接

如果你希望一劳永逸地减少 C 盘风险，可以在“迁移”页把选中的点号目录迁移到 D 盘。软件会：

```text
1. 先备份原目录
2. 把真实目录移动到 D 盘备份目录下的“迁移后的真实目录”
3. 在 C 盘原位置创建 Junction
```

迁移后，软件每次打开都会重新读取当前目录是否已经迁移，并在列表里高亮显示“已迁移”的项目。你也可以随时点“取消迁移”，把 D 盘真实目录迁回 C 盘原位置。

## Junction 是什么

迁移功能使用 Windows 的 **Junction**。它是 NTFS 支持的目录链接技术，效果是：程序看起来仍然访问原来的 C 盘路径，但真实数据已经放在 D 盘目录里。

Windows 命令行里类似这样的命令会创建 Junction：

```cmd
mklink /J C:\Users\<用户名>\.vscode D:\code\backup\迁移后的真实目录\.vscode
```

很多 GitHub 项目和开发环境迁移方案都会使用符号链接、目录链接或 Junction 来把配置目录挪到更安全的位置。这个软件只是把“先备份、再移动、再创建 Junction、再显示状态、可取消迁移”的过程做成了 Windows 图形界面。

注意：Junction 不是云同步，也不是加密备份。D 盘如果损坏，数据仍然会丢失；重要内容仍建议再做离机备份。

## 当前版本

```text
V0.0.1
```

这是早期测试版，功能已经可用，但仍按 bug 版本看待。建议先用“保守用法”做定时备份，确认快照和恢复逻辑符合预期后，再使用迁移功能。

## 下载安装

在 GitHub Releases 下载 Windows 便携版：

```text
C盘文件备份迁移-V0.0.1-windows-portable.zip
```

解压后运行：

```text
C盘文件备份迁移.exe
```

也可以从源码运行：

```powershell
python -m pip install -r requirements.txt
pythonw app_fluent.py
```

## 默认备份对象

默认扫描：

```text
C:\Users\<当前用户>\
```

下现有的 `.` 前缀文件夹。普通文件、普通目录、非点号目录不会默认加入，需要在“备份”页手动添加。

如果用户目录不可扫描，会回退显示：

```text
.claude
.codex
.happy
.ssh
```

## 主要功能

- 自动扫描当前用户目录下的点号文件夹
- 自助选择要备份的文件夹或文件
- 备份目录、定时时间、勾选项目和自定义项目会保存，方便下次继续使用
- 支持 Windows 计划任务定时备份
- 备份后校验快照内文件是否复制完整
- 恢复前会把当前目标目录保存到“恢复前备份”
- “迁移”页显示未迁移、已迁移、异常状态
- 已迁移目录高亮显示，可取消迁移
- 环境页可备份当前 Path 环境变量
- 备份、恢复、迁移过程不会在界面或日志里打印完整 token/key

## 界面和技术

- GUI：PySide6 + qfluentwidgets
- 默认风格：跟随系统主题、蓝色主题色、侧边导航、微软商店风格窗口、紧凑密度
- 默认窗口尺寸：`720x540`
- 默认备份目录：`D:\code\backup`
- 主要页面：总览 / 备份 / 恢复 / 迁移 / 任务计划 / 环境 / 日志

## 敏感数据提醒

`.codex`、`.happy`、`.claude`、`.ssh` 等目录可能包含 token、SSH 私钥、认证状态或 AI 会话数据。当前版本是本地明文备份，不会自动加密。

不要把备份快照上传到公开仓库、公开网盘或不可信位置。如果要离机保存，建议后续配合加密压缩包或私有对象存储。

## 开发运行

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

运行 GUI：

```powershell
pythonw app_fluent.py
```

运行测试：

```powershell
python -m unittest discover -s scripts/test -p "test_*.py" -v
```

生成 UI 截图用于排版检查：

```powershell
python scripts/capture_ui_snapshots.py
```

## 项目结构

- `project_config.py`：项目名称、版本、默认备份目录、默认扫描逻辑
- `backup_core.py`：扫描、备份、恢复、迁移、计划配置和 manifest
- `backup_cli.py`：定时任务和命令行备份入口
- `app_fluent.py`：当前 Windows Fluent GUI
- `style_demo_fluent.py`：Fluent 风格演示器
- `scripts/test/`：单元测试和 GUI smoke 测试

## 参与贡献

欢迎通过 GitHub Issues 提交问题、想法和使用场景。提交 PR 时请说明：

- 改了什么
- 为什么改
- Windows 版本和 Python 版本
- 如何验证

请不要上传 `.codex`、`.happy`、`.claude`、`.ssh`、备份快照或任何包含 token/私钥的文件。
