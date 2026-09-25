@echo off
title Extra LLM X - Autonomous AI Cockpit
color 0b
echo ========================================================
echo         EXTRA LLM X - AUTONOMOUS AI SYSTEM
echo ========================================================
echo.
echo 1) Modern Terminal TUI (Textual / OpenCode style)
echo 2) Web Dashboard (control via browser)
echo 3) Interactive Terminal CLI
echo.
set /p choice="Choose (1, 2, or 3) [Default: 2]: "

if "%choice%"=="1" (
    echo Starting Modern Terminal TUI...
    python run.py --tui
) else if "%choice%"=="3" (
    echo Starting Interactive Terminal CLI...
    python run.py --cli
) else (
    echo Starting Web Dashboard on http://localhost:7860 ...
    python run.py --web
)
pause