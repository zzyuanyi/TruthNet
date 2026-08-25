#!/usr/bin/env bash
# TruthNet 全栈开发启动：后端(8000, lite/mock) + 前端(读 DEPLOY_RUN_PORT)
set -uo pipefail

ROOT="${COZE_WORKSPACE_PATH:-/workspace/projects}"
cd "$ROOT" || exit 1

LOG_DIR="${COZE_LOG_DIR:-/app/work/logs/bypass}"
mkdir -p "$LOG_DIR"

# 后端：lite/mock 模式，固定 8000；后台运行，失败不阻塞前端
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --log-level info \
  >> "$LOG_DIR/truthnet-backend.log" 2>&1 &
echo "TruthNet 后端启动中：http://127.0.0.1:8000 (pid $!)"

# 前端作为主进程（保持前台，读 DEPLOY_RUN_PORT）
exec pnpm run --dir frontend dev