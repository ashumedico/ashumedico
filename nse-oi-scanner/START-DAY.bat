@echo off
REM One click for the whole day. Login, then everything that follows starts by itself.
REM
REM Order matters. The token comes first because nothing else works without it, then the
REM lot audit (once a day, cheap, and a wrong lot poisons every quantity), then the
REM session trader in its own window, and finally the check-in in this one so the first
REM thing on screen is the decision.
cd /d "%~dp0"
title AASHISH TRADING OS - start of day

echo.
echo   ================================================================
echo    START OF DAY
echo   ================================================================
echo.
echo   [1/4] Fyers login...
echo.
python fyers_auth.py
if not exist "access_token.txt" (
    echo.
    echo   [X] Token nahi bana - login poora nahi hua.
    echo       Bina token ke aage kuch nahi chalega. Dobara chala.
    echo.
    pause
    exit /b 1
)

echo.
echo   [2/4] Lot sizes check kar raha hoon...
echo.
python lot_audit.py --repair

echo.
echo   [3/4] Paper trader chalu kar raha hoon (alag window mein)...
if exist "logs\session.lock" (
    echo         Ek session pehle se chal raha hai - naya nahi khol raha.
    echo         Agar wo band ho gaya tha, logs\session.lock delete kar de.
) else (
    if not exist "logs" mkdir "logs"
    start "PAPER TRADER - chalne do" cmd /c ""%~dp0run_paper_session.bat""
    echo         Chalu. Us window ko band mat karna.
)

echo.
echo   [4/4] Aaj ka check-in...
echo.
python checkin.py

echo.
echo   ================================================================
echo   Sab chalu hai. Paper trader alag window mein chal raha hai.
echo   Website dekhni?  ->  "3 - DESK"        Check-in?  ->  "2 - CHECK-IN"
echo   Trade le liya?   ->  Tools\LIYA        Nikal gaya?  ->  Tools\NIKLA
echo   ================================================================
echo.
pause
