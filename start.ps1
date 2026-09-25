<#
.SYNOPSIS
    EXTRA LLM X - PowerShell launcher script (automatic setup + Web/CLI).

.DESCRIPTION
    - Checks Python 3.10+ availability
    - Creates venv (if missing) and installs dependencies
    - Creates .env from .env.example if missing
    - Launches Web Dashboard (default) or Terminal CLI mode

.EXAMPLE
    .\start.ps1                 # Web Dashboard (default)
    .\start.ps1 -CLI            # Terminal CLI mode
    .\start.ps1 -Port 8000      # Web on a different port
    .\start.ps1 -Provider extra-llm-x -Model extra/auto-free
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

function Write-Brand($Msg) {
    Write-Host "⚡ $Msg" -ForegroundColor Cyan
}

function Test-Python {
    try {
        $v = python --version 2>&1
        if ($LASTEXITCODE -ne 0) { throw "" }
        Write-Brand "Detecting Python: $v"
        return $true
    } catch {
        Write-Host "❌ Python not found. Install Python 3.10+ from https://www.python.org/downloads/." -ForegroundColor Red
        return $false
    }
}

function Ensure-Venv {
    if (Test-Path $VenvPy) {
        return $VenvPy
    }
    Write-Brand "Virtual environment not found. Creating .venv..."
    python -m venv $Venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Could not create virtual environment. Running system Python." -ForegroundColor Yellow
        return "python"
    }
    Write-Brand "Upgrading pip and installing requirements..."
    & $VenvPy -m pip install --upgrade pip -q
    if (Test-Path $Requirements) {
        & $VenvPy -m pip install -r $Requirements -q
    }
    return $VenvPy
}

function Ensure-Env {
    if (-not (Test-Path $EnvFile)) {
        if (Test-Path $EnvExample) {
            Copy-Item $EnvExample $EnvFile
            Write-Brand "Created .env from .env.example."
        }
    }
}

if (-not (Test-Python)) { exit 1 }
$Py = Ensure-Venv
Ensure-Env

$ArgsList = @()
if ($CLI) {
    $ArgsList += "--cli"
} elseif ($TUI) {
    $ArgsList += "--tui"
} else {
    $ArgsList += "--web"
    $ArgsList += "--port", $Port
    if ($NoBrowser) { $ArgsList += "--no-browser" }
}

if ($Provider) { $ArgsList += "--provider", $Provider }
if ($Model) { $ArgsList += "--model", $Model }

Write-Brand "Launching Extra LLM X..."
& $Py run.py @ArgsList
