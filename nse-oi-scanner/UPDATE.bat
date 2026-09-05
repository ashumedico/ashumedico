@echo off
REM Pulls the latest code AND refreshes the Desktop icons in one go.
REM Doing only the pull left new launchers invisible until a second, separate command was
REM run - which is exactly the kind of hidden step this folder exists to remove.
cd /d "%~dp0"
echo.
echo   Naya code laa raha hoon...
echo.
git pull origin claude/aios-v2-scaffolder-warqsk
if errorlevel 1 (
    echo.
    echo   [X] Pull nahi hua. Internet check kar, ya screenshot bhej de.
    echo.
    pause
    exit /b 1
)
echo.
echo   Config mein naye settings add kar raha hoon (purane values chhede bina)...
echo.
REM New releases add config keys. Without this the new code reads a key that is not there,
REM falls back to a default, and behaves differently from what the screen says it is doing.
python upgrade_config.py

echo.
echo   Icons refresh kar raha hoon...
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0create_desktop_shortcuts.ps1"
echo.
echo   ================================================================
echo   [OK] Code aur icons dono update ho gaye.
echo   Ab Desktop pe "AASHISH TRADING OS" folder khol.
echo   ================================================================
echo.
pause
