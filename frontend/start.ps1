<#!
.SYNOPSIS
启动 TruthNet 前端开发服务。首次运行自动按 pnpm-lock.yaml 安装依赖。
#>
param(
  [int]$Port = 0,
  [int]$BackendPort = 0
)

$ErrorActionPreference = 'Stop'
$frontendDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($Port -le 0) {
  $Port = if ($env:FRONTEND_PORT) { [int]$env:FRONTEND_PORT } else { 5000 }
}
if ($BackendPort -le 0) {
  $BackendPort = if ($env:BACKEND_PORT) { [int]$env:BACKEND_PORT } else { 8001 }
}
if (-not $env:VITE_API_BASE_URL) {
  $env:VITE_API_BASE_URL = "http://127.0.0.1:$BackendPort"
}

if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) {
  if (-not (Get-Command corepack -ErrorAction SilentlyContinue)) {
    throw '未找到 pnpm 或 corepack。请先安装 Node.js 20+。'
  }
  & corepack enable
  & corepack pnpm@9.0.0 --version | Out-Null
}

Push-Location $frontendDir
try {
  if (-not (Test-Path (Join-Path $frontendDir 'node_modules'))) {
    Write-Host '首次启动：按 pnpm-lock.yaml 安装前端依赖…' -ForegroundColor Cyan
    & pnpm install --frozen-lockfile
  }
  Write-Host "前端启动：http://127.0.0.1:$Port（后端：$env:VITE_API_BASE_URL）" -ForegroundColor Green
  & pnpm dev -- --host 127.0.0.1 --port $Port
} finally {
  Pop-Location
}
