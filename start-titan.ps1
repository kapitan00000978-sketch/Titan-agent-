<#
.SYNOPSIS
    TITAN AGENT - PowerShell ishga tushirish skripti (avtomatik setup + Web/CLI).

.DESCRIPTION
    - Python 3.10+ mavjudligini tekshiradi
    - venv yaratadi (agar yo'q bo'lsa) va qaramliklarni o'rnatadi
    - .env yo'q bo'lsa .env.example dan yaratadi
    - Web Dashboard (default) yoki Terminal CLI rejimida ishga tushiradi

.EXAMPLE
    .\start-titan.ps1                 # Web Dashboard (default)
    .\start-titan.ps1 -CLI            # Terminal CLI rejimi
    .\start-titan.ps1 -Port 8000      # Boshqa portda Web
    .\start-titan.ps1 -Provider ollama -Model hermes3:8b
#>
[CmdletBinding()]
param(
    [switch]$CLI,
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
        Write-Titan "Python aniqlanmoqda: $v"
        return $true
    } catch {
        Write-Host "❌ Python topilmadi. https://www.python.org/downloads/ dan Python 3.10+ o'rnating." -ForegroundColor Red
        return $false
    }
}

function Ensure-Venv {
    if (-not (Test-Path $VenvPy)) {
        Write-Titan "Yangi venv yaratilmoqda..."
        python -m venv $Venv
        if ($LASTEXITCODE -ne 0) { throw "venv yaratib bo'lmadi" }
    }
    Write-Titan "Qaramliklar tekshirilmoqda/sozlanmoqda (birinchi marta uzoq davom etishi mumkin)..."
    & $VenvPy -m pip install --upgrade pip --quiet
    & $VenvPy -m pip install -r $Requirements --quiet
    if ($LASTEXITCODE -ne 0) { throw "pip install muvaffaqiyatsiz" }
}

function Ensure-Env {
    if (-not (Test-Path $EnvFile) -and (Test-Path $EnvExample)) {
        Write-Titan ".env fayli .env.example dan yaratilmoqda..."
        Copy-Item $EnvExample $EnvFile
    }
}

function Start-Titan {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor DarkCyan
    Write-Host "   ⚡ TITAN AGENT — Avtonom AI Tizimi (PowerShell)" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor DarkCyan
    Write-Host ""

    if ($CLI) {
        Write-Titan "Terminal CLI rejimi ishga tushirilmoqda..."
        & $VenvPy run.py --cli
    } else {
        $urlArgs = @("run.py")
        if ($Port -ne 7860) { $urlArgs += "--port"; $urlArgs += "$Port" }
        if ($NoBrowser) { $urlArgs += "--no-browser" }
        if ($Provider) { $urlArgs += "--provider"; $urlArgs += $Provider }
        if ($Model) { $urlArgs += "--model"; $urlArgs += $Model }
        Write-Titan "Web Dashboard ishga tushirilmoqda: http://127.0.0.1:$Port"
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
    Write-Host "❌ Xatolik: $_" -ForegroundColor Red
    exit 1
}