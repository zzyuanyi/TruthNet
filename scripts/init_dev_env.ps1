# TruthNet 开发环境初始化脚本 (Windows PowerShell)
# 使用方法: .\scripts\init_dev_env.ps1
#
# Prompt3 更新: 改为调用 env_bootstrap.py --check 和 env_bootstrap.py --apply

Write-Host "===================================="
Write-Host "  TruthNet - 开发环境初始化 (Windows)"
Write-Host "===================================="
Write-Host ""

$RepoRoot = (Get-Item $PSScriptRoot).Parent.FullName
Set-Location $RepoRoot

# Step 0: 先运行环境检测
Write-Host "[0/2] 检测当前环境..."
python scripts/env_bootstrap.py --check
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  [WARN] 环境检测发现需要注意的事项，详见上方输出。"
}

Write-Host ""
Write-Host "[1/2] 执行环境配置..."
Write-Host "  即将执行: python scripts/env_bootstrap.py --apply"
Write-Host "  这将检测 conda/venv 状态并创建或激活环境。"
Write-Host "  不会自动下载 Miniconda。"
Write-Host ""

$confirm = Read-Host "  是否继续？(y/n) [y]"
if ($confirm -eq "n" -or $confirm -eq "N") {
    Write-Host "  已取消。你可以稍后手动运行:"
    Write-Host "    python scripts/env_bootstrap.py --apply"
    exit 0
}

python scripts/env_bootstrap.py --apply
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [WARN] 环境配置未完全成功，请查看上方输出。"
    Write-Host "  你也可以手动配置:"
    Write-Host "    conda create -n truthnet python=3.11 -y"
    Write-Host "    conda activate truthnet"
    Write-Host "    pip install -r requirements.txt"
    exit 1
}

# Step 2: 验证
Write-Host ""
Write-Host "[2/2] 运行环境验证..."
python scripts/doctor.py
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  [WARN] 环境检测存在警告或失败项，请查看上方输出"
} else {
    Write-Host ""
    Write-Host "  [OK] 环境检测全部通过！"
}

Write-Host ""
Write-Host "===================================="
Write-Host "  初始化完成"
Write-Host "===================================="
Write-Host ""
Write-Host "  开发前: python scripts/start_session.py"
Write-Host "  开发后: python scripts/end_session.py"
Write-Host "  启动后端: cd backend && uvicorn app.main:app --reload"
Write-Host "  前端（待初始化）: cd frontend && pnpm install && pnpm dev"
Write-Host ""
