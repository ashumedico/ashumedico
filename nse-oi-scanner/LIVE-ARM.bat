@echo off
REM Arms or disarms REAL order placement. Deliberately not a one-click toggle: it shows
REM the current state first and makes you type HAAN, because the difference between this
REM being on and off is real money leaving the account without another confirmation.
cd /d "%~dp0"
python broker.py --status
echo.
echo   1 = LIVE chalu karo (asli order lagenge)
echo   2 = LIVE band karo  (sirf paper)
echo   koi aur = kuch mat badlo
echo.
set /p PICK=  ^>
if "%PICK%"=="1" python broker.py --arm
if "%PICK%"=="2" python broker.py --disarm
echo.
pause
