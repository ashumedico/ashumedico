@echo off
REM Check the F&O lot size of EVERY name against its live price.
REM A wrong lot makes the quantity - and the risk figure - meaningless, and it stays
REM invisible until that name happens to be the trade. So check them all at once.
REM Flagged names are then re-read from the live option chain, which is the exchange's
REM own number and survives splits.
cd /d "%~dp0"
if not exist "access_token.txt" (
    echo [i] No Fyers token - running the DEMO audit ^(mechanics only^).
    echo     For the real audit: run "1 - Fyers Login" first.
    python lot_audit.py --demo
) else (
    python lot_audit.py --repair
)
pause
