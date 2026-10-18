@echo off
REM You exited. Tell it the name and the price, and the trade moves to the scorecard.
cd /d "%~dp0"
echo.
set /p NAME=  Kis stock se nikla (naam likh, jaise COFORGE):
if "%NAME%"=="" (
    echo   Naam chahiye. Dobara chala.
    pause
    exit /b
)
echo.
echo   Aadha becha hai toh AADHA likh, poora becha toh ENTER daba:
set /p HALF=  ^>
echo.
if /i "%HALF%"=="AADHA" (
    python checkin.py --sold %NAME% --half
) else (
    python checkin.py --sold %NAME%
)
echo.
pause
