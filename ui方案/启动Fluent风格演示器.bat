@echo off
set "ROOT=%~dp0.."
cd /d "%ROOT%"
start "" /D "%ROOT%" "D:\code\YuYan\python\pythonw.exe" "%ROOT%\style_demo_fluent.py"
exit /b 0
