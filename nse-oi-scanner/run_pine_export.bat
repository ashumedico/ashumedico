@echo off
REM Aaj ke scan ke naam -> TradingView ke liye Pine file + watchlist.
REM Screener ke default 20 naam maine chune the; ye wale system ne chune hain.
cd /d "%~dp0"
title CHART LIST - aaj ke naam
python pine_export.py
echo.
echo   Files:  tradingview\AashishScreener_live.pine
echo           tradingview\watchlist.txt
echo.
pause
