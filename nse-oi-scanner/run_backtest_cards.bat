@echo off
REM Jo cards system chhapta hai, unka asli hisaab - option premium, charges, stop/T1/T2,
REM trail, timeout. Exit engine wahi hai jo live chalta hai.
cd /d "%~dp0"
title SUGGESTIONS KA BACKTEST
python backtest_cards.py --days 900
echo.
pause
