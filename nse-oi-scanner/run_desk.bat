@echo off
REM The dashboard: regime, today's ticket, the names behind it, charts, paper score.
REM Opens in the browser at localhost:8501. Close this window to stop it.
cd /d "%~dp0"
python -c "import streamlit" 2>nul
if errorlevel 1 (
    echo   Streamlit nahi hai - install kar raha hoon, ek baar ka kaam...
    python -m pip install -q streamlit plotly
)
echo.
echo   Browser khul jayega. Band karne ke liye ye window band kar de.
echo.
streamlit run desk.py
pause
