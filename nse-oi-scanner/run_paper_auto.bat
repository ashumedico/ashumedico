@echo off
REM Headless paper run, launched by the Windows scheduler. Never opens a window and never
REM waits for a keypress - it appends to a dated log so a missed run is visible afterwards
REM rather than silently absent.
cd /d "%~dp0"
if not exist "logs" mkdir "logs"
for /f "tokens=1-3 delims=/- " %%a in ("%DATE%") do set STAMP=%%c%%b%%a
echo. >> "logs\paper_%STAMP%.log"
echo ================ %DATE% %TIME% ================ >> "logs\paper_%STAMP%.log"
python paper.py >> "logs\paper_%STAMP%.log" 2>&1
