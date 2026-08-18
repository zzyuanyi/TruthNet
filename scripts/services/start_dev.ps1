# TruthNet 一键启动开发/演示环境（V12）
#
# 用法:
#   powershell -ExecutionPolicy Bypass -File scripts/services/start_dev.ps1            # 全部启动（含 MySQL/Neo4j）
#   powershell -ExecutionPolicy Bypass -File scripts/services/start_dev.ps1 -NoInfra   # 跳过 MySQL/Neo4j（已运行时用）
#   powershell -ExecutionPolicy Bypass -File scripts/services/start_dev.ps1 -NoBackend # 只起前端
#   powershell -ExecutionPolicy Bypass -File scripts/services/start_dev.ps1 -NoFrontend# 只起后端
#
# 停止: powershell -ExecutionPolicy Bypass -File scripts/services/stop_dev.ps1
param(
  [switch]$NoInfra,     # 跳过 MySQL/Neo4j 检查与启动
  [switch]$NoBackend,   # 不启动后端 (uvicorn :8000)
  [switch]$NoFrontend   # 不启动前端 (vite :5000)
)

$ErrorActionPreference = "Stop"
$scriptDir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot     = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$frontendDir  = Join-Path $repoRoot "frontend"
$backendPort  = 8000
$frontendPort = 5000

# 定位子进程 shell: 优先 pwsh 7，回退 Windows PowerShell 5.1
$shellPath = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
if (-not $shellPath -and (Test-Path "C:\Program Files\PowerShell\7\pwsh.exe")) {
  $shellPath = "C:\Program Files\PowerShell\7\pwsh.exe"
}
if (-not $shellPath) { $shellPath = "powershell.exe" }

# 将命令以 -EncodedCommand 传给子进程（规避 5.1 引号拼接问题）
function New-EncodedCommand([string]$Text) {
  return [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($Text))
}

Write-Host ""
Write-Host "TruthNet V12 一键启动" -ForegroundColor Cyan
Write-Host "====================="

# ---------- 基础设施: MySQL(3306) + Neo4j(7687/7474) ----------
if (-not $NoInfra) {
  $mysqlUp = Get-NetTCPConnection -LocalPort 3306 -State Listen -ErrorAction SilentlyContinue
  if ($mysqlUp) {
    Write-Host "[1/4] MySQL 已在运行 (3306)" -ForegroundColor Green
  } else {
    Write-Host "[1/4] 启动 MySQL ..." -ForegroundColor Yellow
    & (Join-Path $scriptDir "start_mysql_dev.ps1")
  }

  $neoUp = Get-NetTCPConnection -LocalPort 7687 -State Listen -ErrorAction SilentlyContinue
  if ($neoUp) {
    Write-Host "[2/4] Neo4j 已在运行 (7687/7474)" -ForegroundColor Green
  } else {
    Write-Host "[2/4] 启动 Neo4j ..." -ForegroundColor Yellow
    & (Join-Path $scriptDir "start_neo4j_dev.ps1")
  }
} else {
  Write-Host "[--] 跳过基础设施 (-NoInfra)" -ForegroundColor DarkGray
}

# ---------- 后端: uvicorn :8000 ----------
if (-not $NoBackend) {
  $busy = Get-NetTCPConnection -LocalPort $backendPort -State Listen -ErrorAction SilentlyContinue
  if ($busy) {
    Write-Host "[3/4] 端口 $backendPort 已被占用，后端跳过（如属残留进程请先跑 stop_dev.ps1）" -ForegroundColor DarkYellow
  } else {
    # 定位 Python 解释器: 环境变量 > 常见 conda 路径 > PATH
    $py = $env:TRUTHNET_PYTHON
    if (-not $py -or -not (Test-Path $py)) {
      $candidates = @(
        "D:\anaconda\envs\truthnet\python.exe",
        "$env:USERPROFILE\anaconda3\envs\truthnet\python.exe",
        "$env:USERPROFILE\miniconda3\envs\truthnet\python.exe"
      )
      $py = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    }
    if (-not $py) { $py = "python" }

    $backendCmd = "`$env:PYTHONUTF8='1'; `$env:PYTHONPATH='backend'; " +
                  "`$Host.UI.RawUI.WindowTitle='TruthNet-Backend'; " +
                  "& '$py' -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port $backendPort"
    Write-Host "[3/4] 启动后端 (http://127.0.0.1:$backendPort) ..." -ForegroundColor Yellow
    Start-Process $shellPath -WorkingDirectory $repoRoot -ArgumentList @("-NoExit", "-EncodedCommand", (New-EncodedCommand $backendCmd))
  }
} else {
  Write-Host "[3/4] 跳过后端 (-NoBackend)" -ForegroundColor DarkGray
}

# ---------- 前端: vite :5000 ----------
if (-not $NoFrontend) {
  $busy = Get-NetTCPConnection -LocalPort $frontendPort -State Listen -ErrorAction SilentlyContinue
  if ($busy) {
    Write-Host "[4/4] 端口 $frontendPort 已被占用，前端跳过（如属残留进程请先跑 stop_dev.ps1）" -ForegroundColor DarkYellow
  } else {
    $frontCmd = "`$Host.UI.RawUI.WindowTitle='TruthNet-Frontend'; " +
                "pnpm exec vite --host --port $frontendPort"
    Write-Host "[4/4] 启动前端 (http://127.0.0.1:$frontendPort) ..." -ForegroundColor Yellow
    Start-Process $shellPath -WorkingDirectory $frontendDir -ArgumentList @("-NoExit", "-EncodedCommand", (New-EncodedCommand $frontCmd))
  }
} else {
  Write-Host "[4/4] 跳过前端 (-NoFrontend)" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "启动完成，访问:" -ForegroundColor Cyan
Write-Host "  前端   http://127.0.0.1:$frontendPort"
Write-Host "  后端   http://127.0.0.1:$backendPort/api/v1/healthz"
Write-Host "  文档   http://127.0.0.1:$backendPort/docs"
Write-Host "停止:   powershell -ExecutionPolicy Bypass -File scripts/services/stop_dev.ps1"
Write-Host ""
