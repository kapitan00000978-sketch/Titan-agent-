<#
.SYNOPSIS
    EXTRA LLM X - PowerShell launcher script wrapper.
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

& (Join-Path $PSScriptRoot "start.ps1") @PSBoundParameters
