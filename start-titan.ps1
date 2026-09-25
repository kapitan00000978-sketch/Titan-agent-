<#
.SYNOPSIS
    TITAN AGENT - PowerShell launcher script (automatic setup + Web/CLI).

.DESCRIPTION
    - Checks Python 3.10+ availability
    - Creates venv (if missing) and installs dependencies
    - Creates .env from .env.example if missing
    - Launches Web Dashboard (default) or Terminal CLI mode

.EXAMPLE
    .\start-titan.ps1                 # Web Dashboard (default)
    .\start-titan.ps1 -CLI            # Terminal CLI mode
    .\start-titan.ps1 -Port 8000      # Web on a different port
    .\start-titan.ps1 -Provider ollama -Model hermes3:8b
#>
[CmdletBinding()]
param(
    [switch]$CLI,
    [switch]$TUI,
    [int]$Port = 7860,
    [string]$Provider = "",
    [string]$Model = "",
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Venv = Join-Path $Root ".venv"
$VenvPy = Join-Path $Venv "Scripts\python.exe"
$EnvFile = Join-Path $Root ".env"
$EnvExample = Join-Path $Root ".env.example"
$Requirements = Join-Path $Root "requirements.txt"

function Write-Titan($Msg) {
    Write-Host "⚡ $Msg" -ForegroundColor Cyan
}

function Test-Python {
    try {
        $v = python --version 2>&1
        if ($LASTEXITCODE -ne 0) { throw "" }
        Write-Titan "Detecting Python: $v"
        return $true
    } catch {
        Write-Host "❌ Python not found. Install Python 3.10+ from https://www.python.org/downloads/." -ForegroundColor Red
        return $false
    }
}

function Ensure-Venv {
    if (-not (Test-Path $VenvPy)) {
        Write-Titan "Creating a new venv..."
        python -m venv $Venv
        if ($LASTEXITCODE -ne 0) { throw "Failed to create venv" }
    }
    Write-Titan "Checking/installing dependencies (may take a while on first run)..."
    & $VenvPy -m pip install --upgrade pip --quiet
    & $VenvPy -m pip install -r $Requirements --quiet
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
}

function Ensure-Env {
    if (-not (Test-Path $EnvFile) -and (Test-Path $EnvExample)) {
        Write-Titan "Creating .env from .env.example..."
        Copy-Item $EnvExample $EnvFile
    }
}

function Start-Titan {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor DarkCyan
    Write-Host "   ⚡ UNIVERSAL AGENT HP — Autonomous AI System" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor DarkCyan
    Write-Host ""

    if ($TUI) {
        Write-Titan "Starting Ultra-Modern Terminal TUI mode..."
        & $VenvPy run.py --tui
    } elseif ($CLI) {
        Write-Titan "Starting Terminal CLI mode..."
        & $VenvPy run.py --cli
    } else {
        $urlArgs = @("run.py", "--web")
        if ($Port -ne 7860) { $urlArgs += "--port"; $urlArgs += "$Port" }
        if ($NoBrowser) { $urlArgs += "--no-browser" }
        if ($Provider) { $urlArgs += "--provider"; $urlArgs += $Provider }
        if ($Model) { $urlArgs += "--model"; $urlArgs += $Model }
        Write-Titan "Starting Web Dashboard: http://127.0.0.1:$Port"
        & $VenvPy @urlArgs
    }
}

if (-not (Test-Python)) { exit 1 }

try {
    Ensure-Venv
    Ensure-Env
    Push-Location $Root
    try {
        Start-Titan
    } finally {
        Pop-Location
    }
} catch {
    Write-Host "❌ Error: $_" -ForegroundColor Red
    exit 1
}