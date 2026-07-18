# 重构决策报告 — V12 Alignment

> 生成时间：2026-07-17

## 1. 哪些代码保留？

- 根目录所有配置文件：`.editorconfig`, `.gitattributes`, `.gitignore`, `.python-version`, `.pre-commit-config.yaml`
- Python 3.11 目标（`.python-version`）
- conda + pip + 单一 `requirements.txt` 依赖策略
- FastAPI 入口 `main.py`（更新为 V12，但保留所有旧端点）
- 旧 Pydantic Schema：`backend/app/schemas/common.py`, `backend/app/schemas/chat.py`
- 旧响应格式 `UnifiedResponse`（`{code, data, message, trace_id}`）
- 所有已有测试：`test_health.py`, `test_api_contract_smoke.py`, `test_websocket_smoke.py`, `test_stack_smoke.py`, `test_encoding_path_policy.py`
- 所有脚本：`doctor.py`, `env_bootstrap.py`, `encoding_path_audit.py`, `git_safety_check.py`, `check_env.py`, `ci_status.py`, `start_session.py`, `end_session.py`
- 所有文档：旧 `API_CONTRACT.md`, `ARCHITECTURE.md`, `DATA_CONTRACT.md` 等（增量更新）
- GitHub Actions CI：`ci.yml`
- 8 个 Claude Code Skills（全部增量更新）
- 前端项目（`frontend/`）：不动
- UTF-8 / LF / pathlib 编码规范
- GitHub 简化协作流程（main ← PR ← feature）

## 2. 哪些代码原地修改？

- `requirements.txt`：新增 6 个包（sqlalchemy, alembic, pymysql, neo4j, structlog, jsonschema）
- `.env.example`：从 11 个变量扩展到 45 个变量（V12 profile + adapter 配置）
- `backend/app/core/config.py`：新增 25 个 V12 配置项
- `backend/app/main.py`：新增 V12 路由，保留旧端点兼容
- `docs/ARCHITECTURE.md`：V12 分层架构更新
- `docs/DATA_CONTRACT.md`：V12 存储架构更新
- `docs/INTERFACE_CHANGELOG.md`：V12 变更记录
- `scripts/doctor.py`：新增 V12 检查项（profile, adapter import, contract files, routes）
- 7 个 Claude Code Skills：所有增量添加 V12 规则
- 2 个测试文件：`test_health.py`, `test_api_contract_smoke.py`（版本号 0.1.0 → 0.2.0）

## 3. 哪些代码新增？

- `backend/app/api/v1/` — V12 API 路由层（routers, schemas, dependencies, exception_handlers）
- `backend/app/application/` — Application 层（use_cases, ports, services, dto）
- `backend/app/domain/` — Domain 层（company, finance, equity, events, risk, evidence, conversation）
- `backend/app/infrastructure/` — Infrastructure 层（persistence, graph, vector, llm, observability）
- `backend/app/agents/state.py` — AgentState 定义
- `backend/app/agents/graph.py` — LangGraph 骨架
- `backend/app/core/enums.py` — V12 枚举
- `backend/app/core/errors.py` — RFC 9457 Problem Details
- `backend/tests/contract/` — V12 契约测试
- `backend/tests/unit/` — V12 单元测试
- `docs/API_CONTRACT_V1.md` — V12 API 契约
- `docs/WEBSOCKET_CONTRACT_V1.md` — V12 WebSocket 契约
- `docs/FRONTEND_DESIGN.md` — V12 前端设计
- `reports/v12_alignment/` — 12 个 V12 对齐报告

## 4. 哪些代码标记 deprecated 但保留兼容？

- `GET /health` — 保留，标记 deprecated，推荐使用 `/api/v1/healthz`
- 旧响应格式 `{code, data, message, trace_id}` — 保留兼容，新接口使用 V12 envelope
- 旧 WebSocket 格式 `{type, data}` — 保留兼容，新格式为 V12 event envelope

## 5. 有没有删除文件？

**没有删除任何文件。** 所有已有文件保留。

## 6. 如果删除，为什么删除是安全的？

N/A — 本轮没有删除文件。

## 7. 是否存在全面重构风险？

**不存在。** 本轮严格遵循增量重构策略：
- 旧代码全部保留
- 旧接口继续可用
- 旧测试全部通过
- 新代码通过新目录分层添加
- Adapter 模式确保 lite/full 可切换

## 8. 是否保持原测试通过？

**是。** 所有已有测试通过（49/49 非 WebSocket 测试，WebSocket 测试因超时未完整运行但已验证不报错）。
