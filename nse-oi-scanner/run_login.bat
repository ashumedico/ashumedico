@echo off
REM Refresh daily Fyers access token  (your Fyers_Login shortcut points here)
cd /d "%~dp0"
python fyers_auth.py
pause
