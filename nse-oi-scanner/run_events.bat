@echo off
REM The results calendar. Implied vol rises into a results date and collapses after it -
REM the stock can move exactly as predicted and the option still loses. Until a date is
REM on file, every ticket says event risk was NOT CHECKED, which is deliberate: an empty
REM calendar cannot clear a name.
REM   Add one:  python events.py --add RELIANCE 2026-08-14 results
cd /d "%~dp0"
python events.py
echo.
echo   Add a date:  python events.py --add NAME YYYY-MM-DD results
echo   Try NSE:     python events.py --refresh
echo.
pause
