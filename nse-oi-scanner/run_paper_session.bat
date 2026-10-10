@echo off
REM Full-session paper trading. Wakes at every candle close, marks open trades, exits on
REM stop/T1/T2/timeout, enters when flat, and squares off before the close.
REM This window must stay open - close it and the trader stops. Book is never lost.
cd /d "%~dp0"
if not exist "logs" mkdir "logs"
REM A lock so START-DAY cannot spawn a second trader on top of a running one - two
REM sessions would both act on the same book and double every entry.
echo %DATE% %TIME% > "logs\session.lock"
if not exist "access_token.txt" (
    echo.
    echo   Token nahi hai. Pehle "1 - Fyers Login" chala.
    echo   Filhaal DEMO pe dikha raha hoon ki kaise chalta hai.
    echo.
    python paper.py --session --demo
) else (
    python paper.py --session
)
del "logs\session.lock" 2>nul
echo.
pause
