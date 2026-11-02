@echo off
REM Every number on a ticket must agree with every other one: stop on the losing side of
REM ENTRY, targets in order, and the printed R:R equal to the real one at that entry.
cd /d "%~dp0"
python test_card_math.py
echo.
pause
