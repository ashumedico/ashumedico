@echo off
REM Updates SECRET_KEY in config.py after regenerating it on the Fyers dashboard.
REM Prompted, not typed as an argument - a command line survives in history and in
REM screenshots long after the secret should have stopped existing anywhere.
cd /d "%~dp0"
echo.
echo   Fyers dashboard pe Secret regenerate karne ke baad, naya secret yahan daal.
echo   config.py ka backup apne aap ban jayega.
echo.
python configure.py --secret
echo.
pause
