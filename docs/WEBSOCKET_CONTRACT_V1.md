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
| `turn.cancel` | turn_id, 可选 reason | 取消当前轮次（Phase D #5 协作式） |
| `stream.resume` | session_id, last_sequence, 可选 turn_id | 断线重连（Phase D #6） |
| `ping` | client_time | 心跳 |

## Server → Client 事件

| `event_type` | 说明 | 状态 |
|------|------|:---:|
| `turn.accepted` | 请求已接收，分配 turn_id | ✅ |
| `company.candidates` | 候选公司列表 | 🔸 |
| `module.started` | 模块开始执行（真流式：节点实际执行前发送） | ✅ |
| `module.completed` | 模块终态和耗时 | ✅ |
| `answer.delta` | 文本增量（真流式：generate_answer 实时分段） | ✅ |
| `artifact.upsert` | 结构化产物更新 (规则/图/时间线/证据/股权链路) | ✅ |
| `warning.raised` | 数据不足/超时/降级 | 🔸 |
| `turn.completed` | 最终结果 + 追问建议 + pattern_matches + equity_chains | ✅ |
| `turn.failed` | 本轮无法继续 | ✅ |
| `turn.cancelled` | `turn.cancel` 确认（≤2s，幂等，单终态） | ✅ |
| `stream.resume_ack` | 断线补发结果（replay_count/gap） | ✅ |
| `heartbeat` | 服务端心跳 | 🔸 |

## Phase D #5 协作式取消

```json
{"event_type": "turn.cancel", "payload": {"turn_id": "turn_01"}}
```

服务端：
1. 2 秒内确认 `turn.cancelled`；
2. 立即置位 cancellation token；
3. 当前不可中断节点可结束，结束后不启动下一个节点；
4. `turn.cancelled` 恰好一次；不再发送 `turn.completed`；
5. 重复取消幂等；已完成 turn 的取消返回明确终态，不改变历史。

## Phase D #6 断线补发

```json
{
  "event_type": "stream.resume",
  "payload": {"session_id": "ses_xxx", "last_sequence": 27}
}
```

服务端：
- 补发所有 `sequence > last_sequence` 的缓存事件（原 event_id/sequence/turn_id）；
- 顺序严格递增、不重复；跨新 socket 保持 session sequence；
- 无事件时返回 `stream.resume_ack`（replay_count=0）；
- 请求序号早于缓存起点 → `STREAM_GAP` 可恢复错误；
- session 不存在 → `SESSION_NOT_FOUND`；
- 事件缓冲上限/TTL 来自配置（WS_EVENT_BUFFER_MAX_EVENTS / TTL_SECONDS）。

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
