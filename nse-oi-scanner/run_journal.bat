@echo off
REM Journal: log today's signals, grade past ones, print the lessons.
cd /d "%~dp0"
if not exist "access_token.txt" (
    echo [i] No Fyers token - running on DEMO data.
    python journal.py --demo --backfill --review --lessons
) else (
    python journal.py --all
)
echo.
echo Full report written to journal_report.md
pause
