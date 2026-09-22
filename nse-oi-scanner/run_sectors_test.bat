@echo off
REM Sector membership correlation se nikalta hai - ye check karta hai ki wo sahi nikalta hai.
cd /d "%~dp0"
python test_sectors.py
echo.
pause
