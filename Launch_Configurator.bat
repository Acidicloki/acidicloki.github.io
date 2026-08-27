@echo off
title Weekend at Loki's - Windows Configurator v6.7
echo ==============================================================================
echo   WEEKEND AT LOKI'S - WINDOWS COMPANION CONFIGURATOR (v6.7)
echo ==============================================================================
echo.
echo Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    py --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Python is not installed or not in PATH.
        echo Please install Python 3.10+ from https://www.python.org/
        pause
        exit /b 1
    ) else (
        echo Launching Configurator with 'py'...
        py configurator.py
    )
) else (
    echo Launching Configurator with 'python'...
    python configurator.py
)
