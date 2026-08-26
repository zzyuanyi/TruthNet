<#!
.SYNOPSIS
启动 TruthNet FastAPI 后端。缺少运行依赖时按仓库 requirements.txt 安装。
#>
param(
  [int]$Port = 0,
  [string]$HostAddress = ''
)

$ErrorActionPreference = 'Stop'
$backendDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $backendDir '..')).Path

if ($Port -le 0) {
  $Port = if ($env:BACKEND_PORT) { [int]$env:BACKEND_PORT } else { 8001 }
}
if (-not $HostAddress) {
  $HostAddress = if ($env:BACKEND_HOST) { $env:BACKEND_HOST } else { '127.0.0.1' }
}

if ($env:TRUTHNET_PYTHON) {
  if (-not (Test-Path $env:TRUTHNET_PYTHON)) {
    throw "TRUTHNET_PYTHON 不存在：$env:TRUTHNET_PYTHON"
  }
  $python = $env:TRUTHNET_PYTHON
} else {
  $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
  if (-not $pythonCommand) {
    throw '未找到 Python。请安装 Python 3.11+，或设置 TRUTHNET_PYTHON。'
  }
  $python = $pythonCommand.Source
}

& $python -c 'import fastapi, uvicorn' 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host '首次启动：安装后端依赖…' -ForegroundColor Cyan
  & $python -m pip install -r (Join-Path $repoRoot 'requirements.txt')
}

Push-Location $repoRoot
try {
  Write-Host "后端启动：http://$HostAddress`:$Port" -ForegroundColor Green
  & $python -m uvicorn app.main:app --app-dir backend --host $HostAddress --port $Port
} finally {
  Pop-Location
}
