@echo off
REM Paper trading. Takes today's signal, marks open paper trades against live prices,
REM and scores the book against what the backtest claimed. No real order is ever placed.
cd /d "%~dp0"
if not exist "access_token.txt" (
    echo   [i] Token nahi hai - DEMO data pe chala raha hoon.
    echo       Asli paper trade ke liye pehle "1 - Fyers Login" chala.
    echo.
    python paper.py --demo
) else (
    python paper.py
)
echo.
pause
