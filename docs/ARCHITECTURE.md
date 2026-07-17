# 架构设计 — V12 Baseline

> **版本**: 2.0 | **基线**: V12 (2026-07-15)
> 设计依据: `TruthNet_综合设计方案_V12(2).md` §6 系统总体架构

## 架构全景

```text
┌────────────────────────────────────────────────────────────────┐
│ React + Vite + TypeScript                                      │
│ 对话 / 企业画像 / 对比 / 报告任务                              │
└───────────────────────────┬────────────────────────────────────┘
                            │ REST + WebSocket
┌───────────────────────────▼────────────────────────────────────┐
│ FastAPI API 层                                                  │
│ Router · Pydantic DTO · Exception Handler · Auth 预留 · Trace  │
└───────────────────────────┬────────────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────────────┐
│ Application 层                                                 │
│ SearchCompany · AnalyzeCompany · Compare · CreateReport         │
│ 会话 · 幂等 · 超时 · 缓存 · 部分成功 · Adapter 选择            │
└───────────────────────────┬────────────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────────────┐
│ LangGraph Agent 层                                             │
│ LoadContext → ResolveEntity → Plan → Parallel Modules           │
│ → CrossValidate → BuildClaims → Generate → Validate → Persist   │
└──────────────┬──────────────────┬──────────────────┬────────────┘
               │                  │                  │
        Finance Port        Graph Port        Retrieval/LLM Port
               │                  │                  │
┌──────────────▼──────────────────▼──────────────────▼────────────┐
│ Infrastructure Adapters                                        │
│ MySQL · Neo4j · ChromaDB · LLM Providers                       │
│ akshare · 文件解析 · 报告渲染                                  │
└────────────────────────────────────────────────────────────────┘
```

## 分层职责 (V12)

### API 层
- 请求解析和鉴权预留
- Pydantic 校验
- HTTP/WebSocket 契约
- 错误转换
- 不包含财务计算和数据库查询细节

### Application 层
- 执行业务用例
- 决定是否调用 Agent 或直接查询
- 管理 deadline、幂等、缓存和降级
- 组合 Port
- 返回 Domain DTO

### Domain 层
- 公司、财务规则、股权、事件、证据、风险和会话的核心模型
- 规则计算和不变量
- 不依赖 FastAPI、MySQL、Neo4j 或 SDK

### Agent 层
- 自然语言意图和主体消歧
- 生成执行计划
- 编排确定性工具
- 交叉验证结构化结果
- 生成基于证据的回答

### Infrastructure 层
- SQL、图、向量、外部数据、模型和报告实现
- 实现 Application Port
- 可切换、可测试、可降级

## Agent 节点流程

```text
LoadContext → ResolveEntity → PlanModules → ParallelModules
→ CrossValidate → BuildClaimsAndEvidence → GenerateAnswer
→ ValidateEvidenceAndSchema → PersistTurn
```

| 节点 | 职责 |
|------|------|
| LoadContext | 加载 session_id、thread_id、消息、当前主体、结构化记忆 |
| ResolveEntity | 用户问题 → CompanyRef 或候选列表 |
| PlanModules | 意图 → ExecutionPlan（simple_query 或 diagnose） |
| Finance | CompanyRef + as_of → FinanceResult + Evidence |
| Equity | CompanyRef + as_of + depth → EquityResult + Evidence |
| Events | CompanyRef + 时间窗 → EventResult + Evidence |
| CrossValidate | 三类结果 → CrossSignal + 模式候选 |
| BuildClaims | 结果 + Evidence → Claim 列表 |
| GenerateAnswer | Claim + 问题 + 上下文 → 自然语言答案 + 追问建议 |
| ValidateEvidence | 文本 + Claim → 校验通过或降级模板 |
| PersistTurn | 完整 State → 会话、checkpoint、审计日志 |

## 关键技术决策

| 领域 | 决策 | 状态 |
|------|------|:---:|
| Web 后端 | FastAPI | ✅ 已实施 |
| Agent 编排 | LangGraph StateGraph | 🔸 骨架已建 |
| 数据契约 | Pydantic V2 | ✅ 已实施 |
| 结构化存储 | MySQL 8.0 (full) / SQLite (lite) | ✅ 已实施 |
| 图存储 | Neo4j (full) / NetworkX (lite) | ✅ 已实施 |
| 向量存储 | ChromaDB | ✅ 已实施 |
| LLM | Provider Adapter; DeepSeek/Qwen/Mock | ✅ Adapter 已建 |
| 前端 | React + Vite + TypeScript | ✅ 已初始化 |
| UI | shadcn/ui + Tailwind CSS | 🔸 待接入 |
| 图表 | Recharts | 🔸 待接入 |
| 图谱 | D3.js | 🔸 待接入 |
| 测试 | pytest, Ruff, pre-commit, CI | ✅ 已实施 |
| 编码路径 | UTF-8, LF, pathlib.Path | ✅ 已实施 |
| Git | 成员分支 → PR → main | ✅ 已实施 |

## Port 协议

| Port | lite Adapter | full Adapter | 状态 |
|------|-------------|-------------|:---:|
| `CompanyRepository` | SQLite | MySQL | ✅ |
| `FinanceRepository` | SQLite | MySQL | 🔸 骨架 |
| `EquityGraphPort` | NetworkX | Neo4j | ✅ |
| `VectorStorePort` | ChromaDB | ChromaDB | ✅ |
| `LLMProvider` | Mock | DeepSeek / Qwen | ✅ Mock, 🔸 真实 |

## Evidence/Claim 体系

```
EvidenceRef (来源 → 字段 → 值 → 版本 → 哈希)
     │
     ▼
Claim (statement + confidence + evidence_ids + rule_id + verification_status)
     │
     ▼
AgentState (claims[] + evidence[] + results[])
```

- 事实型 Claim 至少一个 Evidence
- LLM 只能引用已提供的 `evidence_id`
- 所有数据带版本和时间 (`as_of`, `dataset_version`)
- 风险评分 = financial + equity + event + rating - data_quality_penalty

## 兼容策略

| 维度 | 旧 | 新 | 策略 |
|------|----|----|------|
| 健康检查 | GET /health | GET /healthz | 旧 deprecated |
| 响应格式 | {code, data, message, trace_id} | {data, meta, warnings} | 共存 |
| WebSocket | {type, data} | V12 event envelope | 共存 |
| 错误格式 | {code, message, trace_id} | RFC 9457 Problem Details | 新接口使用 |
