@echo off
title Universal Agent HP - Autonomous AI Cockpit
color 0b
echo ========================================================
echo     UNIVERSAL AGENT HP - AUTONOMOUS AI SYSTEM
echo ========================================================
echo.
echo 1) Modern Terminal TUI (Textual / OpenCode style)
echo 2) Web Dashboard (control via browser)
echo 3) Interactive Terminal CLI
echo.
set /p choice="Choose (1, 2, or 3) [Default: 1]: "

if "%choice%"=="2" (
    echo Starting Web Dashboard...
    powershell -ExecutionPolicy Bypass -File "%~dp0start-titan.ps1"
) else if "%choice%"=="3" (
    echo Starting Terminal CLI...
    powershell -ExecutionPolicy Bypass -File "%~dp0start-titan.ps1" -CLI
) else (
    echo Starting Modern Terminal TUI...
    powershell -ExecutionPolicy Bypass -File "%~dp0start-titan.ps1" -TUI
)
pause