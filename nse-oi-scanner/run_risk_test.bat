@echo off
REM Proves the drawdown halt actually halts - at the floor, on entries only, and that
REM an unreadable ledger blocks instead of assuming today's loss was zero.
cd /d "%~dp0"
python test_risk_limits.py
echo.
pause
