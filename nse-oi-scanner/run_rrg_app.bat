@echo off
REM AASHISH TRADING OS - the RRG auto-trader app (main window = RRG).
REM Self-healing: makes sure every dependency is present before launching.
cd /d "%~dp0"

echo Checking dependencies...
python -c "import streamlit, plotly, matplotlib, numpy, pandas" 2>nul
if errorlevel 1 (
    echo Installing missing packages ^(one time, ~1 min^)...
    python -m pip install -q -r requirements.txt
    python -c "import streamlit, plotly, matplotlib, numpy, pandas" 2>nul
    if errorlevel 1 (
        echo.
        echo [X] Some packages still missing. Run this and send me the error:
        echo     python -m pip install -r requirements.txt
        echo.
        pause & exit /b 1
    )
)

echo Starting Aashish Trading OS...
echo Your browser will open at http://localhost:8501
echo Close this window to stop the app.
python -m streamlit run rrg_app.py
pause
