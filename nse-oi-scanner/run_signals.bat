@echo off
REM Revalidated trade signals + 3 annotated charts (1 CE, 1 PE, 1 Future).
REM 3-layer confluence: OI buildup x option chain x chart action.
cd /d "%~dp0"
REM No Fyers token yet? show the demo (dry-run) so you still see charts.
set "MODE="
if not exist "access_token.txt" (
    set "MODE=--dry-run"
    echo [i] No Fyers token found - showing DEMO charts. Run "Fyers Login" for live signals.
)
echo === 1 CE + 1 PE + 1 Future  (3-layer confluence + annotated charts) ===
python charts.py %MODE%
echo.
echo === Relative Rotation Graph (leading / lagging vs NIFTY) ===
python rrg.py %MODE%
echo.
echo Opening the charts folder...
if exist charts start "" "charts"
pause
