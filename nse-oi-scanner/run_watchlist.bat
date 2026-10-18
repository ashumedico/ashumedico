@echo off
REM Q1 FY27 fundamental watchlist -> kaunse naam options mein trade ho sakte hain.
REM Sirf F&O naamo pe option milta hai; baaki cash-only hain.
cd /d "%~dp0"
title WATCHLIST - kya trade ho sakta hai
python watchlist.py --all
echo.
pause
