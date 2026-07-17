# TruthNet V12 Full Stack Port Check
# 检查 MySQL, Neo4j, ChromaDB 端口是否监听

$ports = @(
    @{Name="MySQL"; Port=3307; Host="127.0.0.1"},
    @{Name="Neo4j Bolt"; Port=7687; Host="127.0.0.1"},
    @{Name="Neo4j HTTP"; Port=7474; Host="127.0.0.1"}
)

Write-Host "TruthNet V12 Full Stack Port Check" -ForegroundColor Cyan
Write-Host "===================================="

$allOk = $true
foreach ($p in $ports) {
    $listener = Get-NetTCPConnection -LocalPort $p.Port -LocalAddress $p.Host -ErrorAction SilentlyContinue
    if ($listener) {
        Write-Host "  [OK] $($p.Name) : $($p.Host):$($p.Port) - LISTENING" -ForegroundColor Green
    } else {
        Write-Host "  [DOWN] $($p.Name) : $($p.Host):$($p.Port) - NOT LISTENING" -ForegroundColor Red
        $allOk = $false
    }
}

# ChromaDB persistent dir
$chromaDir = "E:\project\TruthNet\.local\chroma"
if (Test-Path $chromaDir) {
    Write-Host "  [OK] ChromaDB persist dir: $chromaDir" -ForegroundColor Green
} else {
    Write-Host "  [WARN] ChromaDB persist dir not found: $chromaDir" -ForegroundColor Yellow
}

Write-Host "===================================="
if ($allOk) {
    Write-Host "  All required ports listening" -ForegroundColor Green
    exit 0
} else {
    Write-Host "  Some services not running" -ForegroundColor Red
    exit 1
}
