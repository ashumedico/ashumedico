@echo off
REM Registers Windows tasks so paper trading runs by itself through the session.
REM Five checkpoints: after the opening candles settle, twice midday, before the close,
REM and a final mark at 15:20 so nothing is left unmarked overnight.
cd /d "%~dp0"
echo.
echo   ================================================================
echo    PAPER TRADING - ROZ APNE AAP
echo   ================================================================
echo.
echo   Ye 5 baar chalega har trading din:
echo       09:45   pehli candles settle hone ke baad
echo       11:15   midday
echo       13:00   midday
echo       14:45   band hone se pehle
echo       15:20   aakhri mark
echo.
echo   ZAROORI: Fyers token roz expire hota hai. Subah ek baar
echo   "1 - Fyers Login" chalana padega, warna run miss ho jayega
echo   (log mein saaf likha aayega ki miss hua).
echo.
pause

schtasks /Create /TN "AashishPaper_0945" /TR "cmd /c \"%~dp0run_paper_auto.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 09:45 /F
schtasks /Create /TN "AashishPaper_1115" /TR "cmd /c \"%~dp0run_paper_auto.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 11:15 /F
schtasks /Create /TN "AashishPaper_1300" /TR "cmd /c \"%~dp0run_paper_auto.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 13:00 /F
schtasks /Create /TN "AashishPaper_1445" /TR "cmd /c \"%~dp0run_paper_auto.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 14:45 /F
schtasks /Create /TN "AashishPaper_1520" /TR "cmd /c \"%~dp0run_paper_auto.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 15:20 /F

echo.
echo   ================================================================
echo   [OK] Paper trading ab apne aap chalega.
echo.
echo   Score dekhna ho:  icon "2c - PAPER TRADE"
echo   Band karna ho:    is folder mein STOP-PAPER.bat chala
echo   ================================================================
echo.
pause
