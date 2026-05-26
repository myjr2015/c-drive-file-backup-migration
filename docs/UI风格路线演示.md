# UI 风格路线演示

本项目新增 `style_lab.py`，用于在不改动正式界面 `app_fluent.py` 的前提下，对比多种 UI 技术路线的视觉语言。

## 演示包含的方案

- 当前 / Fluent Qt：PySide6 + qfluentwidgets，贴近当前正式软件。
- Web / shadcn + Tauri：模拟 Web 组件和 Tauri 桌面壳的视觉路线。
- Python / Flet + Flutter：模拟 Flutter/Material 取向的跨平台 Python UI。
- C# / Avalonia + Material：模拟 .NET/XAML 自绘桌面工具风格。
- Python / CustomTkinter：模拟轻量 Python 桌面工具风格。

## 启动方式

```powershell
python style_lab.py
```

或双击：

```text
ui方案\启动跨平台UI风格实验室.bat
```

如果需要更明显地比较各个 GitHub 开源项目的完整界面风格，优先打开：

```text
docs/github_style_gallery.html
```

或双击：

```text
ui方案\启动GitHub风格全景演示.bat
```

如果需要看每个项目“官方组件到底有哪些”，打开组件图库：

```text
docs/ui_components/index.html
```

或双击：

```text
ui方案\启动UI组件图库.bat
```

组件图库是一个 UI 一个网页，不再把所有项目塞在一个业务界面里。每页按组件类别展示：

- 官方定位
- 主题和字体
- 按钮
- 输入和选择
- 导航
- 数据展示
- 弹窗和反馈
- 布局容器

全景演示包含：

- shadcn/ui
- Tauri
- Avalonia UI
- Material Design In XAML
- Flet
- CustomTkinter
- Uno Platform
- PyQt-Fluent-Widgets

每个项目页都可以单独调节：

- 主题/风格：例如 Light、Dark、品牌色、Material 色种、Fluent Light/Dark。
- 字体：例如 Segoe UI、Inter、Roboto、微软雅黑 UI、Cascadia Mono。
- 按钮：例如默认描边、直角、圆角胶囊、扁平、悬浮。
- 导航：例如侧边栏、顶部标签、窄轨道、单页无导航。
- 布局：例如紧凑、标准、宽松、仪表盘纵向。

## 说明

这个演示器展示的是视觉风格和信息排版，不代表项目已经迁移到 Tauri、Flet、Avalonia 或 CustomTkinter。
正式软件仍以 PySide6 + qfluentwidgets 为主线维护。
