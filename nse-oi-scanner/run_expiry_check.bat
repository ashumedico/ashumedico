@echo off
REM Which expiry is actually the cheapest for the way you trade?
REM Near expiry is cheaper and more levered but decays fast; far expiry costs premium and
REM is illiquid. This shows how far the STOCK has to move, at each expiry, before the
REM option has paid for its own decay and spread. Lowest number wins.
cd /d "%~dp0"
python option_pnl.py --sweep-dte
echo.
echo   ================================================================
echo   Ye tere config (BAR_MINUTES, HOLD_BARS) ke hisaab se nikla hai.
echo   Hold badla toh sahi expiry bhi badlegi - dobara chala lena.
echo   ================================================================
echo.
pause
