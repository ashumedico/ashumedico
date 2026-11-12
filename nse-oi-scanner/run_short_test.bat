@echo off
REM Short book ka number - LONG only vs SHORT only vs BOTH, ek hi data pe.
REM Jab tak yeh number nahi banta, engine short trade nahi karega. Sirf dikhayega.
cd /d "%~dp0"
title SHORT BOOK - kya yeh apni jagah banata hai
python short_test.py --days 900
echo.
pause
