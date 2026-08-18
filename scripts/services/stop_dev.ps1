# TruthNet 一键停止后端/前端（按端口识别，MySQL/Neo4j 保持运行）
#
# 用法:
#   powershell -ExecutionPolicy Bypass -File scripts/services/stop_dev.ps1
param(
  [int[]]$Port = @(8000, 5000)
)

$ErrorActionPreference = "Continue"

foreach ($p in $Port) {
  $conn = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
  if ($conn) {
    foreach ($c in $conn) {
      $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
      if ($proc) {
        Write-Host "停止端口 $p 进程 (pid $($c.OwningProcess) $($proc.ProcessName))" -ForegroundColor Yellow
        Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
      }
    }
  }
  else {
    Write-Host "端口 $p 无监听进程" -ForegroundColor DarkGray
  }
}

# 兜底: 关闭残留的 TruthNet 专用窗口（用户手动关窗后此处无操作）
Get-Process pwsh -ErrorAction SilentlyContinue |
  Where-Object { $_.MainWindowTitle -match "^TruthNet-(Backend|Frontend)$" } |
  ForEach-Object {
    Write-Host "关闭残留窗口 (pid $($_.Id))" -ForegroundColor DarkYellow
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
  }

Write-Host ""
Write-Host "完成。MySQL/Neo4j 保持运行。" -ForegroundColor Green
