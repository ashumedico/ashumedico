@echo off
REM You took the trade the check-in suggested. This records it, so the next check-in
REM knows what you hold and grades it against the live price instead of asking you.
cd /d "%~dp0"
echo.
echo   Aaj ka suggested trade book mein daal raha hoon...
echo.
python checkin.py --buy
echo.
pause
