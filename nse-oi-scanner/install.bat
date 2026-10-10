@echo off
REM One-click: puts the 3 scanner icons on your Windows desktop.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "create_desktop_shortcuts.ps1"
pause
