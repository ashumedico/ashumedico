@echo off
REM PANIC / KILL SWITCH. Creates STOP_TRADING.txt -> the auto-trader halts immediately
REM and (in live mode) stops opening new positions.
cd /d "%~dp0"
echo halt requested %date% %time% > STOP_TRADING.txt
echo.
echo ================================================
echo   TRADING HALTED. STOP_TRADING.txt created.
echo   The auto-trader will stop on its next check.
echo   To resume later: delete STOP_TRADING.txt
echo ================================================
pause
