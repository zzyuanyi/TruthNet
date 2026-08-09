# TruthNet backend watchdog for Windows Task Scheduler.
[CmdletBinding()]
param(
    [string]$PythonPath = "D:\anaconda\envs\truthnet\python.exe",
    [string]$BackendDirectory = "",
    [string]$HostAddress = "127.0.0.1",
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,
    [string]$LogDirectory = "",
    [string]$AppModule = "app.main:app",
    [ValidateRange(0, 3600)]
    [int]$RestartDelaySeconds = 5,
    [ValidateRange(0, 1000000)]
    [int]$MaxRestarts = 0,
    [ValidateRange(0, 300)]
    [int]$StartupProbeSeconds = 5,
    [ValidateRange(1, 300)]
    [int]$MonitorIntervalSeconds = 10,
    [switch]$CheckOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not $BackendDirectory) {
    $BackendDirectory = Join-Path $repoRoot "backend"
}
if (-not $LogDirectory) {
    $LogDirectory = Join-Path $repoRoot "logs\backend-watchdog"
}

New-Item -ItemType Directory -Path $LogDirectory -Force | Out-Null
$eventLogPath = Join-Path $LogDirectory "watchdog.jsonl"
$statePath = Join-Path $LogDirectory "watchdog-state.json"
$script:RestartCount = 0

if (Test-Path -LiteralPath $statePath) {
    try {
        $savedState = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        if ($null -ne $savedState.restart_count) {
            $script:RestartCount = [int]$savedState.restart_count
        }
    }
    catch {
        $script:RestartCount = 0
    }
}

function Write-WatchdogEvent {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Event,
        [hashtable]$Data = @{}
    )

    $payload = [ordered]@{
        timestamp = (Get-Date).ToUniversalTime().ToString("o")
        event = $Event
        port = $Port
        restart_count = $script:RestartCount
    }
    foreach ($key in $Data.Keys) {
        $payload[$key] = $Data[$key]
    }
    $line = $payload | ConvertTo-Json -Compress -Depth 6
    Add-Content -LiteralPath $eventLogPath -Value $line -Encoding utf8
    Write-Host $line
}

function Save-WatchdogState {
    $state = [ordered]@{
        updated_at = (Get-Date).ToUniversalTime().ToString("o")
        restart_count = $script:RestartCount
        port = $Port
    }
    $state | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding utf8
}

function Test-TcpPort {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $connect = $client.BeginConnect($HostAddress, $Port, $null, $null)
        if (-not $connect.AsyncWaitHandle.WaitOne(500)) {
            return $false
        }
        $client.EndConnect($connect)
        return $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Get-PortState {
    $healthUrl = "http://${HostAddress}:${Port}/api/v1/healthz"
    try {
        $response = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 2
        if ($response.data.status -eq "healthy") {
            return "truthnet"
        }
    }
    catch {
        # A failed health probe may still mean another process owns the port.
    }

    if (Test-TcpPort) {
        return "occupied"
    }
    return "free"
}

function Stop-WithPortState {
    param([string]$PortState)

    if ($PortState -eq "truthnet") {
        Write-WatchdogEvent -Event "truthnet_instance_detected" -Data @{
            health_url = "http://${HostAddress}:${Port}/api/v1/healthz"
        }
        return 0
    }
    if ($PortState -eq "occupied") {
        Write-WatchdogEvent -Event "port_conflict" -Data @{
            reason = "port is occupied by a non-TruthNet process"
        }
        return 2
    }
    Write-WatchdogEvent -Event "port_free"
    return 0
}

if ($CheckOnly) {
    exit (Stop-WithPortState -PortState (Get-PortState))
}

if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    Write-WatchdogEvent -Event "startup_failed" -Data @{
        reason = "python executable not found"
        python_path = $PythonPath
    }
    exit 3
}
if (-not (Test-Path -LiteralPath $BackendDirectory -PathType Container)) {
    Write-WatchdogEvent -Event "startup_failed" -Data @{
        reason = "backend directory not found"
        backend_directory = $BackendDirectory
    }
    exit 3
}

while ($true) {
    $portState = Get-PortState
    if ($portState -eq "occupied") {
        exit (Stop-WithPortState -PortState $portState)
    }
    if ($portState -eq "truthnet") {
        Write-WatchdogEvent -Event "monitoring_existing_instance"
        do {
            Start-Sleep -Seconds $MonitorIntervalSeconds
            $portState = Get-PortState
        } while ($portState -eq "truthnet")
        Write-WatchdogEvent -Event "existing_instance_lost" -Data @{
            observed_state = $portState
        }
        if ($portState -eq "occupied") {
            exit (Stop-WithPortState -PortState $portState)
        }
    }

    $runId = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfffZ")
    $stdoutPath = Join-Path $LogDirectory "backend-${runId}.stdout.log"
    $stderrPath = Join-Path $LogDirectory "backend-${runId}.stderr.log"
    $stdoutStream = $null
    $stderrStream = $null
    try {
        $startedAt = Get-Date
        $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
        $startInfo.FileName = $PythonPath
        $startInfo.Arguments = "-m uvicorn $AppModule --host $HostAddress --port $Port"
        $startInfo.WorkingDirectory = $BackendDirectory
        $startInfo.UseShellExecute = $false
        $startInfo.CreateNoWindow = $true
        $startInfo.RedirectStandardOutput = $true
        $startInfo.RedirectStandardError = $true

        $process = [System.Diagnostics.Process]::new()
        $process.StartInfo = $startInfo
        if (-not $process.Start()) {
            throw "process start returned false"
        }
        $stdoutStream = [System.IO.File]::Open(
            $stdoutPath,
            [System.IO.FileMode]::Create,
            [System.IO.FileAccess]::Write,
            [System.IO.FileShare]::Read
        )
        $stderrStream = [System.IO.File]::Open(
            $stderrPath,
            [System.IO.FileMode]::Create,
            [System.IO.FileAccess]::Write,
            [System.IO.FileShare]::Read
        )
        $stdoutCopyTask = $process.StandardOutput.BaseStream.CopyToAsync($stdoutStream)
        $stderrCopyTask = $process.StandardError.BaseStream.CopyToAsync($stderrStream)
        Write-WatchdogEvent -Event "process_started" -Data @{
            pid = $process.Id
            stdout_log = $stdoutPath
            stderr_log = $stderrPath
        }
    }
    catch {
        if ($null -ne $stdoutStream) {
            $stdoutStream.Dispose()
        }
        if ($null -ne $stderrStream) {
            $stderrStream.Dispose()
        }
        Write-WatchdogEvent -Event "startup_failed" -Data @{
            reason = $_.Exception.Message
            python_path = $PythonPath
            backend_directory = $BackendDirectory
        }
        exit 3
    }

    if ($StartupProbeSeconds -gt 0) {
        Start-Sleep -Seconds $StartupProbeSeconds
    }
    if (-not $process.HasExited) {
        $startupState = Get-PortState
        Write-WatchdogEvent -Event "startup_probe" -Data @{
            pid = $process.Id
            state = $startupState
        }
    }

    $process.WaitForExit()
    try {
        $stdoutCopyTask.GetAwaiter().GetResult()
        $stderrCopyTask.GetAwaiter().GetResult()
    }
    finally {
        $stdoutStream.Dispose()
        $stderrStream.Dispose()
    }
    $exitCode = $process.ExitCode
    $runtimeSeconds = [math]::Round(((Get-Date) - $startedAt).TotalSeconds, 3)
    $script:RestartCount += 1
    Save-WatchdogState
    Write-WatchdogEvent -Event "process_exited" -Data @{
        pid = $process.Id
        exit_code = $exitCode
        runtime_seconds = $runtimeSeconds
    }

    if ($MaxRestarts -gt 0 -and $script:RestartCount -ge $MaxRestarts) {
        Write-WatchdogEvent -Event "watchdog_stopped" -Data @{
            reason = "maximum restart count reached"
            last_exit_code = $exitCode
        }
        exit $exitCode
    }

    if ($RestartDelaySeconds -gt 0) {
        Start-Sleep -Seconds $RestartDelaySeconds
    }
}
