---
name: software-engineering
description: 软件工程与设计模式。统一分层架构、设计模式使用位置、代码规范。
---

# 软件工程规范

## 分层架构

```text
API Layer       ← HTTP 请求/响应、参数校验、路由
Agent Layer     ← 编排推理流程：意图 → 路由 → 调度
Skill Layer     ← 确定性工具能力：图谱遍历、数据聚合
Service Layer   ← 业务服务：财务计算、风险分析
Repository      ← 数据访问：SQLite、NetworkX、ChromaDB
Schema Layer    ← Pydantic 数据契约（跨层 DTO）
```

### 各层规则

| 层 | 允许 | 禁止 |
|----|------|------|
| API | 参数校验、调用 Agent、组装响应 | ❌ 业务逻辑、SQL、财务规则 |
| Agent | 推理编排、工具决策 | ❌ 直接 SQL、直接 ChromaDB 操作 |
| Skill | 确定性算法、图遍历 | ❌ LLM 调用（那是 Agent 的事） |
| Service | 可复用业务计算 | ❌ HTTP 相关逻辑 |
| Repository | 数据的增删改查 | ❌ 业务判断 |
| Schema | 数据结构、校验 | ❌ 运行时逻辑 |

## 设计模式使用位置

### Strategy（策略模式）
**用途**：不同勾稽规则、不同风险评分策略
**位置**：`backend/app/agents/finance_agent.py` 内的 CheckStrategy

```python
class RevenueCashCheck(CheckStrategy):
    """营收与现金流入勾稽检查"""
    def check(self, data: FinancialData) -> CheckResult: ...
```

### Adapter（适配器模式）
**用途**：不同 LLM 提供商、嵌入模型、数据源
**位置**：`backend/app/core/llm.py`

```python
class LLMAdapter(ABC):
    @abstractmethod
    def chat(self, messages: list[dict]) -> str: ...
```

### Facade（外观模式）
**用途**：对前端暴露统一问答接口
**位置**：`backend/app/agents/orchestrator.py`

### Factory（工厂模式）
**用途**：创建 Agent/Skill/LLM Client
**位置**：`backend/app/core/factory.py`

### Repository（仓库模式）
**用途**：隔离数据库/图/向量库访问
**位置**：`backend/app/core/repositories.py`

### DTO / Schema
**用途**：固定跨层传输结构
**位置**：`backend/app/schemas/` 下的所有 Pydantic 模型

## 代码规范

### Python 命名

| 类型 | 规范 | 示例 |
|------|------|------|
| 模块 | snake_case | `ownership_skill.py` |
| 类 | PascalCase | `ChatRequest` |
| 函数 | snake_case | `get_company_risk()` |
| 常量 | UPPER_SNAKE | `MAX_OWNERSHIP_DEPTH` |
| 私有 | _leading_underscore | `_build_graph()` |

### 禁止事项

- ❌ API 里直接写复杂财务规则 → 放在 Service/Skill 层
- ❌ Agent 里直接拼 SQL → 通过 Repository
- ❌ 前端依赖后端临时字段 → 字段进入 Schema 才能用
- ❌ 大量业务逻辑散落在 `main.py` → 归入对应层
- ❌ 使用 `dict` 或裸 `list` 跨层传递 → 必须用 Pydantic model

## 测试要求

- 每个 `agents/` 模块 ≥ 1 个 smoke test
- 每个 `skills/` 模块 ≥ 1 个单元测试
- 每个 `api/` 路由 ≥ 1 个集成测试
- 关键业务规则必须有注释和文档出处

## 错误处理

1. API 层：FastAPI HTTPException，不暴露 traceback
2. Agent 层：填充 `missing_modules`，降级不崩溃
3. Service 层：抛自定义异常
4. 所有错误包含 `trace_id`

## 日志

```
[时间] [级别] [trace_id=xxx] 消息
```

工具调用必须记录：输入摘要、输出摘要、耗时、错误。

---

## V12 更新（2026-07-17）

### V12 分层架构（更新）

```text
API Layer        ← HTTP/WS 请求/响应、V12 envelope、Problem Details
Application      ← Use Cases、Port (Protocol)、DTO
Domain           ← 纯 Pydantic V2 模型（Company/Finance/Equity/Events/Risk/Evidence/Conversation）
Agent            ← LangGraph StateGraph + AgentState
Infrastructure   ← Adapters (SQLite/MySQL, NetworkX/Neo4j, ChromaDB, Mock/DeepSeek/Qwen)
```

### Adapter + Profile 策略

- lite profile: SQLite + NetworkX + Mock LLM（默认开发/CI）
- full profile: MySQL + Neo4j + DeepSeek/Qwen（正式演示）
- 所有 Adapter 实现对应 Port 协议
- 不强制 MySQL/Neo4j 作为基础测试前置条件

### Evidence/Claim 核心边界

- `EvidenceRef`: 证据引用（来源→字段→值→置信度）
- `Claim`: 结论声明（statement + confidence + evidence + counter_evidence）
- 每条回答由若干 Claim 组成，每个 Claim 有独立证据链

### 关键规则

- 不全面重建，同仓库增量重构
- 先保留已��测试和工程基线
- 新增依赖写入唯一 `requirements.txt`
- 外部服务通过 Adapter 和 profile 管理
