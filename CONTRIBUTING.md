# 贡献指南

感谢你愿意改进 Ai会话备份。

## 提交问题

- Bug 请使用 GitHub Issues 的 Bug 模板。
- 请说明 Windows 版本、Python 版本、启动方式、复现步骤和相关日志。
- 不要上传 `.happy`、`.codex`、`.claude`、`.ssh`、备份快照或任何包含 token/私钥的文件。

## 提交 PR

1. Fork 仓库并创建功能分支。
2. 安装依赖：

```powershell
python -m pip install -r requirements.txt
```

3. 运行测试：

```powershell
python -m unittest discover -s scripts/test -p "test_*.py"
```

4. PR 里说明修改内容、原因、验证结果和截图（如果改了 UI）。

## 开发约定

- 默认界面技术栈是 PySide6 + qfluentwidgets。
- 删除用户数据时必须优先进入回收站，不要默认永久删除。
- GUI 不要打印完整 token、key、SSH 私钥或认证 JSON。
- 改 UI 后至少运行测试，必要时用 `python scripts/capture_ui_snapshots.py` 生成截图检查。
