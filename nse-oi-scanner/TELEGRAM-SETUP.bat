@echo off
REM One-time Telegram alert setup. Discovers your chat id automatically,
REM writes config.py for you, and sends a test message.
cd /d "%~dp0"
python setup_telegram.py
if errorlevel 1 (
    echo.
    echo  Kuch atka. Upar ka message padh aur dobara chala.
    pause & exit /b 1
)
echo.
echo  Ab schedule bhi laga du? koi bhi key dabao...
pause >nul
schtasks /Create /TN "AashishTradingWatchdog_Mid"   /TR "cmd /c cd /d \"%~dp0\" && python alert_watch.py" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 12:30 /F
schtasks /Create /TN "AashishTradingWatchdog_Close" /TR "cmd /c cd /d \"%~dp0\" && python alert_watch.py" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 15:10 /F
echo.
echo ============================================================
echo  SAB HO GAYA.
echo  Roz 12:30 aur 15:10 pe khud check karega.
echo  Message SIRF tab aayega jab kuch karna ho.
echo ============================================================
pause
