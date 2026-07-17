# 技术栈导入矩阵

| Stack | Import | Minimal Smoke | Status | Notes |
|-------|--------|---------------|--------|-------|
| FastAPI | yes | app import (title="TruthNet API") | PASS | |
| Pydantic V2 | yes | model roundtrip (model_dump) | PASS | |
| Pydantic Settings | yes | settings import | PASS | |
| LangGraph | yes | StateGraph mini (TypedDict) | PASS | |
| LangChain Core | yes | import only | PASS | |
| ChromaDB | yes | ephemeral client + add/query | PASS | Windows temp file workaround applied |
| SQLAlchemy | yes | sqlite memory SELECT 1 | PASS | |
| Alembic | yes | command import (v1.13.2) | PASS | |
| PyMySQL | yes | driver import (v1.4.6) | PASS | Pure Python, no compilation needed |
| Neo4j | yes | driver import (v5.26.0) + GraphDatabase | PASS | No real server needed |
| structlog | yes | logger bind(component) | PASS | |
| jsonschema | yes | validate({name}, {required}) | PASS | |
| NetworkX | yes | small graph (1 node, DiGraph) | PASS | |
| pandas | yes | import only | PASS | |
| numpy | yes | import only | PASS | |
| pytest | yes | import only (v8.3.3) | PASS | |
| ruff | yes | import only | PASS | |
| pre-commit | yes | import only | PASS | |
| V12 Adapters | yes | SQLite + NetworkX + Mock LLM imports | PASS | Lite profile |

## 未验证项

| Item | Status | Reason |
|------|--------|--------|
| MySQL connection | not_run | lite profile; no MySQL server |
| Neo4j connection | not_run | lite profile; no Neo4j server |
| DeepSeek API | not_run | lite profile; mock only |
| Qwen API | not_run | lite profile; mock only |
| Alembic migration | not_run | `alembic init` not yet run |
| Pre-commit hooks | not_run | Requires `pre-commit install` |
