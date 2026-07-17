# V12 差异审计

> 基于任务描述中的 V12 设计要求（`TruthNet_综合设计方案_V12(2).md` 内容已整合到任务指令中），与当前仓库状态进行逐项对比。
> 注意：V12 设计文件本身不在仓库中，本审计以任务指令中描述的 V12 目标为准。

## 审计方法

每项 V12 要求对比当前仓库状态，给出决策和本轮动作。

决策类型：
- `keep` — 保留不动
- `modify` — 原地修改
- `add` — 新增
- `deprecate_keep_compat` — 标记废弃但保留兼容
- `postpone` — 本轮暂缓
- `remove_only_if_proven_safe` — 仅在有充分证据时删除

---

## 基础环境

| V12 要求 | 当前仓库状态 | 决策 | 原因 | 本轮动作 |
|----------|------------|------|------|---------|
| Python 3.11 | `.python-version` 写 3.11，但本地运行 3.12.7 | keep | 保持 3.11 目标，本地环境差异不影响仓库 | 不改变 `.python-version` |
| conda 环境 `truthnet` | conda 已配置，推荐使用 | keep | 现有环境策略合理 | 保留 |
| 单一 requirements.txt | 已存在，19 个包全部 `==` | modify | 需增量添加 V12 依赖 | 新增 sqlalchemy, alembic, pymysql, neo4j, structlog 等 |
| UTF-8 / LF / pathlib | 已强制执行 | keep | 规范已硬化 | 保留 |
| 禁止硬编码盘符 | 已配置 | keep | 规范已硬化 | 保留 |

## 后端框架与核心库

| V12 要求 | 当前仓库状态 | 决策 | 原因 | 本轮动作 |
|----------|------------|------|------|---------|
| FastAPI | 0.115.0，已使用 | keep | 版本满足 | 保留 |
| LangGraph StateGraph | 0.2.55，已安装但未使用 StateGraph | modify | 需要升级到 StateGraph 用法 | 新增 agents/state.py, agents/graph.py 骨架 |
| Pydantic V2 | 2.9.2，已使用 | keep | 版本满足 | 保留 |
| ChromaDB | 0.5.23，已安装 | keep | 版本满足 | 保留 |

## 存储层

| V12 要求 | 当前仓库状态 | 决策 | 原因 | 本轮动作 |
|----------|------------|------|------|---------|
| SQLite（lite adapter） | 已作为默认数据库 | keep | 继续作为 lite profile 默认 | 保留，新增 SQLite adapter |
| MySQL 8.0（full） | 无 | add | V12 正式目标 | 新增 MySQL adapter 骨架，不强制安装 |
| NetworkX（lite adapter） | 3.3，已安装 | keep | 继续作为 lite profile 默认 | 保留，新增 NetworkX adapter |
| Neo4j（full） | 无 | add | V12 正式目标 | 新增 Neo4j adapter 骨架，不强制安装 |
| SQLAlchemy | 无 | add | V12 要求 ORM | 新增依赖和最小配置 |
| Alembic | 无 | add | V12 要求 migration | 新增依赖和最小配置 |

## LLM Provider

| V12 要求 | 当前仓库状态 | 决策 | 原因 | 本轮动作 |
|----------|------------|------|------|---------|
| DeepSeek（主） | 无 | add | V12 主 Provider | 新增 adapter 空实现 |
| Qwen（备选） | 无 | add | V12 备选 Provider | 新增 adapter 空实现 |
| Mock（lite） | 隐含存在（main.py hardcoded） | modify | 需要显式化为 Mock adapter | 新增 MockLLMProvider |
| Provider Adapter 模式 | 无 | add | V12 架构要求 | 新增 LLMProvider Protocol |

## 前端

| V12 要求 | 当前仓库状态 | 决策 | 原因 | 本轮动作 |
|----------|------------|------|------|---------|
| React + Vite + TypeScript | ✅ 已初始化，构建通过 | keep | 满足 V12 | 保留 |
| shadcn/ui + Tailwind CSS | ❌ 未集成 | postpone | 本轮重点是后端契约 | 标记为后续任务 |
| Recharts | ❌ 未集成 | postpone | 本轮重点是后端契约 | 标记为后续任务 |
| D3.js | ❌ 未集成 | postpone | 本轮重点是后端契约 | 标记为后续任务 |

## API 契约

| V12 要求 | 当前仓库状态 | 决策 | 原因 | 本轮动作 |
|----------|------------|------|------|---------|
| `/healthz` | 无，只有 `/health` | add | V12 标准端点 | 新增 `/healthz`，保留 `/health` |
| `/readyz` | 无 | add | V12 就绪检查 | 新增 |
| `POST /api/v1/chat` | 已存在 | modify | 需要 V12 响应格式 | 新增 V12 envelope，保留旧格式兼容 |
| `WS /api/v1/chat/ws` | 已存在 | modify | 需要 V12 event envelope | 新增 V12 envelope，保留旧格式兼容 |
| `GET /api/v1/companies` | 无 | add | V12 公司搜索 | 新增 mock 端点 |
| V12 响应格式 `{data, meta, warnings}` | 无，当前是 `{code, data, message, trace_id}` | add | V12 新格式 | 新增 V12Response，旧格式兼容 |
| RFC 9457 Problem Details | 无 | add | V12 错误格式 | 新增 ProblemDetails 模型 |
| WebSocket event envelope | 当前简单 `{type, data}` | modify | V12 要求完整 envelope | 新增 WS event envelope |
| partial success | 无 | postpone | 本轮先建模型 | 骨架 |

## Agent 架构

| V12 要求 | 当前仓库状态 | 决策 | 原因 | 本轮动作 |
|----------|------------|------|------|---------|
| Agent State（LangGraph） | 无 StateGraph | add | V12 核心 | 新增 agents/state.py |
| Application/Port/Adapter 分层 | 无 | add | V12 架构 | 新增 application/, infrastructure/ |
| Evidence/Claim 模型 | Evidence 字段简单 | modify | V12 需要增强 | 新增 EvidenceRef, Claim 模型 |
| CompanyRef | 无 | add | V12 领域模型 | 新增 |
| RiskLevel 枚举 | 隐含在 RiskScore | add | V12 显式枚举 | 新增 |
| ModuleStatus 枚举 | missing_modules 是字符串列表 | modify | V12 结构化 | 新增 ModuleStatus |
| ExecutionPlan | 无 | add | V12 Runtime | 新增骨架 |
| observability context | trace_id 已存在 | modify | V12 需要更完整 | 新增 infrastructure/observability/ |

## CI / 质量

| V12 要求 | 当前仓库状态 | 决策 | 原因 | 本轮动作 |
|----------|------------|------|------|---------|
| pytest | ✅ 28/29 通过 | keep | 满足 | 保留，修复 1 个预存失败 |
| Ruff | ✅ 通过 | keep | 满足 | 保留 |
| pre-commit | ✅ 配置 | keep | 满足 | 保留 |
| CI 3 平台 | ✅ ubuntu/win/mac | keep | 满足 | 保留，增加 doctor --ci |
| CI 不依赖 MySQL/Neo4j | ✅ | keep | 满足 | 保持 |
| push 后检查 CI | scripts/ci_status.py 存在 | keep | 满足 | 保留 |

## Git 协作

| V12 要求 | 当前仓库状态 | 决策 | 原因 | 本轮动作 |
|----------|------------|------|------|---------|
| main ← PR ← feature 分支 | ✅ 已实施 | keep | 满足 | 保留 |
| 不自动 commit/push/merge | ✅ 规范已硬化 | keep | 满足 | 保留 |
| 不直接 push main | ✅ | keep | 满足 | 保留 |

## 文档

| V12 要求 | 当前仓库状态 | 决策 | 原因 | 本轮动作 |
|----------|------------|------|------|---------|
| API_CONTRACT_V1.md | 无，有 API_CONTRACT.md | add | V12 版本化 | 新增 V1，保留旧文档 |
| WEBSOCKET_CONTRACT_V1.md | 无，WS 在 API_CONTRACT.md 中 | add | V12 独立文档 | 新增 |
| DATA_CONTRACT.md | 已存在 | modify | V12 更新 | 增量更新 |
| FRONTEND_DESIGN.md | 无 | add | V12 新文档 | 新增 |
| OpenAPI spec 文件 | 无 | postpone | 本轮先建文档 | 标记 |
| AsyncAPI spec 文件 | 无 | postpone | 本轮先建文档 | 标记 |

## Profile 机制

| V12 要求 | 当前仓库状态 | 决策 | 原因 | 本轮动作 |
|----------|------------|------|------|---------|
| TRUTHNET_PROFILE=lite\|full | 无 | add | V12 核心机制 | 新增配置 |
| SQL_BACKEND | 无 | add | lite/full 切换 | 新增配置 |
| GRAPH_BACKEND | 无 | add | lite/full 切换 | 新增配置 |
| VECTOR_BACKEND | 无 | add | lite/full 切换 | 新增配置 |
| LLM_BACKEND | 无 | add | lite/full 切换 | 新增配置 |

## 审计统计

| 类别 | keep | modify | add | postpone | deprecate_keep_compat |
|------|------|--------|-----|----------|----------------------|
| 基础环境 | 5 | 1 | 0 | 0 | 0 |
| 后端框架 | 4 | 1 | 0 | 0 | 0 |
| 存储层 | 2 | 0 | 5 | 0 | 0 |
| LLM Provider | 0 | 1 | 3 | 0 | 0 |
| 前端 | 1 | 0 | 0 | 3 | 0 |
| API 契约 | 0 | 3 | 5 | 1 | 1 |
| Agent 架构 | 0 | 3 | 7 | 0 | 0 |
| CI/质量 | 5 | 0 | 0 | 0 | 0 |
| Git 协作 | 3 | 0 | 0 | 0 | 0 |
| 文档 | 0 | 1 | 4 | 2 | 0 |
| Profile | 0 | 0 | 5 | 0 | 0 |
| **合计** | **20** | **10** | **29** | **6** | **1** |

## 结论

**当前策略：保留工程外壳，重构核心契约与分层；不得全面删除重建。**

V12 适配的核心工作是：
1. 新增 Application/Port/Adapter 分层（29 项 add）
2. 修改 API/WebSocket 契约格式（10 项 modify）
3. 保留所有已有工程基线（20 项 keep）
4. 前端升级推迟到后续阶段（6 项 postpone）
5. 旧 /health 端点标记 deprecated 但保留（1 项 deprecate_keep_compat）
