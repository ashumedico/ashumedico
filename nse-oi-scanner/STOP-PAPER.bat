@echo off
REM Removes the scheduled paper-trading runs. The book itself is untouched - stopping the
REM schedule should never destroy the record it built.
schtasks /Delete /TN "AashishPaper_0945" /F 2>nul
schtasks /Delete /TN "AashishPaper_1115" /F 2>nul
schtasks /Delete /TN "AashishPaper_1300" /F 2>nul
schtasks /Delete /TN "AashishPaper_1445" /F 2>nul
schtasks /Delete /TN "AashishPaper_1520" /F 2>nul
echo.
echo   [OK] Automatic paper runs band. Book waise ka waisa hai -
echo        "2c - PAPER TRADE" se ab bhi score dikh jayega.
echo.
pause
