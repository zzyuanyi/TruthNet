# TruthNet V12 - Start MySQL in console mode (dev, no admin)
param(
    [int]$Port = 3307,
    [string]$DataDir = "E:\project\TruthNet\.local\mysql_data"
)

$MYSQL_BIN = "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqld.exe"

if (-not (Test-Path $MYSQL_BIN)) {
    Write-Host "[ERROR] MySQL not found at: $MYSQL_BIN" -ForegroundColor Red
    Write-Host "Install via: winget install Oracle.MySQL"
    exit 1
}

# Check if already running
$existing = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "[INFO] MySQL port $Port already listening" -ForegroundColor Yellow
    exit 0
}

# Ensure data dir exists
if (-not (Test-Path $DataDir)) {
    Write-Host "[INFO] Initializing MySQL data directory: $DataDir"
    & $MYSQL_BIN --initialize-insecure --console --datadir=$DataDir
    Write-Host "[OK] MySQL initialized"
}

Write-Host "[INFO] Starting MySQL on 127.0.0.1:$Port..."
Start-Process -FilePath $MYSQL_BIN -ArgumentList "--console","--datadir=$DataDir","--port=$Port","--bind-address=127.0.0.1" -WindowStyle Hidden

Start-Sleep -Seconds 3
$listener = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
if ($listener) {
    Write-Host "[OK] MySQL started on port $Port" -ForegroundColor Green
    Write-Host "Connect: mysql -u root --host 127.0.0.1 --port $Port"
} else {
    Write-Host "[FAIL] MySQL did not start" -ForegroundColor Red
    exit 1
}
