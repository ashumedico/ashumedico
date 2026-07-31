@echo off
REM Full-session paper trading. Wakes at every candle close, marks open trades, exits on
REM stop/T1/T2/timeout, enters when flat, and squares off before the close.
REM This window must stay open - close it and the trader stops. Book is never lost.
cd /d "%~dp0"
if not exist "access_token.txt" (
    echo.
    echo   Token nahi hai. Pehle "1 - Fyers Login" chala.
    echo   Filhaal DEMO pe dikha raha hoon ki kaise chalta hai.
    echo.
    python paper.py --session --demo
) else (
    python paper.py --session
)
echo.
pause
