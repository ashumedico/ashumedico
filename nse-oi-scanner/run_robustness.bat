@echo off
REM Robustness suite: tries to DISPROVE the edge before you trade it.
REM Out-of-sample + cost sensitivity + regime gate + parameter stability.
cd /d "%~dp0"
if not exist "access_token.txt" (
    echo [i] No Fyers token - running DEMO ^(mechanics only^).
    python robustness.py --demo
) else (
    echo Fetching history. This takes a few minutes the first time.
    python robustness.py --days 400
)
pause
