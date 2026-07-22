# TruthNet Neo4j 原生安装预检脚本 — Windows
# 用法: powershell -File scripts/neo4j_native/preflight.ps1
# 检查 Java、端口和现有 Neo4j 实例

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
Write-Host "=== TruthNet Neo4j Native Preflight ===" -ForegroundColor Cyan

# --- Java ---
Write-Host "`n[1/4] Checking Java..." -ForegroundColor Yellow
$javaHome = $env:JAVA_HOME
if (-not $javaHome) {
    $javaHome = [Environment]::GetEnvironmentVariable("JAVA_HOME", "User")
}
if (-not $javaHome) {
    $javaHome = [Environment]::GetEnvironmentVariable("JAVA_HOME", "Machine")
}
if ($javaHome) {
    Write-Host "  JAVA_HOME = $javaHome" -ForegroundColor Green
    $javaBin = Join-Path $javaHome "bin\java.exe"
    if (Test-Path $javaBin) {
        & $javaBin -version 2>&1 | ForEach-Object { Write-Host "  $_" }
    } else {
        Write-Host "  WARNING: java.exe not found at $javaBin" -ForegroundColor Red
    }
} else {
    Write-Host "  WARNING: JAVA_HOME not set" -ForegroundColor Red
}

# --- Ports ---
Write-Host "`n[2/4] Checking ports..." -ForegroundColor Yellow
$ports = @(7474, 7687)
foreach ($port in $ports) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        Write-Host "  Port $port : IN USE (PID $($conn.OwningProcess))" -ForegroundColor Red
    } else {
        Write-Host "  Port $port : free" -ForegroundColor Green
    }
}

# --- Existing Neo4j ---
Write-Host "`n[3/4] Checking existing Neo4j..." -ForegroundColor Yellow
$svc = Get-Service -Name "*neo4j*" -ErrorAction SilentlyContinue
if ($svc) { Write-Host "  Service: $($svc.Name) ($($svc.Status))" -ForegroundColor Yellow }
$proc = Get-Process -Name "neo4j*","java*" -ErrorAction SilentlyContinue
if ($proc) { Write-Host "  Process: $($proc.ProcessName) (PID $($proc.Id))" -ForegroundColor Yellow }
if (-not $svc -and -not $proc) { Write-Host "  No existing Neo4j found" -ForegroundColor Green }

# --- Disk ---
Write-Host "`n[4/4] Checking disk space..." -ForegroundColor Yellow
$vol = Get-Volume | Where-Object { $_.DriveLetter -eq ($pwd.Drive.Name -replace ':', '') }
if ($vol) {
    $freeGB = [math]::Round($vol.SizeRemaining / 1GB, 1)
    Write-Host "  Drive ${pwd}: $freeGB GB free" -ForegroundColor $(if ($freeGB -gt 5) { "Green" } else { "Red" })
}

Write-Host "`n=== Preflight Complete ===" -ForegroundColor Cyan
