# WebSocket 契约 V1 — V12 Baseline

> **版本**: 1.0 | **基线**: V12 (2026-07-15) | **端点**: `ws://localhost:8000/api/v1/chat/ws`
> 设计依据: `TruthNet_综合设计方案_V12(2).md` §12 WebSocket 契约

---

## V12 统一事件信封

```json
{
  "schema_version": "1.0",
  "event_id": "evt_01",
  "event_type": "answer.delta",
  "session_id": "ses_01",
  "turn_id": "turn_01",
  "sequence": 8,
  "timestamp": "2026-07-15T10:00:05+08:00",
  "trace_id": "trace_01",
  "payload": {}
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | string | 固定 `"1.0"` |
| `event_id` | string | 事件唯一 ID |
| `event_type` | string | 事件类型 |
| `session_id` | string | 会话 ID |
| `turn_id` | string | 轮次 ID |
| `sequence` | int | 单调递增序号 |
| `timestamp` | string | ISO 8601 时间戳 |
| `trace_id` | string | 追踪 ID (UUID4) |
| `payload` | object | 事件数据 |

---

## Client → Server 事件

| `event_type` | Payload | 说明 |
|------|------|------|
| `chat.query` | text, session_id, 可选 as_of | 发起问答 |
| `company.confirm` | company_ref, session_id, turn_id | 确认候选公司 |
| `chat.follow_up` | text, session_id | 追问 |
| `turn.cancel` | turn_id | 取消当前轮次 |
| `stream.resume` | turn_id, last_received_sequence | 断线重连 |
| `ping` | client_time | 心跳 |

## Server → Client 事件

| `event_type` | 说明 | 状态 |
|------|------|:---:|
| `turn.accepted` | 请求已接收，分配 turn_id | ✅ |
| `company.candidates` | 候选公司列表 | 🔸 |
| `module.started` | 模块开始执行 | ✅ |
| `module.completed` | 模块终态和耗时 | 🔸 |
| `answer.delta` | 文本增量 | ✅ |
| `artifact.upsert` | 结构化产物更新 (规则/图/时间线/证据) | ✅ |
| `warning.raised` | 数据不足/超时/降级 | 🔸 |
| `turn.completed` | 最终结果 + 追问建议 | ✅ |
| `turn.failed` | 本轮无法继续 | ✅ |
| `heartbeat` | 服务端心跳 | 🔸 |

---

## 完整时序

```text
Client → chat.query
Server → turn.accepted
Server → company.candidates                // 需要消歧时
Client → company.confirm
Server → module.started(finance)
Server → module.started(equity)
Server → module.started(events)
Server → answer.delta
Server → artifact.upsert(finance_rules)
Server → module.completed(finance)
Server → artifact.upsert(equity_graph)
Server → module.completed(equity)
Server → warning.raised(events_partial)     // 可选
Server → artifact.upsert(event_timeline)
Server → answer.delta
Server → turn.completed
```

---

## artifact.upsert

```json
{
  "event_type": "artifact.upsert",
  "payload": {
    "artifact_type": "finance_rules",
    "artifact_id": "finance_600518_2026Q2",
    "revision": 2,
    "operation": "replace",
    "data": {}
  }
}
```

支持的 `artifact_type`: `finance_rules`, `equity_graph`, `event_timeline`, `risk_assessment`, `evidence_chain`, `industry_benchmark`, `follow_up_suggestions`

---

## 重连恢复

```json
{
  "event_type": "stream.resume",
  "payload": {
    "turn_id": "turn_01",
    "last_received_sequence": 17
  }
}
```

服务端可补发则从 18 开始；执行已完成则返回最终事件。

---

## 兼容策略

旧格式 `{type, data}` 保留兼容。新旧格式通过路由优先级区分。
