@echo off
REM Does the OPTION earn the order, or only the stock? Checks the measured spread,
REM the liquidity floors, implied-vs-realised vol, and that the stock-to-option
REM translation cannot return a loss bigger than the premium.
cd /d "%~dp0"
python test_option_quality.py
echo.
pause
