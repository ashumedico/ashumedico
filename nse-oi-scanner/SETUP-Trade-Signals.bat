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
echo === Creating your 4 desktop icons ===
powershell -NoProfile -ExecutionPolicy Bypass -File "create_desktop_shortcuts.ps1"

echo.
echo ============================================================
echo  DONE. Look at your Desktop for 4 icons:
echo    - Fyers Login          (get today's token first)
echo    - NSE OI Scanner
echo    - OI Scanner Board     (dashboard at localhost:8501)
echo    - Trade Signals + RRG  (1 CE + 1 PE + 1 Future + charts + RRG)
echo.
echo  First run: add your Fyers keys once ->  python setup.py
echo ============================================================
pause
