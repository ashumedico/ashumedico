@echo off
REM Proves the launcher window builds and its wiring is real - config round-trip,
REM kill switch, masked secrets, and that the engine refuses to start while halted.
cd /d "%~dp0"
python test_launcher.py
echo.
pause
