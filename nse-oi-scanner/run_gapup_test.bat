@echo off
REM The Chartink gap-up filter, rebuilt here. This checks it still MEANS the same thing:
REM the SMA window ends yesterday, the band edges are strict, and a clause that cannot
REM be evaluated fails rather than being skipped.
cd /d "%~dp0"
python test_gapup.py
echo.
pause
