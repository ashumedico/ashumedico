@echo off
REM Launch NSE F&O OI-Change Options Scanner  (your NSE_Options_Scanner shortcut points here)
cd /d "%~dp0"
python scanner.py --loop
pause
