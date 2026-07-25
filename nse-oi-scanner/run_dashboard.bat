@echo off
REM NSE F&O OI-Change Scanner dashboard (http://localhost:8501)
cd /d "%~dp0"
streamlit run app.py
pause
