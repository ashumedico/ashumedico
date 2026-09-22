@echo off
REM Proves the website actually renders - banner, ribbon, levels, all three scenarios.
REM Runs on synthetic data, so it works with no token and no market open.
cd /d "%~dp0"
python -c "import streamlit" 2>nul
if errorlevel 1 python -m pip install -q streamlit plotly
python test_desk.py
echo.
pause
