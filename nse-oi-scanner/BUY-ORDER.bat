@echo off
REM Places an order through Fyers API Connect - the browser route, which does not care
REM about the IP whitelist because the order leaves Fyers' own servers, not this machine.
cd /d "%~dp0"
echo.
set /p NAME=  Stock ka naam (jaise SONACOMS):
set /p STRIKE=  Strike (jaise 750):
set /p CEPE=  CE ya PE:
set /p MON=  Expiry month (jaise AUG, khaali chhod = sabse nazdeek):
echo.
if "%MON%"=="" (
    python order_page.py --buy %NAME% --strike %STRIKE% --type %CEPE%
) else (
    python order_page.py --buy %NAME% --strike %STRIKE% --type %CEPE% --month %MON%
)
echo.
echo   Browser khul gaya hoga - wahan saare numbers dekh ke Buy dabana.
echo.
pause
