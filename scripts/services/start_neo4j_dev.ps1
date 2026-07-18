# TruthNet V12 - Start Neo4j in console mode (dev, no admin)
param(
    [string]$Neo4jHome = "E:\project\TruthNet\.local\neo4j\neo4j-community-2025.06.1",
    [string]$JavaHome = "C:\Program Files\Eclipse Adoptium\jdk-21.0.11.10-hotspot"
)

$NEO4J_BAT = Join-Path $Neo4jHome "bin\neo4j.bat"

if (-not (Test-Path $NEO4J_BAT)) {
    Write-Host "[ERROR] Neo4j not found at: $NEO4J_BAT" -ForegroundColor Red
    Write-Host "Download from: https://neo4j.com/download-center/#community"
    exit 1
}

if (-not (Test-Path $JavaHome)) {
    Write-Host "[ERROR] JDK not found at: $JavaHome" -ForegroundColor Red
    Write-Host "Install via: winget install EclipseAdoptium.Temurin.21.JDK"
    exit 1
}

# Check if already running
$existing = Get-NetTCPConnection -LocalPort 7687 -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "[INFO] Neo4j port 7687 already listening" -ForegroundColor Yellow
    exit 0
}

$env:JAVA_HOME = $JavaHome
$env:NEO4J_HOME = $Neo4jHome

Write-Host "[INFO] Starting Neo4j on bolt://127.0.0.1:7687 ..."
Start-Process -FilePath $NEO4J_BAT -ArgumentList "console" -WindowStyle Hidden

Start-Sleep -Seconds 10
$listener = Get-NetTCPConnection -LocalPort 7687 -ErrorAction SilentlyContinue
if ($listener) {
    Write-Host "[OK] Neo4j started on port 7687" -ForegroundColor Green
    Write-Host "Bolt: bolt://127.0.0.1:7687"
    Write-Host "HTTP: http://127.0.0.1:7474"
} else {
    Write-Host "[FAIL] Neo4j did not start" -ForegroundColor Red
    exit 1
}
