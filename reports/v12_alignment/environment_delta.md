# 环境变化报告 — V12 Alignment

> 生成时间：2026-07-17

## 1. 是否保留 conda truthnet？

**是。** conda `truthnet` 环境保持不变，仍然推荐使用。

## 2. 是否保留 Python 3.11？

**是。** `.python-version` 仍为 `3.11`。

注意：本地开发机当前运行 Python 3.12.7，这是预存问题，非本轮引入。

## 3. requirements 新增了哪些包？

| 包 | 版本 | 用途 |
|----|------|------|
| `sqlalchemy` | 2.0.35 | ORM 框架（MySQL/SQLite 统一访问） |
| `alembic` | 1.13.2 | 数据库迁移管理 |
| `pymysql` | 1.1.1 | MySQL 纯 Python 驱动（Windows 兼容） |
| `neo4j` | 5.26.0 | Neo4j Python 驱动 |
| `structlog` | 24.4.0 | 结构化日志（可选，lite 下回退到标准 logging） |
| `jsonschema` | 4.23.0 | JSON Schema 校验 |

总计：从 19 个包增加到 25 个包。

## 4. 新增包为什么必要？

- **sqlalchemy + alembic**：V12 正式 ORM 和 migration 方案
- **pymysql**：full profile MySQL adapter 的驱动
- **neo4j**：full profile Neo4j adapter 的驱动
- **structlog**：full profile 结构化日志（lite 回退标准 logging）
- **jsonschema**：OpenAPI/AsyncAPI spec 校验

## 5. 是否仍只有一个 requirements？

**是。** 没有新增 `requirements-dev.txt`、`requirements-full.txt` 等第二文件。所有依赖在唯一 `requirements.txt` 中。

## 6. 是否新增 MySQL/Neo4j 驱动？

**是。** `pymysql` (MySQL) 和 `neo4j` (Neo4j) 驱动已加入 `requirements.txt`。

## 7. MySQL/Neo4j 是否成为基础测试前置条件？

**否。** lite profile 下不要求 MySQL/Neo4j 服务在线。基础测试和 CI 不依赖外部数据库。

## 8. lite/full profile 如何使用？

- `TRUTHNET_PROFILE=lite`（默认）：使用 SQLite + NetworkX + ChromaDB local + Mock LLM
- `TRUTHNET_PROFILE=full`：使用 MySQL + Neo4j + ChromaDB persistent + DeepSeek/Qwen

通过 `.env` 或环境变量设置。

## 9. Windows/macOS/Linux 是否可继续运行？

**是。**
- `pymysql` 是纯 Python 实现，Windows 下无编译问题
- `neo4j` Python driver 跨平台
- 其他新增包均为纯 Python 或跨平台 wheel

## 10. 是否需要用户手动安装 MySQL/Neo4j？

**否（lite） / 是（full）。**
- lite profile：无需安装任何外部服务
- full profile：需要安装 MySQL 8.0 和 Neo4j，但这是后续阶段的正式演示需求
