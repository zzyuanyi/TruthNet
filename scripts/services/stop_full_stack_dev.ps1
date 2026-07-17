# TruthNet V12 - Stop dev services (only TruthNet processes)
Write-Host "TruthNet V12 Full Stack Dev Stop" -ForegroundColor Cyan
Write-Host "================================="

# Stop MySQL (only the one on port 3307 with TruthNet datadir)
$mysqlProc = Get-Process -Name "mysqld" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -match "mysql_data"
}
if ($mysqlProc) {
    Write-Host "[INFO] Stopping MySQL (TruthNet instance)..."
    $mysqlProc | Stop-Process -Force
    Write-Host "[OK] MySQL stopped"
} else {
    Write-Host "[INFO] No TruthNet MySQL process found"
}

# Stop Neo4j (only from TruthNet .local path)
$neo4jProc = Get-Process -Name "java" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -match "neo4j-community"
}
if ($neo4jProc) {
    Write-Host "[INFO] Stopping Neo4j (TruthNet instance)..."
    $neo4jProc | Stop-Process -Force
    Write-Host "[OK] Neo4j stopped"
} else {
    Write-Host "[INFO] No TruthNet Neo4j process found"
}

Write-Host "[OK] Done. ChromaDB has no persistent daemon."
