# TruthNet Docker Compose 一键部署 — Phase D #9

> 覆盖：backend + MySQL 8.4 + Neo4j 2025.06.1 + Chroma + BGE 缓存卷 + LLM 环境变量 + 报告输出卷。

## 前提

- Docker 28+ / Docker Compose v2+ 已安装。
- 本机已有本地 MySQL/Neo4j 不受影响（Compose 使用独立端口/卷/网络）。

## 快速开始

```bash
# 1. 准备环境变量（填入真实密码/密钥，不提交）
cp .env.compose.example .env.compose

# 2. 启动（独立 project name，与本地服务隔离）
docker compose --env-file .env.compose -p truthnet-compose up -d --build

# 3. 检查健康
curl http://127.0.0.1:8001/api/v1/healthz
curl http://127.0.0.1:8001/api/v1/readyz

# 4. 冒烟
bash scripts/verify_compose_smoke.sh

# 5. 停止（不删卷；不作用于其他项目）
docker compose --env-file .env.compose -p truthnet-compose down

# 6. 彻底清理（仅本项目的卷）
docker compose --env-file .env.compose -p truthnet-compose down -v
```

## 端口映射（避开本地服务）

| 服务 | 容器端口 | 宿主机 |
|------|---------|--------|
| backend | 8000 | 8001（`BACKEND_PORT`） |
| MySQL | 3306 | 3307（`MYSQL_PORT`） |
| Neo4j Bolt | 7687 | 7688（`NEO4J_BOLT_PORT`） |
| Neo4j HTTP | 7474 | 7475（`NEO4J_HTTP_PORT`） |

## 卷（独立命名，不触碰本地 `.local/`）

- `truthnet-compose-mysql-data` — MySQL 数据
- `truthnet-compose-neo4j-data` — Neo4j 数据
- `truthnet-compose-chroma-data` — Chroma 持久化
- `truthnet-compose-bge-cache` — BGE 嵌入模型缓存
- `truthnet-compose-report-data` — PDF 报告输出

## 数据导入（进入 backend 容器）

```bash
docker compose --env-file .env.compose -p truthnet-compose exec backend bash
python scripts/import_data.py --dry-run        # 预检（需先挂载 data/raw）
python scripts/neo4j_full_import.py            # Neo4j 全量图谱
```

> 注意：镜像默认不含 `data/raw` 赛方数据（不提交大文件）。
> 需要时用 `-v ./data/raw:/app/data/raw` 挂载本地数据目录。

## 版本约束

- MySQL 固定 `mysql:8.4`。
- Neo4j 固定 `neo4j:2025.06.1`（**禁止 2025.06.0**）。
- Python 固定 `python:3.11-slim-bookworm`。
- 不使用 `latest` 标签。

## 与本地服务隔离说明

- 独立 project name `truthnet-compose`；
- 宿主机端口全部避开本地（8000/3306/7687/7474）；
- 独立命名卷，不挂载用户真实 `.local/mysql_data` 或 `.local/neo4j`；
- `down -v` 只作用于本 project 的卷，不影响其他项目；
- 不停止本地 Windows MySQL/Neo4j，不覆盖本地 `.env`。

## 故障排查

```bash
# 查看日志
docker compose --env-file .env.compose -p truthnet-compose logs -f backend

# 仅重建 backend
docker compose --env-file .env.compose -p truthnet-compose up -d --build backend

# 检查健康
docker compose --env-file .env.compose -p truthnet-compose ps
```
