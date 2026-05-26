@echo off
set "ROOT=%~dp0.."
cd /d "%ROOT%"
start "" /D "%ROOT%" pythonw.exe style_lab.py
exit /b 0
