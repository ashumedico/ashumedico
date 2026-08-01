@echo off
REM Does the F&O list know where it came from? A cache with no expiry is used forever,
REM and every name NSE added since is then invisible on every screen - a missing name
REM looks exactly like a name that did not qualify.
cd /d "%~dp0"
python test_universe.py
echo.
pause
