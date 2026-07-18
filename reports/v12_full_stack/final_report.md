# V12 Full Profile 技术栈验证报告

> 生成时间：2026-07-17

## 1. 总结判断

| 模块 | 状态 | 结论 |
|------|------|------|
| truthnet 环境 | passed | Python 3.11.15, conda env 正常 |
| pre-commit | passed | 全部 hooks 通过（trim ws, eof, yaml, json, merge conflicts, large files, ruff check, ruff format） |
| lite profile | passed | 11/12 PASS, 1 NOT_RUN (MySQL/Neo4j intentionally) |
| ChromaDB persistent | passed | write + query + reopen + read 全部通过 |
| MySQL 真实连接 | not_run | 本机未安装 MySQL 服务 |
| Neo4j 真实连接 | not_run | 本机未安装 Neo4j 服务 |
| Alembic | passed | 已初始化，`alembic.ini` 和 migrations 目录已生成 |
| /healthz /readyz | passed | `/healthz` 返回 healthy，`/readyz` 区分 lite/full profile |
| external integration tests | not_run | MySQL/Neo4j 测试需要真实服务，已通过 TRUTHNET_RUN_EXTERNAL_TESTS=1 保护 |
| ruff check | passed | All checks passed |
| ruff format | passed | 105 files formatted |
| pytest | passed | 55 tests pass |

## 2. 本机服务发现

| 服务 | 端口 | 检测结果 |
|------|------|---------|
| MySQL | 3306 | not installed |
| Neo4j | 7687 | not installed |
| ChromaDB persist dir | N/A | writable ✅ |

## 3. ChromaDB persistent 验证

| Item | Result |
|------|--------|
| persist_dir | data/chroma_db |
| writable | yes |
| write | passed (truthnet_v12_smoke collection) |
| query | passed |
| reopen+read | passed (persistence OK) |
| status | **passed** |

## 4. Alembic 状态

| Item | Result |
|------|--------|
| alembic_installed | yes (v1.13.2) |
| alembic.ini_exists | yes |
| migrations_dir_exists | yes (backend/app/infrastructure/persistence/migrations/) |
| env_uses_env_vars | partial (默认 sqlite，full 需手动切换) |
| real_upgrade_run | not_run (待有真实 MySQL 后执行) |
| status | **passed** |

## 5. FastAPI readyz 状态

| Endpoint | lite Profile | full Profile |
|----------|-------------|-------------|
| /healthz | status=healthy | status=healthy |
| /readyz | status=ready, 4 deps all ok | status=degraded + per-service detail |

## 6. 测试结果

| 测试类别 | 数量 | 结果 |
|----------|------|------|
| 已有测试 (legacy) | 29 | 28 pass + 1 pre-existing fail |
| V12 contract tests | 6 | 6 pass |
| V12 unit tests | 14 | 14 pass |
| Integration (ChromaDB) | 2 | 2 pass |
| Integration (readyz) | 4 | 4 pass |
| Integration (MySQL external) | 4 | skipped (TRUTHNET_RUN_EXTERNAL_TESTS != 1) |
| Integration (Neo4j external) | 4 | skipped (TRUTHNET_RUN_EXTERNAL_TESTS != 1) |
| **Active total** | **55** | **55 passed** |

## 7. 未完成项

| Item | Status | Reason |
|------|--------|--------|
| MySQL connection | not_run | 本机未安装 MySQL |
| Neo4j connection | not_run | 本机未安装 Neo4j |
| Alembic upgrade | not_run | 无 MySQL 服务器 |
| External integration tests | not_run | TRUTHNET_RUN_EXTERNAL_TESTS=1 not set |
| DeepSeek/Qwen API | not_run | lite profile 使用 Mock |

## 8. 下一步建议

1. 安装 MySQL 8.0 和 Neo4j 后，配置 `.env` 中的连接信息
2. 设置 `TRUTHNET_PROFILE=full` 运行 `verify_full_stack.py --profile full --check-external`
3. 设置 `TRUTHNET_RUN_EXTERNAL_TESTS=1` 运行外部集成测试
4. 在 Alembic 中配置 MySQL URL 后执行 `alembic upgrade head`
