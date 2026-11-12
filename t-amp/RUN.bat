@echo off
REM ===========================================================================
REM  RUN.bat  -  opens T-Amp, the classic player for YouTube Music.
REM
REM  First run sets up T-Amp's own Python environment in .venv (2-3 minutes,
REM  one time). After that it opens straight away. Needs Python 3.10+.
REM ===========================================================================
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    python --version >nul 2>&1
    if errorlevel 1 (
        echo   [X] Python not found. Install it from python.org with "Add to PATH" ticked.
        pause & exit /b 1
    )
    echo   First run: setting up T-Amp's Python environment...
    python -m venv .venv
    if errorlevel 1 (
        echo   [X] Could not create .venv
        pause & exit /b 1
    )
)

REM Install or refresh packages whenever requirements.txt changed since the last install.
fc /b requirements.txt ".venv\requirements.installed" >nul 2>&1
if errorlevel 1 (
    echo   Installing T-Amp's packages...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo   [X] Package install failed - check the internet connection and run again.
        pause & exit /b 1
    )
    copy /y requirements.txt ".venv\requirements.installed" >nul
)

start "" ".venv\Scripts\pythonw.exe" "%~dp0T-Amp.pyw"
