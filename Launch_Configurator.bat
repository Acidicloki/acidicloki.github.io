@echo off
title Weekend at Loki's - Windows Configurator v7.0
echo ==============================================================================
echo   WEEKEND AT LOKI'S - WINDOWS COMPANION CONFIGURATOR (v7.0)
echo ==============================================================================
echo.
echo [1/2] Checking Python environment...

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

echo [2/2] Launching Windows Companion Program...
echo.
%PY_CMD% configurator.py

if %errorlevel% neq 0 (
    echo.
    echo ==============================================================================
    echo [NOTICE] Configurator closed with exit code: %errorlevel%
    echo If you encountered an error, check 'companion_error.log' in this folder.
    echo ==============================================================================
    echo.
    pause
)
