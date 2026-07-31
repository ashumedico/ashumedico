@echo off
REM THE one command. Run it whenever you sit down.
REM Shows: what to do with what you hold, and whether there is a new trade.
cd /d "%~dp0"
if not exist "access_token.txt" (
    echo.
    echo [!] Aaj ka Fyers token nahi hai. Pehle "1 - Fyers Login" chala.
    echo     Filhaal DEMO data dikha raha hoon.
    echo.
    python checkin.py --demo
) else (
    python checkin.py
)
echo.
echo   Trade le liya?  ->  icon  "2a - LIYA (bought)"
echo   Nikal gaya?     ->  icon  "2b - NIKLA (sold)"
echo.
pause
