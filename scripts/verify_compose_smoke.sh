#!/usr/bin/env bash
# TruthNet Compose 冒烟测试 — Phase D #9
#
# 使用独立 project name / 不同宿主机端口 / 独立卷，与本地服务完全隔离。
# 不做 `docker compose down -v` 作用于其他项目。
#
# 用法：
#   cp .env.compose.example .env.compose   # 填入真实密码/密钥
#   bash scripts/verify_compose_smoke.sh
#
# 若 Docker 不可用：输出 blocked_by_local_docker_unavailable 并退出码 2。

set -euo pipefail

PROJECT="truthnet-compose"
ENV_FILE=".env.compose"
BACKEND_PORT="${BACKEND_PORT:-8001}"
LOCAL_BACKEND="http://127.0.0.1:${BACKEND_PORT}"

if ! command -v docker >/dev/null 2>&1; then
  echo "blocked_by_local_docker_unavailable"
  exit 2
fi

echo "[1/6] 静态校验 compose 配置..."
docker compose --env-file "${ENV_FILE}" -p "${PROJECT}" config >/dev/null
echo "  OK compose config 有效"

echo "[2/6] 启动服务（独立 project/卷/端口）..."
docker compose --env-file "${ENV_FILE}" -p "${PROJECT}" up -d --build
echo "  OK 服务已启动"

echo "[3/6] 等待服务健康..."
for i in $(seq 1 30); do
  if curl -fsS "${LOCAL_BACKEND}/api/v1/healthz" >/dev/null 2>&1; then
    echo "  OK backend /healthz 响应"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "  FAIL backend 未就绪（30 次探测）"
    docker compose --env-file "${ENV_FILE}" -p "${PROJECT}" ps
    exit 1
  fi
  sleep 3
done

echo "[4/6] /readyz..."
curl -fsS "${LOCAL_BACKEND}/api/v1/readyz" >/dev/null && echo "  OK /readyz 响应"

echo "[5/6] API smoke（公司搜索）..."
curl -fsS "${LOCAL_BACKEND}/api/v1/companies?query=康美&limit=5" >/dev/null && echo "  OK 公司搜索响应"

echo "[6/6] 收集容器状态..."
docker compose --env-file "${ENV_FILE}" -p "${PROJECT}" ps --format 'table {{.Name}}\t{{.Status}}'

echo ""
echo "Compose smoke 通过（独立环境，不影响本地 MySQL/Neo4j）。"
