@echo off
REM ===========================================================================
REM  BUILD-EXE.bat  —  makes "AASHISH TRADING OS.exe" and puts it on the Desktop.
REM
REM  Ek baar chalana hai. Iske baad Desktop pe ek .exe hoga jise double-click
REM  karke poora system khulta hai - login, self-test, engine, desk, kill switch.
REM
REM  Ye .exe launcher hai, poora system nahi: code isi folder se chalta hai.
REM  Matlab '0 - UPDATE' se code update karo, .exe waisa ka waisa kaam karega -
REM  dobara build karne ki zaroorat nahi.
REM ===========================================================================
cd /d "%~dp0"
title BUILD - AASHISH TRADING OS.exe
echo.
echo   ================================================================
echo    AASHISH TRADING OS  -  .exe bana raha hoon
echo   ================================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo   [X] Python nahi mila. python.org se install kar, "Add to PATH" tick karke.
    echo.
    pause & exit /b 1
)

python -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo   [X] tkinter nahi hai. Python installer dobara chala aur
    echo       "tcl/tk and IDLE" wala box tick kar.
    echo.
    pause & exit /b 1
)

echo   [1/4] PyInstaller check...
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo         nahi hai - install kar raha hoon, ek baar ka kaam...
    python -m pip install -q pyinstaller
    if errorlevel 1 (
        echo   [X] PyInstaller install nahi hua. Internet check kar.
        echo.
        pause & exit /b 1
    )
)

echo   [2/4] Purana build saaf kar raha hoon...
if exist "build" rmdir /s /q "build"
if exist "dist"  rmdir /s /q "dist"
if exist "AASHISH TRADING OS.spec" del /q "AASHISH TRADING OS.spec"

echo   [3/4] Build chal raha hai (2-3 minute lagenge, window band mat kar)...
echo.
REM  --onefile     : ek hi .exe, koi folder nahi
REM  --noconsole   : sirf window dikhe, kaala console nahi
REM  --icon        : Desktop pe pehchana jaye
REM  Sirf launcher package hota hai. Baaki code folder se chalta hai, isliye
REM  update karne pe dobara build nahi karna padta.
python -m PyInstaller --onefile --noconsole --clean ^
    --name "AASHISH TRADING OS" ^
    --icon "tbone.ico" ^
    --distpath "dist" ^
    launcher.py
if errorlevel 1 (
    echo.
    echo   [X] Build fail. Upar ka red text copy karke bhej de.
    echo.
    pause & exit /b 1
)

echo.
echo   [4/4] Desktop pe rakh raha hoon...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$d=[Environment]::GetFolderPath('Desktop');" ^
  "if(-not (Test-Path $d)){$d=Join-Path $env:USERPROFILE 'Desktop'}" ^
  "$f=Join-Path $d 'AASHISH TRADING OS';" ^
  "if(-not (Test-Path $f)){New-Item -ItemType Directory -Path $f | Out-Null}" ^
  "Copy-Item 'dist\AASHISH TRADING OS.exe' $f -Force;" ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'AASHISH TRADING OS.lnk'));" ^
  "$s.TargetPath=(Join-Path $f 'AASHISH TRADING OS.exe');" ^
  "$s.WorkingDirectory='%~dp0';" ^
  "$s.Description='Trading OS - launcher';" ^
  "$s.Save();" ^
  "Write-Host ('   [OK] ' + (Join-Path $f 'AASHISH TRADING OS.exe'))"

echo.
echo   ================================================================
echo   [OK] Ho gaya.
echo.
echo    Desktop pe:  AASHISH TRADING OS  (icon)
echo    Folder mein: AASHISH TRADING OS\AASHISH TRADING OS.exe
echo.
echo    Double-click kar. Pehli baar:
echo      1. Fyers Client ID + Secret bhar
echo      2. "1  Fyers login" daba
echo      3. "Self-test" daba - sab OK hona chahiye
echo      4. "START ENGINE"
echo.
echo    .exe ko dobara build karne ki zaroorat nahi - code
echo    '0 - UPDATE' se update hota rahega.
echo   ================================================================
echo.
pause
