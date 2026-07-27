@echo off
REM Auto-trader. PAPER by default (safe). Live only if config.py LIVE_TRADING=True.
cd /d "%~dp0"
if exist "STOP_TRADING.txt" (
    echo [HALTED] STOP_TRADING.txt exists. Delete it (or use STOP-TRADING.bat menu) to resume.
    pause & exit /b
)
echo Starting auto-trader loop. Close this window OR run STOP-TRADING.bat to halt.
python auto_trader.py --loop
pause
