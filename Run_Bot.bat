@echo off
title Weekend at Loki's - Discord Bot Runner v6.7
echo ==============================================================================
echo   WEEKEND AT LOKI'S - DISCORD BOT RUNNER (v6.7)
echo ==============================================================================
echo.
echo [1/2] Checking and installing dependencies...
python -m pip install -r requirements.txt --quiet >nul 2>&1
if %errorlevel% neq 0 (
    py -m pip install -r requirements.txt --quiet >nul 2>&1
)

echo [2/2] Starting bot.py...
echo.
python bot.py
if %errorlevel% neq 0 (
    py bot.py
)
echo.
echo Bot process ended.
pause
