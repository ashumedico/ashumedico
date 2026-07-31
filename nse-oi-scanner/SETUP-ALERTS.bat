@echo off
REM Registers a Windows task so the watchdog checks your positions by itself
REM and pings Telegram only when a decision is due.
cd /d "%~dp0"

echo.
echo ============================================================
echo   TELEGRAM ALERTS SETUP
echo ============================================================
echo.
echo  Pehle Telegram pe ye 2 min ka kaam:
echo    1. Telegram kholo, search:  @BotFather
echo    2. Bhejo:  /newbot   - naam kuch bhi rakho
echo    3. Woh ek TOKEN dega - copy kar lo
echo    4. Search:  @userinfobot  - usse /start - woh tumhara ID dega
echo    5. config.py mein daalo:
echo         TELEGRAM_TOKEN = "yahan token"
echo         TELEGRAM_CHAT  = "yahan id"
echo.
echo  Ho gaya? koi bhi key dabao...
pause >nul

echo.
echo === Telegram test ===
python alert_watch.py --test
echo.
echo  Phone pe message aaya? agar NAHI to token/id dobara check karo.
echo  Aaya? koi bhi key dabao - schedule laga deta hoon.
pause >nul

echo.
echo === Roz ka schedule laga raha hoon ===
schtasks /Create /TN "AashishTradingWatchdog_Mid" /TR "cmd /c cd /d \"%~dp0\" && python alert_watch.py" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 12:30 /F
schtasks /Create /TN "AashishTradingWatchdog_Close" /TR "cmd /c cd /d \"%~dp0\" && python alert_watch.py" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 15:10 /F

echo.
echo ============================================================
echo  HO GAYA. Ab roz 12:30 aur 15:10 pe khud check karega.
echo  Message SIRF tab aayega jab kuch karna ho.
echo.
echo  Band karna ho to:
echo    schtasks /Delete /TN "AashishTradingWatchdog_Mid" /F
echo    schtasks /Delete /TN "AashishTradingWatchdog_Close" /F
echo ============================================================
pause
