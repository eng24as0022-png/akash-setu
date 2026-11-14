@echo off
title Akash Setu - Tactical Disaster Response Command Node
echo ==============================================================================
echo    AKASH SETU (आकाश सेतु) - TACTICAL DISASTER RESPONSE PLATFORM
echo ==============================================================================
echo.
echo Checking Python environment...
python --version
if %errorlevel% neq 0 (
    echo [ERROR] Python 3 was not detected in PATH. Please install Python 3.10+
    pause
    exit /b 1
)

echo.
echo Launching Akash Setu Mission Control Server...
echo Tactical Dashboard will be available at: http://localhost:8080
echo.
python server.py 8080
pause
