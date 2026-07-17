# WebSocket 契约 V1 — V12 Baseline

> **版本**: 1.0
> **基线**: V12 (2026-07-17)
> **端点**: `ws://localhost:8000/api/v1/chat/ws`

---

## V12 Event Envelope

所有 WebSocket 消息使用统一 envelope：

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
| `event_id` | string | 事件唯一 ID（`evt_` 前缀 + 8 位 hex） |
| `event_type` | string | 事件类型（见下表） |
| `session_id` | string | 会话 ID（`ses_` 前缀 + UUID4） |
| `turn_id` | string | 轮次 ID（`turn_` 前缀 + UUID4） |
| `sequence` | int | 单调递增序号 |
| `timestamp` | string | ISO 8601 时间戳 |
| `trace_id` | string | 追踪 ID（UUID4） |
| `payload` | object | 事件数据 |

---

## 事件类型

### `turn.accepted`
用户问题已接收。

```json
{
  "event_type": "turn.accepted",
  "payload": {
    "message": "已收到问题: ..."
  }
}
```

### `module.started`
模块开始执行。

```json
{
  "event_type": "module.started",
  "payload": {
    "module": "orchestrator",
    "status": "running"
  }
}
```

### `answer.delta`
流式回答片段。

```json
{
  "event_type": "answer.delta",
  "payload": {
    "text": "部分回答文本...",
    "index": 0
  }
}
```

### `artifact.upsert`
结构化产物更新。

```json
{
  "event_type": "artifact.upsert",
  "payload": {
    "artifact_type": "risk_score",
    "data": {"overall": 0.15}
  }
}
```

### `turn.completed`
轮次成功完成。

```json
{
  "event_type": "turn.completed",
  "payload": {
    "answer": "完整回答...",
    "evidence": [],
    "graph": {},
    "timeline": [],
    "risk_score": {},
    "warnings": [],
    "missing_modules": []
  }
}
```

### `turn.failed`
轮次执行失败。

```json
{
  "event_type": "turn.failed",
  "payload": {
    "error_code": "INVALID_JSON",
    "message": "无效的 JSON 格式"
  }
}
```

### `heartbeat`
心跳（可选，用于 keepalive）。

```json
{
  "event_type": "heartbeat",
  "payload": {}
}
```

---

## 客户端发送

客户端发送简化的请求格式（不需要 envelope）：

```json
{
  "question": "请分析贵州茅台2023年营收",
  "context": {"company_code": "600519"}
}
```

服务端负责包装为 V12 event envelope。

---

## 兼容策略

旧格式 `{type, data}` 保留兼容。新旧格式通过路由优先级区分。
