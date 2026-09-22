@echo off
REM R-Factor: TradeFinder's momentum-intensity idea, and our composite version that folds
REM in VOLUME and RANGE. Proves the composite reduces to the price-only version at normal
REM activity - which is what makes the ablation a measurement of the addition rather than
REM a comparison of two unrelated rankings.
cd /d "%~dp0"
python test_rfactor.py
echo.
pause
