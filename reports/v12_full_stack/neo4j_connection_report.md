# Neo4j 连接验证报告

| Item | Value |
|------|-------|
| driver | neo4j v5.26.0 |
| uri_sanitized | bolt://localhost:7687 |
| auth | not_run (NEO4J_PASSWORD not configured) |
| return_1 | not_run |
| write_smoke | not_run |
| cleanup | not_run |
| status | **not_run** — Neo4j 未安装在本机 |

## 如何配置

1. 安装 Neo4j
2. 编辑 `.env`，设置 NEO4J_PASSWORD
3. 运行: `python scripts/verify_full_stack.py --profile full --check-external`
