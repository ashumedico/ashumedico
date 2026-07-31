@echo off
REM ============================================================
REM  ONE-CLICK SETUP  —  Trade Signals + RRG desktop icons
REM  Save this file to your Desktop, then double-click it.
REM  It fetches the latest scanner code and drops 4 icons for you.
REM ============================================================
setlocal
set "REPO=https://github.com/ashumedico/ashumedico.git"
set "BRANCH=claude/aios-v2-scaffolder-warqsk"
set "DIR=C:\claude-scanner"

echo.
echo === Checking for git and python ===
where git  >nul 2>&1 || (echo [X] git is not installed. Install Git for Windows from https://git-scm.com/download/win then run me again. & pause & exit /b 1)
where python >nul 2>&1 || (echo [X] python is not installed. Install Python from https://python.org then run me again. & pause & exit /b 1)

echo.
echo === Getting the latest scanner code into %DIR% ===
if exist "%DIR%\.git" (
    cd /d "%DIR%"
    git fetch origin
) else (
    git clone "%REPO%" "%DIR%" || (echo [X] Clone failed. Check your internet / GitHub login. & pause & exit /b 1)
    cd /d "%DIR%"
)
git checkout "%BRANCH%"
git pull origin "%BRANCH%"

echo.
echo === Installing Python packages (matplotlib, numpy, etc.) ===
cd /d "%DIR%\nse-oi-scanner"
python -m pip install -r requirements.txt

echo.
echo === Creating your Desktop folder + launchers ===
powershell -NoProfile -ExecutionPolicy Bypass -File "create_desktop_shortcuts.ps1"

echo.
echo ============================================================
echo  DONE. One folder on your Desktop: "AASHISH TRADING OS"
echo  Open it - everything is inside, numbered in running order:
echo    1 - Fyers Login       (today's token - do this first)
echo    2 - RRG Trader        (the cockpit, localhost:8501)
echo    3 - Signal Desk       (one-page desk)
echo    4 - Auto-Trader       (hands-free, PAPER)
echo    5 - Find Best Setup   (backtest on your own data)
echo    6 - OI Scanner
echo    STOP - Kill Switch    (halt everything)
echo.
echo  First time only: add your Fyers keys ->  python setup.py
echo ============================================================
pause
