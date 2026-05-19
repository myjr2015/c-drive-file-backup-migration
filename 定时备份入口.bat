@echo off
setlocal
cd /d "%~dp0"
"D:\code\YuYan\python\python.exe" backup_cli.py scheduled-backup --config "%~dp0data\schedule.json"

