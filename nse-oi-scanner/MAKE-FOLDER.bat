@echo off
REM ============================================================
REM  MAKE-FOLDER.bat  -  builds the "AASHISH TRADING OS" desktop
REM  folder and reports exactly what happens at each step.
REM  Run this if the folder did not appear.
REM ============================================================
cd /d "%~dp0"
echo.
echo ============================================================
echo   Building your Desktop folder
echo ============================================================
echo Running from: %CD%
echo.

if not exist "create_desktop_shortcuts.ps1" (
    echo [X] create_desktop_shortcuts.ps1 is MISSING from this folder.
    echo     The code is out of date. Run SETUP-Trade-Signals.bat first,
    echo     or in this folder run:   git pull origin claude/aios-v2-scaffolder-warqsk
    echo.
    pause & exit /b 1
)

echo --- Step 1: checking which launchers exist here ---
for %%F in (run_login.bat run_rrg_app.bat run_signals.bat run_autotrader.bat run_sweep.bat run_scanner.bat STOP-TRADING.bat) do (
    if exist "%%F" (echo   [ok]      %%F) else (echo   [MISSING] %%F)
)
echo.

echo --- Step 2: creating the folder + shortcuts ---
powershell -NoProfile -ExecutionPolicy Bypass -File "create_desktop_shortcuts.ps1"
if errorlevel 1 (
    echo.
    echo [X] PowerShell reported an error above. Copy that red text and send it.
    echo.
    pause & exit /b 1
)

echo.
echo --- Step 3: verifying what actually landed on the Desktop ---
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$d=[Environment]::GetFolderPath('Desktop'); $f=Join-Path $d 'AASHISH TRADING OS'; if(Test-Path $f){ Write-Host \"[OK] Folder exists: $f\"; Get-ChildItem $f | ForEach-Object { Write-Host ('   - ' + $_.Name) } } else { Write-Host \"[X] Not found at $d\" }"

echo.
echo ============================================================
echo  If you see [OK] above, open that folder on your Desktop.
echo  If the Desktop path shown is inside OneDrive, the folder is
echo  in your OneDrive Desktop - same thing, it syncs.
echo ============================================================
pause
