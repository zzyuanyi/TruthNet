#!/usr/bin/env bash
# TruthNet 开发环境初始化脚本 (macOS/Linux)
# 使用方法: bash scripts/init_dev_env.sh
#
# Prompt3 更新: 改为调用 env_bootstrap.py --check 和 env_bootstrap.py --apply

set -e

echo "========================================="
echo "  TruthNet - 开发环境初始化 (macOS/Linux)"
echo "========================================="
echo ""

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Step 0: 先运行环境检测
echo "[0/2] 检测当前环境..."
python scripts/env_bootstrap.py --check || true

echo ""
echo "[1/2] 执行环境配置..."
echo "  即将执行: python scripts/env_bootstrap.py --apply"
echo "  这将检测 conda/venv 状态并创建或激活环境。"
echo "  不会自动下载 Miniconda。"
echo ""

read -r -p "  是否继续？(y/n) [y]: " confirm
confirm=${confirm:-y}
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "  已取消。你可以稍后手动运行:"
    echo "    python scripts/env_bootstrap.py --apply"
    exit 0
fi

python scripts/env_bootstrap.py --apply
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo "  [WARN] 环境配置未完全成功，请查看上方输出。"
    echo "  你也可以手动配置:"
    echo "    conda create -n truthnet python=3.11 -y"
    echo "    conda activate truthnet"
    echo "    pip install -r requirements.txt"
    exit 1
fi

# Step 2: 验证
echo ""
echo "[2/2] 运行环境验证..."
python scripts/doctor.py
EXIT_CODE=$?

echo ""
echo "========================================="
echo "  初始化完成"
echo "========================================="
echo ""
if [ $EXIT_CODE -ne 0 ]; then
    echo "  [WARN] 环境检测存在警告或失败项，请查看上方输出"
else
    echo "  [OK] 环境检测全部通过！"
fi
echo ""
echo "  开发前: python scripts/start_session.py"
echo "  开发后: python scripts/end_session.py"
echo "  启动后端: cd backend && uvicorn app.main:app --reload"
echo "  前端（待初始化）: cd frontend && pnpm install && pnpm dev"
echo ""
