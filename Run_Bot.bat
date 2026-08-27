@echo off
title Weekend at Loki's - Discord Bot Runner v7.0
echo ==============================================================================
echo   WEEKEND AT LOKI'S - DISCORD BOT RUNNER (v7.0)
echo ==============================================================================
echo.
echo [1/2] Verifying Python and required packages...

set PY_CMD=python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    py --version >nul 2>&1
    if %errorlevel% equ 0 (
        set PY_CMD=py
    ) else (
        echo.
        echo [ERROR] Python is not installed or not added to your Windows PATH.
        echo Please download and install Python 3.10+ from: https://www.python.org/downloads/
        echo (Make sure to check 'Add python.exe to PATH' during installation!)
        echo.
        pause
        exit /b 1
    )
)

%PY_CMD% -m pip install discord.py aiohttp Pillow python-dotenv --quiet >nul 2>&1

echo [2/2] Starting bot.py...
echo.
%PY_CMD% bot.py

echo.
echo ==============================================================================
echo [NOTICE] Bot process ended.
echo If the bot failed to start, verify DISCORD_TOKEN in .env or check 'bot_error.log'.
echo ==============================================================================
echo.
pause
