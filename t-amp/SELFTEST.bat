@echo off
REM Checks every part with real data: ffmpeg, the JavaScript runtime, your speakers,
REM a live YouTube Music search, a stream, and 3 seconds of decoded audio.
cd /d "%~dp0"
if exist "dist\T-Amp\T-Amp.exe" (
    start /wait "" "dist\T-Amp\T-Amp.exe" --selftest
    type "%APPDATA%\T-Amp\selftest.txt"
) else (
    ".venv\Scripts\python.exe" -m tamp --selftest
)
echo.
pause
