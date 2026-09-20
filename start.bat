@echo off
title Titan Agent - Autonomous AI Cockpit
color 0b
echo ========================================================
echo        TITAN AGENT - AUTONOMOUS AI SYSTEM
echo ========================================================
echo.
echo 1) Web Dashboard (control via browser)
echo 2) Terminal CLI (control via console)
echo.
set /p choice="Choose (1 or 2) [Default: 1]: "

if "%choice%"=="2" (
    echo Starting Terminal CLI...
    powershell -ExecutionPolicy Bypass -File "%~dp0start-titan.ps1" -CLI
) else (
    echo Starting Web Dashboard...
    powershell -ExecutionPolicy Bypass -File "%~dp0start-titan.ps1"
)
pause