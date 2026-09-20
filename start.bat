@echo off
title Titan Agent - Autonomous AI Cockpit
color 0b
echo ========================================================
echo        TITAN AGENT - AVTONOM AI BOSHQARUV TIZIMI
echo ========================================================
echo.
echo 1) Web Dashboard (Brauzer orqali boshqarish)
echo 2) Terminal CLI (Konsol orqali boshqarish)
echo.
set /p choice="Tanlang (1 yoki 2) [Default: 1]: "

if "%choice%"=="2" (
    echo Terminal CLI ishga tushirilmoqda...
    powershell -ExecutionPolicy Bypass -File "%~dp0start-titan.ps1" -CLI
) else (
    echo Web Dashboard ishga tushirilmoqda...
    powershell -ExecutionPolicy Bypass -File "%~dp0start-titan.ps1"
)
pause