@echo off
setlocal
cd /d "%~dp0"
start "" /D "%~dp0" "D:\code\YuYan\python\pythonw.exe" "%~dp0app_fluent.py"
exit /b 0
