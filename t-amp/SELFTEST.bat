@echo off
REM Checks every part with real data: ffmpeg, the JavaScript runtime, your speakers,
REM a live YouTube Music search, a stream, 3 s of decoded audio, and 3 s played aloud.
cd /d "%~dp0"
if exist "%APPDATA%\T-Amp\selftest.txt" del "%APPDATA%\T-Amp\selftest.txt"
if exist "dist\T-Amp\T-Amp.exe" (
    start /wait "" "dist\T-Amp\T-Amp.exe" --selftest
    type "%APPDATA%\T-Amp\selftest.txt"
) else (
    ".venv\Scripts\python.exe" -m tamp --selftest
)
echo.
pause
