@echo off
REM Proves one press cannot send an order, and that the kill switch / live flag /
REM missing-contract guards still hold at the button layer. Sends nothing real.
cd /d "%~dp0"
python test_orders.py
echo.
pause
