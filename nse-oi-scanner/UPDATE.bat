@echo off
REM Pulls the latest code. This is the only thing that ever needs the internet and git,
REM and it exists so that updating never means typing a git command by hand.
cd /d "%~dp0"
echo.
echo   Naya code laa raha hoon...
echo.
git pull origin claude/aios-v2-scaffolder-warqsk
if errorlevel 1 (
    echo.
    echo   [X] Pull nahi hua. Internet check kar, ya screenshot bhej de.
) else (
    echo.
    echo   [OK] Update ho gaya.
    echo.
    echo   Agar naye icon chahiye, ye bhi chala:
    echo       powershell -ExecutionPolicy Bypass -File "%~dp0create_desktop_shortcuts.ps1"
)
echo.
pause
