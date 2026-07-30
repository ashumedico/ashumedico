@echo off
REM AASHISH TRADING OS — the RRG auto-trader app (main window = RRG).
cd /d "%~dp0"
echo Starting Aashish Trading OS...
echo Your browser will open at http://localhost:8501
echo Close this window to stop the app.
python -m streamlit run rrg_app.py
pause
