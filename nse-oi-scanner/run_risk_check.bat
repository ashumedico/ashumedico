@echo off
REM Where does the account stand against its OWN limits - today, this week, per trade.
REM DAY_DD / WEEK_DD / MAX_LOSS sat in config.py enforced by nothing until now. If this
REM says "NOT enforced", those settings are decoration, not protection.
cd /d "%~dp0"
python risk_limits.py
echo.
pause
