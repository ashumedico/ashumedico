@echo off
REM Find the BEST RRG setup on Aashish's own live data (walk-forward, no lookahead).
REM Writes rrg_best_setup.json — the app then trades whatever your data validated.
cd /d "%~dp0"
if not exist "access_token.txt" (
    echo [i] No Fyers token — running the DEMO sweep instead ^(mechanics only^).
    python rrg_strategy.py --demo
) else (
    echo Fetching history for the full F^&O universe. This takes a few minutes the first time.
    python rrg_strategy.py --sweep --days 400
)
pause
