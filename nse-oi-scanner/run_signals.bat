@echo off
REM Revalidated trade signals + 3 annotated charts (1 CE, 1 PE, 1 Future).
REM 3-layer confluence: OI buildup x option chain x chart action.
cd /d "%~dp0"
echo === 1 CE + 1 PE + 1 Future  (3-layer confluence + annotated charts) ===
python charts.py
echo.
echo === Relative Rotation Graph (leading / lagging vs NIFTY) ===
python rrg.py
echo.
echo Opening the charts folder...
if exist charts start "" "charts"
pause
