@echo off
REM ===========================================================================
REM  BUILD-EXE.bat  -  makes dist\T-Amp\T-Amp.exe and a Desktop shortcut to it.
REM
REM  Run RUN.bat once first (it sets up .venv). The .exe folder is
REM  self-contained: Python, Qt, ffmpeg and the JavaScript runtime are inside.
REM ===========================================================================
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo   [X] Run RUN.bat once first - it sets up the Python environment.
    pause & exit /b 1
)
echo   [1/3] PyInstaller...
".venv\Scripts\python.exe" -m pip install -q pyinstaller
if errorlevel 1 ( echo   [X] PyInstaller install failed & pause & exit /b 1 )

echo   [2/3] Building T-Amp.exe (a few minutes)...
".venv\Scripts\python.exe" build.py
if errorlevel 1 ( echo   [X] Build failed - see the messages above & pause & exit /b 1 )

echo   [3/3] Desktop shortcut...
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\T-Amp.lnk'); $s.TargetPath='%~dp0dist\T-Amp\T-Amp.exe'; $s.WorkingDirectory='%~dp0dist\T-Amp'; $s.IconLocation='%~dp0dist\T-Amp\T-Amp.exe,0'; $s.Save()"
echo.
echo   Done: dist\T-Amp\T-Amp.exe  (and T-Amp on your Desktop)
pause
