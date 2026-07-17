# 依赖变化报告 — V12 Alignment

> 生成时间：2026-07-17

## 旧依赖（19 个包，全部保留）

fastapi, uvicorn, websockets, pydantic, pydantic-settings, python-dotenv, langgraph, langchain-core, langchain-openai, networkx, chromadb, pandas, numpy, scikit-learn, pytest, pytest-asyncio, httpx, ruff, pre-commit

## 新增依赖（6 个包）

| 包 | 版本 | 分类 | 原因 |
|----|------|------|------|
| sqlalchemy | 2.0.35 | ORM | MySQL/SQLite 统一 ORM 访问 |
| alembic | 1.13.2 | Migration | 数据库 Schema 版本管理 |
| pymysql | 1.1.1 | MySQL Driver | 纯 Python MySQL 驱动，Windows 兼容 |
| neo4j | 5.26.0 | Graph DB | Neo4j Python driver |
| structlog | 24.4.0 | Logging | 结构化日志（lite 回退标准 logging） |
| jsonschema | 4.23.0 | Validation | OpenAPI/AsyncAPI spec 校验 |

## 未引入的潜在依赖

| 包 | 原因 |
|----|------|
| mysqlclient | Windows 上需要编译 MySQL C 库，选择 pymysql 代替 |
| openapi-spec-validator | 本轮只建文档骨架，暂不引入 |
| prometheus-client | 可观测性为骨架阶段，后续引入 |
| opentelemetry | 同上 |

## 依赖冲突检查

- sqlalchemy 2.0.35 与现有 langchain 0.3 兼容
- alembic 1.13.2 依赖 sqlalchemy >=1.3.0
- pymysql 1.1.1 纯 Python，无 C 编译依赖
- 无已知依赖冲突
