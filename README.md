# Ai会话备份

`Ai会话备份` 是一个 Windows 桌面工具，用来备份当前用户目录下的 AI 会话、命令行工具配置和开发环境配置，重点保护 `.codex`、`.happy`、`.claude`、`.ssh`、`.vscode` 这类容易被 C 盘重装、系统恢复或误清理影响的数据。

GitHub 英文项目名：**AI Session Backup**。

## 为什么需要它

很多 AI 工具、开发工具和命令行工具来自 Linux / Unix 生态，习惯把配置和会话数据放在用户目录下的点号文件夹里，例如：

```text
C:\Users\<用户名>\.codex
C:\Users\<用户名>\.happy
C:\Users\<用户名>\.claude
C:\Users\<用户名>\.ssh
C:\Users\<用户名>\.vscode
```

这些目录在 Windows 上不显眼，但可能保存 AI 对话、会话索引、登录状态、CLI 配置、SSH key、编辑器插件配置和恢复系统后很难补齐的本地状态。

Windows 重装系统、恢复系统、换机器、C 盘损坏或误清理时，这些数据经常一起丢失。`Ai会话备份` 的目标是让这些重要目录默认被看见、被备份，并在需要时可以迁移到 D 盘长期保存。

## 当前版本

```text
V1.0.0
```

这是第一个正式公开发布版本。建议先使用“备份”功能确认快照内容和恢复逻辑，再按需使用“迁移”功能。

## 下载运行

在 GitHub Releases 下载 Windows 便携版：

```text
Ai会话备份-V1.0.0-windows-portable.zip
```

解压后运行：

```text
Ai会话备份.exe
```

也可以从源码运行：

```powershell
python -m pip install -r requirements.txt
pythonw app_fluent.py
```

## 两种用法

### 1. 保守用法：备份 C 盘配置

软件默认扫描当前用户目录下现有的 `.` 前缀文件夹，并显示在“备份”页里。你可以勾选要保护的目录，也可以手动添加普通文件或文件夹。

备份会生成快照目录，默认保存到：

```text
D:\code\backup
```

快照名使用：

```text
YYYY-MM-DD_HH-MM-SS
```

这种方式不会改变 C 盘原始目录结构，适合正在使用、经常变化、可能有数据库锁或程序占用的目录。

### 2. 迁移用法：真实数据放到 D 盘，C 盘只保留引用

如果你希望减少 C 盘风险，可以在“迁移”页把选中的点号目录迁移到 D 盘。软件会：

```text
1. 先备份原目录
2. 把真实目录移动到 D 盘备份目录下的“迁移后的真实目录”
3. 在 C 盘原位置创建 Junction
```

迁移后，程序看起来仍然访问原来的 C 盘路径，但真实数据已经放在 D 盘。软件每次打开都会重新读取迁移状态，并高亮显示已经迁移的项目。你也可以点“取消迁移”，把 D 盘真实目录迁回 C 盘原位置。

## Junction 是什么

迁移功能使用 Windows 的 **Junction**。它是 NTFS 支持的目录链接技术，命令行里类似这样：

```cmd
mklink /J C:\Users\<用户名>\.vscode D:\code\backup\迁移后的真实目录\.vscode
```

很多开发环境迁移方案都会使用符号链接、目录链接或 Junction 来把配置目录挪到更安全的位置。这个软件把“先备份、再移动、再创建 Junction、显示状态、可取消迁移”的过程做成了 Windows 图形界面。

注意：Junction 不是云同步，也不是加密备份。D 盘如果损坏，数据仍然会丢失；重要内容仍建议再做离机备份。

## 主要功能

- 自动扫描当前用户目录下的点号文件夹
- 自助选择要备份的文件夹或文件
- 备份目录、定时时间、勾选项目和自定义项目会保存
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

不要把备份快照上传到公开仓库、公开网盘或不可信位置。如果要离机保存，建议配合加密压缩包或私有对象存储。

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

生成 Windows 便携版：

```powershell
python scripts/build_windows_release.py
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
