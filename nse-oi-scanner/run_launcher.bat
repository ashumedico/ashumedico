@echo off
REM The launcher window - credentials, settings, START ENGINE, live log.
REM Same thing the .exe opens; this runs it straight from Python.
cd /d "%~dp0"
start "" pythonw launcher.py
if errorlevel 1 python launcher.py
