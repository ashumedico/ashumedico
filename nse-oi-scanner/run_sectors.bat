@echo off
REM Sector feed probe - kaunse index symbols asli mein resolve hote hain.
REM Jo resolve nahi hota wo heatmap mein aata hi nahi, zero bhar ke nahi dikhaya jaata.
cd /d "%~dp0"
title SECTOR FEED - probe
python sectors.py
echo.
pause
