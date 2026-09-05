@echo off
REM What implied-vol history has been collected. A true IV RANK needs ~60 observations
REM per name; until then the desk shows IV against realised vol instead of a percentile
REM computed from almost nothing.
cd /d "%~dp0"
python iv_history.py
echo.
pause
