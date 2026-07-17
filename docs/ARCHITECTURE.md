# 架构设计 — V12 Baseline

> **版本**: 2.0
> **基线**: V12 (2026-07-17)

## 系统分层 (V12)

```text
┌──────────────────────────────────────────────────┐
│               前端 (React 18)                     │
│    shadcn/ui / Tailwind / Recharts / D3.js       │
├──────────────────────────────────────────────────┤
│           API 层 (FastAPI)                        │
│    REST: /api/v1/*          (V12 envelope)       │
│    WebSocket: /api/v1/chat/ws  (V12 event env)   │
│    兼容: /health, 旧格式保留                      │
├──────────────────────────────────────────────────┤
│         Application 层                            │
│    Use Cases / Ports (Protocol) / DTOs            │
│    不依赖 FastAPI，不依赖具体数据库                │
├──────────────────────────────────────────────────┤
│           Domain 层 (纯 Pydantic V2)              │
│    Company / Finance / Equity / Events            │
│    Risk / Evidence / Conversation                 │
├──────────────────────────────────────────────────┤
│         Agent 层 (LangGraph StateGraph)           │
│    Orchestrator / Memory / Finance / QA           │
│    State (AgentState) / Graph / Reducers          │
├──────────────────────────────────────────────────┤
│        Infrastructure 层 (Adapters)               │
│    ┌──────────┬──────────┬────────────────────┐  │
│    │ SQLite   │ MySQL    │ Persistence         │  │
│    │ NetworkX │ Neo4j    │ Graph               │  │
│    │ ChromaDB │          │ Vector              │  │
│    │ Mock     │ DeepSeek │ Qwen   LLM          │  │
│    │ Logging  │ Tracing  │ Metrics  Observ.    │  │
│    └──────────┴──────────┴────────────────────┘  │
└──────────────────────────────────────────────────┘
```

## V12 关键架构决策

| 决策 | 选择 | 原因 |
|------|------|------|
| 分层模式 | Application / Domain / Infrastructure | 端口-适配器，可测试，可替换 |
| Adapter 策略 | lite (SQLite/NetworkX/Mock) + full (MySQL/Neo4j/DeepSeek) | 渐进式迁移，不阻塞本地开发 |
| Profile 机制 | TRUTHNET_PROFILE=lite\|full | 环境切换，CI 不依赖外部服务 |
| Agent 状态 | LangGraph StateGraph + AgentState | 类型安全，支持条件路由 |
| 响应格式 | V12 envelope {data, meta, warnings} | 向后兼容旧 {code, data, message} |
| 错误格式 | RFC 9457 Problem Details | 标准化，可恢复标记 |
| 证据模型 | EvidenceRef + Claim | 回答可信性核心边界 |
| 测试分层 | contract / unit | 契约验证 + 单元隔离 |

## Port 协议（5 个）

| Port | lite Adapter | full Adapter |
|------|-------------|-------------|
| `CompanyRepository` | SQLite | MySQL |
| `FinanceRepository` | SQLite | MySQL |
| `EquityGraphPort` | NetworkX | Neo4j |
| `VectorStorePort` | ChromaDB | ChromaDB |
| `LLMProvider` | Mock | DeepSeek / Qwen |

## 兼容策略

| 维度 | 旧 | 新 | 策略 |
|------|----|----|------|
| 健康检查 | GET /health | GET /api/v1/healthz | 旧保留，标记 deprecated |
| 就绪检查 | 无 | GET /api/v1/readyz | 新增 |
| 响应格式 | {code, data, message, trace_id} | {data, meta, warnings} | 共存，旧测试不回归 |
| WebSocket | {type, data} | V12 event envelope | 共存 |
| 错误格式 | {code, message, trace_id} | RFC 9457 Problem Details | 新增 |
