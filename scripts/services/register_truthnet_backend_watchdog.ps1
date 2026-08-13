# Explicitly register the TruthNet watchdog with Windows Task Scheduler.
# Run this script manually from an elevated PowerShell. It is never invoked by the app.
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$TaskName = "TruthNet Backend Watchdog",
    [string]$PythonPath = "D:\anaconda\envs\truthnet\python.exe",
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,
    [string]$LogDirectory = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$watchdogPath = (Resolve-Path (Join-Path $PSScriptRoot "watch_truthnet_backend.ps1")).Path
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$backendDirectory = Join-Path $repoRoot "backend"
if (-not $LogDirectory) {
    $LogDirectory = Join-Path $repoRoot "logs\backend-watchdog"
}
if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    throw "Python executable not found: $PythonPath"
}

$arguments = @(
    "-NoProfile",
    "-ExecutionPolicy Bypass",
    "-File `"$watchdogPath`"",
    "-PythonPath `"$PythonPath`"",
    "-BackendDirectory `"$backendDirectory`"",
    "-Port $Port",
    "-LogDirectory `"$LogDirectory`""
) -join " "

if ($PSCmdlet.ShouldProcess($TaskName, "Register Windows startup watchdog task")) {
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arguments
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $settings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -User "SYSTEM" `
        -RunLevel Highest `
        -Force | Out-Null
    Write-Output "Registered scheduled task: $TaskName"
}
