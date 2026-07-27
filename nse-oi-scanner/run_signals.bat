@echo off
REM Everything in ONE webpage: OI buildup + option chain + 1 CE / 1 PE / 1 Future
REM (with annotated charts) + RRG. Builds report.html and opens it in your browser.
cd /d "%~dp0"
set "MODE="
if not exist "access_token.txt" (
    set "MODE=--dry-run"
    echo [i] No Fyers token found - building the DEMO page. Run "Fyers Login" for live data.
)
python report.py %MODE%
echo.
echo If the page did not open, double-click  report.html  in this folder.
pause
