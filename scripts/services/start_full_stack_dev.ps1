# TruthNet V12 - Start all services for development
Write-Host "TruthNet V12 Full Stack Dev Start" -ForegroundColor Cyan
Write-Host "=================================="

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "`n[1/2] Starting MySQL..."
& "$scriptDir\start_mysql_dev.ps1"

Write-Host "`n[2/2] Starting Neo4j..."
& "$scriptDir\start_neo4j_dev.ps1"

Write-Host "`n=================================="
Write-Host "Checking ports..."
& "$scriptDir\check_full_stack_ports.ps1"

Write-Host "`nChromaDB persistent mode (no daemon needed)"
Write-Host "  Dir: E:\project\TruthNet\.local\chroma"
Write-Host "`nServices started. Run stop_full_stack_dev.ps1 to stop."
