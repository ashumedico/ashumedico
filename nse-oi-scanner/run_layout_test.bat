@echo off
REM Does the desk FIT your 21-inch screen? Drives a real browser at 1920x940, clicks
REM through all five tabs and measures how far each one runs past one screen.
REM Every other test asks whether an element exists; only this one asks whether you
REM can SEE it. Needs playwright + a chromium: python -m playwright install chromium
cd /d "%~dp0"
python -c "import playwright" 2>nul
if errorlevel 1 python -m pip install -q playwright && python -m playwright install chromium
python test_layout.py
echo.
pause
