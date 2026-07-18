---
name: api-contract-first
description: 接口先行原则。保证前后端接口设计先于实现、稳定、可 mock。
---

# API Contract-First（接口先行）

## 核心原则

**接口设计 → Schema 定义 → 文档更新 → Mock JSON → 实现代码**

开发任何 API 时必须严格遵循这个顺序。不允许跳过接口设计直接写实现。

## 开发流程

### 1. 先更新 Pydantic Schema

在 `backend/app/schemas/` 下创建或更新对应的 Pydantic 模型：

```python
# backend/app/schemas/chat.py
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    question: str = Field(..., description="用户问题")
    session_id: str | None = Field(None, description="会话ID")
    context: dict | None = Field(None, description="附加上下文")

class ChatResponse(BaseModel):
    answer: str
    evidence: list[dict] = []
    graph: dict = {}
    timeline: list[dict] = []
    risk_score: float = 0.0
    warnings: list[str] = []
    missing_modules: list[str] = []
    trace_id: str
```

### 2. 更新 docs/API_CONTRACT.md

在 `docs/API_CONTRACT.md` 中添加接口定义，包含：
- 接口路径和方法
- 请求字段说明
- 响应字段说明
- mock JSON 示例
- 错误格式
- 稳定性状态（✅ 稳定 / 🔶 MVP / 🔸 草案）

### 3. 更新 docs/INTERFACE_CHANGELOG.md

记录所有接口变更，包含：
- 变动类型（Added / Changed / Deprecated / Breaking）
- 影响范围
- 是否已审阅

### 4. 提供 Mock JSON

```json
{
  "code": 0,
  "data": {
    "answer": "示例回答...",
    "evidence": [],
    "graph": {},
    "timeline": [],
    "risk_score": 0.15,
    "warnings": [],
    "missing_modules": [],
    "trace_id": "mock-trace-id"
  },
  "message": "ok",
  "trace_id": "mock-trace-id"
}
```

## 统一响应结构

**所有** REST 接口必须遵循：

```json
{
  "code": 0,
  "data": {},
  "message": "ok",
  "trace_id": "uuid-string"
}
```

| code | 含义 |
|------|------|
| 0 | 成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 422 | 参数校验失败 |
| 500 | 服务器内部错误 |
| 503 | 服务不可用 |

## WebSocket 消息类型

| 类型 | 说明 |
|------|------|
| `status` | 处理状态更新 |
| `partial_answer` | 流式部分回答 |
| `final_answer` | 完整回答 |
| `error` | 错误信息 |

## 财报问答响应核心字段

每个问答响应必须覆盖：

- `answer` — Markdown 格式主回答
- `evidence` — 证据列表（来源、字段、值）
- `graph` — 图谱可视化的 nodes + edges
- `timeline` — 事件时间线
- `risk_score` — 0-1 风险评分
- `warnings` — 财务预警点
- `missing_modules` — 暂缺模块
- `trace_id` — 请求追踪 ID

## 接口修改规则

### 允许（无需特殊流程）
- ✅ 向响应追加新字段
- ✅ 向请求追加可选字段（有默认值）
- ✅ 添加全新的接口

### 需要完整变更流程
- ⚠️ 修改已有字段名
- ⚠️ 修改已有字段类型
- ⚠️ 删除已有字段
- ⚠️ 修改接口路径

### 破坏性修改必须
1. 在 `INTERFACE_CHANGELOG.md` 记录原因
2. 提供迁移方式
3. 保留兼容层或明确标注废弃版本
4. **请求用户审阅并确认**

## 禁止

- ❌ 前端私自改后端字段名
- ❌ 后端在 API 中直接暴露数据库字段
- ❌ 错误响应让前端"猜字段"
- ❌ 接口进入 dev 分支后再做破坏性修改（除非走完整流程）

---

## V12 更新（2026-07-17）

### V12 响应格式

新接口使用 V12 envelope：`{data, meta, warnings}`

```json
{
  "data": {},
  "meta": {
    "request_id": "req_01",
    "trace_id": "trace_01",
    "schema_version": "1.0",
    "generated_at": "2026-07-17T10:00:00+08:00",
    "data_as_of": "2026-06-30",
    "dataset_version": "mock-v12",
    "rule_set_version": "finance-rules-1.0.0",
    "graph_version": "equity-mock-v12"
  },
  "warnings": []
}
```

旧格式 `{code, data, message, trace_id}` 保留兼容。

### V12 错误格式

使用 RFC 9457 Problem Details：

```json
{
  "type": "https://truthnet/errors/module-timeout",
  "title": "Module execution timed out",
  "status": 503,
  "detail": "...",
  "instance": "/api/v1/companies/600518/risk",
  "error_code": "EQUITY_TIMEOUT",
  "trace_id": "trace_01",
  "recoverable": true
}
```

### V12 WebSocket Event Envelope

```json
{
  "schema_version": "1.0",
  "event_id": "evt_01",
  "event_type": "answer.delta",
  "session_id": "ses_01",
  "turn_id": "turn_01",
  "sequence": 8,
  "timestamp": "2026-07-17T10:00:05+08:00",
  "trace_id": "trace_01",
  "payload": {}
}
```

### V12 契约文档

- API: `docs/API_CONTRACT_V1.md`
- WebSocket: `docs/WEBSOCKET_CONTRACT_V1.md`
- Data: `docs/DATA_CONTRACT.md`
- 旧文档保留不删除

### 接口变更必须同步更新

1. Pydantic schema（`backend/app/api/v1/schemas/`）
2. `docs/API_CONTRACT_V1.md`
3. `docs/WEBSOCKET_CONTRACT_V1.md`
4. `docs/INTERFACE_CHANGELOG.md`
5. 后端测试
6. 前端 types
