@echo off
REM The ablation: turn each filter OFF one at a time and see what it was actually worth.
REM This is the test that killed the RRG (-6.3% after costs). Takes a few minutes.
cd /d "%~dp0"
title ABLATION - kaunsa filter sach mein kaam karta hai
echo.
echo   Har filter ko alag-alag OFF karke test karta hoon.
echo   NOT TESTED aur FAILED alag cheezein hain - dono alag dikhengi.
echo.
python hypothesis.py --days 900
echo.
echo   Report: hypothesis_report.txt
echo.
pause
