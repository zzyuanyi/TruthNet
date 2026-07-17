# Interface Changelog

> 记录所有接口、Schema、数据库结构的变更历史。
> 破坏性修改必须在此记录并请求项目负责人审阅。

---

## 模板

```markdown
## YYYY-MM-DD

### Changed
- 修改了什么字段 / 接口 / 表
- 原因
- 影响范围

### Added
- 新增了什么

### Deprecated
- 废弃了什么，预计何时删除

### Breaking Changes
- 是否有破坏性修改：
- 影响前端：
- 影响后端：
- 迁移方式：
- 是否已由项目负责人审阅：
```

---

## 2026-07-02 — Prompt4：前端初始化 + 接口冻结 + GitHub 协作简化

### Changed
- `POST /api/v1/chat` 响应：`risk_score` 字段从 `float` 升级为 `RiskScore` 对象
  - 新结构：`{"overall": 0.15, "financial": 0.10, "ownership": 0.20, "sentiment": 0.05}`
  - **破坏性变更**：类型从 float 变为 object
  - 已同步更新：backend schema, frontend types, 后端测试, API 文档
- `WS /api/v1/chat/ws` final_answer.data 结构同步 HTTP ChatData（含新 risk_score）
- GitHub 协作模型从 `main→dev→feature` 简化为 `main←PR←feature`

### Added
- 前端 React + Vite + TypeScript 项目初始化（22 个文件）
- 前端类型 `frontend/src/types/api.ts` 与 backend schema 完全对齐
- 前端组件：ChatPanel, RiskPanel, EvidenceList, TimelinePanel, GraphPanel
- HTTP 客户端 + WebSocket 客户端代码
- CI frontend job（typecheck + build）
- `reports/prompt4/` 全部报告

### Breaking Changes
- `risk_score` 从 float 变为 RiskScore 对象 — **破坏性变更**
- 影响前端：需更新 RiskPanel 组件（已完成）
- 影响后端：所有引用 risk_score 的代码（已更新）
- 迁移方式：前端使用 `risk_score.overall` 替代 `risk_score`
- 是否已由项目负责人审阅：✅ Prompt4 冻结评审

### Deprecated
- dev 分支不再强制要求（保留为历史参考）

---

## 2026-07-02 — Prompt3：WebSocket 最小 mock 实现

### Changed
- `WS /api/v1/chat/ws` 从「合同占位」升级为「最小 mock 实现」
  - 接收 `{"type": "question", "data": {"question": "..."}}` 格式
  - 返回 status → partial_answer → final_answer 三类消息
  - 错误时返回 error 消息
  - 所有消息包含 trace_id
  - 不调用真实 LLM，不访问真实数据
- `docs/API_CONTRACT.md` 更新 WebSocket 章节：
  - 补充客户端发送消息格式表
  - 补充每条消息的详细字段说明
  - 状态从 🔶 MVP 更新为 🔶 MVP（已实现最小 mock 端点，Prompt3）

### Added
- 新增 `backend/tests/test_websocket_smoke.py` WebSocket smoke 测试
- 新增 `backend/app/schemas/chat.py` 中的 WSMessage/WSStatusData/WSPartialAnswerData schema（Prompt1 已创建）
- WebSocket 端点错误处理：无效 JSON、缺少 question 字段

### Breaking Changes
- 无破坏性修改
- 是否已由项目负责人审阅：✅ Prompt3 基线

---

## 2026-07-17 — V12 文档对齐更新

### Changed
- `docs/API_CONTRACT_V1.md`: 更新为 V12 完整端点列表（18 个端点）、部分成功格式、公共查询参数
- `docs/ARCHITECTURE.md`: 更新为 V12 完整架构（Agent 节点流程、Evidence/Claim 体系、分层职责）
- `docs/WEBSOCKET_CONTRACT_V1.md`: 更新为 V12 完整 WS 契约（Client→Server 事件、artifact.upsert、重连恢复）
- `docs/DATA_CONTRACT.md`: 更新为 V12 数据架构（分层模型、MySQL 表结构、Neo4j 图模型、ChromaDB Collections）
- `docs/FRONTEND_DESIGN.md`: 更新为 V12 前端设计（页面路由、组件树、响应式、风险视觉规范、WS Reducer、无障碍）
- `CLAUDE.md`: 更新引用最新设计文档

### Design Baseline
- 设计依据: `TruthNet_综合设计方案_V12(2).md` (2026-07-15)
- 覆盖: §1 产品概述, §4-5 前端设计, §6 系统架构, §7 Agent 设计, §8 业务设计, §9 证据体系, §10 数据架构, §11-12 REST/WS 契约, §14 安全, §15 可观测性, §16 测试与 CI, §19 迁移策略

---

## 2026-07-17 — V12：设计对齐与增量重构基线

### Changed
- `POST /api/v1/chat` 响应：新增 V12 response envelope `{data, meta, warnings}` 格式
  - 旧 `{code, data, message, trace_id}` 格式保留兼容
  - **非破坏性变更**：旧客户端不受影响
- `WS /api/v1/chat/ws`：新增 V12 event envelope 格式
  - 新增 `schema_version`, `event_id`, `session_id`, `turn_id`, `sequence`, `timestamp` 字段
  - 新增事件类型: `turn.accepted`, `module.started`, `answer.delta`, `artifact.upsert`, `turn.completed`, `turn.failed`, `heartbeat`
  - 旧 `{type, data}` 格式保留兼容
- `GET /health` 标记为 deprecated（保留兼容），新增 `GET /api/v1/healthz`
- `requirements.txt` 新增 6 个 V12 依赖：sqlalchemy, alembic, pymysql, neo4j, structlog, jsonschema
- `backend/app/core/config.py` 新增 V12 配置项：TRUTHNET_PROFILE, SQL_BACKEND, GRAPH_BACKEND, VECTOR_BACKEND, LLM_BACKEND, MySQL/Neo4j 连接, DeepSeek/Qwen Provider, 数据版本字段
- `backend/app/schemas/` 保留不动，新增 `backend/app/api/v1/schemas/` V12 schema
- 目录结构：新增 `application/`, `domain/`, `infrastructure/` 分层

### Added
- 新增 `/api/v1/healthz`（进程存活探针）
- 新增 `/api/v1/readyz`（就绪探针，lite profile 不依赖外部服务）
- 新增 `GET /api/v1/companies?query=`（公司搜索，mock）
- 新增 V12 响应格式：`V12Response[T]` = `{data, meta, warnings}`
- 新增 RFC 9457 Problem Details 错误格式：`ProblemDetail`
- 新增核心领域模型：`CompanyRef`, `EvidenceRef`, `Claim`, `ConfidenceLevel`, `EvidenceType`
- 新增枚举：`RiskLevel`, `ModuleStatus`, `Profile`, `BackendType`
- 新增 Port 协议（5 个）：`CompanyRepository`, `FinanceRepository`, `EquityGraphPort`, `VectorStorePort`, `LLMProvider`
- 新增 Adapter 骨架：
  - SQLite: `CompanyRepository`, `FinanceRepository`（lite）
  - MySQL: `CompanyRepository`（full，骨架）
  - NetworkX: `EquityGraph`（lite）
  - Neo4j: `EquityGraph`（full，骨架）
  - ChromaDB: `VectorStore`（lite/full 共用）
  - Mock: `LLMProvider`（lite）
  - DeepSeek: `LLMProvider`（full，骨架）
  - Qwen: `LLMProvider`（full，骨架）
- 新增 Agent State (`agents/state.py`) 和 Agent Graph 骨架 (`agents/graph.py`)
- 新增可观测性骨架：logging, tracing, metrics
- 新增 V12 契约文档：`API_CONTRACT_V1.md`, `WEBSOCKET_CONTRACT_V1.md`, `FRONTEND_DESIGN.md`
- 新增 V12 测试：contract tests (API v1 + WS v1), unit tests (models + ports/mock + healthz/readyz)
- 新增 `TRUTHNET_PROFILE=lite|full` profile 机制
- 更新 `doctor.py` 增加 V12 检查项
- 更新 `.env.example` 增加 45 个 V12 配置变量
- 更新 7 个 skills 同步 V12 规则
- 生成 `reports/v12_alignment/` 完整报告（12 个文件）

### Deprecated
- `GET /health` — 保留兼容，推荐使用 `GET /api/v1/healthz`
- 旧响应格式 `{code, data, message, trace_id}` — 保留兼容，推荐使用 V12 envelope
- 旧 WebSocket 格式 `{type, data}` — 保留兼容，推荐使用 V12 event envelope

### Breaking Changes
- 无破坏性修改 — 所有旧接口和格式保留兼容
- 是否已由项目负责人审阅：⏳ 待审阅（V12 对齐基线）

---

## 2024-07-02 — 初始工程基线

### Added
- 创建 `docs/API_CONTRACT.md` MVP 版接口草案
  - `POST /api/v1/chat` (REST)
  - `WS /api/v1/chat/ws` (WebSocket)
  - `POST /api/v1/files/upload`
  - `GET /api/v1/companies/{company_id}/risk`
  - `GET /api/v1/companies/{company_id}/ownership`
  - `GET /api/v1/companies/{company_id}/timeline`
  - `GET /health`
- 创建 `docs/DATA_CONTRACT.md` SQLite / NetworkX / ChromaDB 数据边界定
- 创建 `backend/app/schemas/common.py` 统一响应格式
- 创建 `backend/app/schemas/chat.py` 对话相关 schema

### Changed
- 无（初始版本）

### Deprecated
- 无

### Breaking Changes
- 无破坏性修改（初始版本）
- 是否已由项目负责人审阅：✅ 初始基线
