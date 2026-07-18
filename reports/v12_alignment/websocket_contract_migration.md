# WebSocket 契约迁移记录 — V12 Alignment

> 生成时间：2026-07-17

## 迁移摘要

| 维度 | 旧（Prompt3/4） | 新（V12） | 策略 |
|------|---------------|----------|------|
| 文档 | `docs/API_CONTRACT.md` (WS 章节) | `docs/WEBSOCKET_CONTRACT_V1.md` | 独立文档 |
| 消息格式 | `{type, data}` | V12 event envelope | 共存，旧格式优先匹配 |
| 消息类型 | status/partial_answer/final_answer/error | turn.accepted/module.started/answer.delta/artifact.upsert/turn.completed/turn.failed/heartbeat | 旧类型保留 |

## V12 Event Envelope

```json
{
  "schema_version": "1.0",
  "event_id": "evt_01",
  "event_type": "turn.accepted",
  "session_id": "ses_01",
  "turn_id": "turn_01",
  "sequence": 1,
  "timestamp": "2026-07-17T10:00:00+08:00",
  "trace_id": "trace_01",
  "payload": {}
}
```

## 兼容策略

- Legacy WS 端点在 main.py 中先注册，优先匹配
- V12 WS 端点在 router 中注册，同路径
- 旧客户端收到 `{type, data}` 格式
- V12 客户端可通过请求头或其他方式切换到新格式（后续实现）
