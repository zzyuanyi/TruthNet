# API 接口契约 V1 — V12 Baseline

> **版本**: 1.0
> **基线**: V12 (2026-07-17)
> **状态**: 🔶 MVP — 字段可能追加，不删除不重命名
> **旧文档**: `docs/API_CONTRACT.md` 保留作为历史参考（deprecated）

---

## 基础信息

- 基础 URL：`http://localhost:8000`
- API 前缀：`/api/v1/`
- Content-Type：`application/json`

## 响应格式

### V12 统一响应 Envelope（新接口）

```json
{
  "data": {},
  "meta": {
    "request_id": "req_01",
    "trace_id": "trace_01",
    "schema_version": "1.0",
    "generated_at": "2026-07-15T10:00:00+08:00",
    "data_as_of": "2026-06-30",
    "dataset_version": "mock-v12",
    "rule_set_version": "finance-rules-1.0.0",
    "graph_version": "equity-mock-v12"
  },
  "warnings": []
}
```

### 旧格式兼容（deprecated）

```json
{
  "code": 0,
  "data": {},
  "message": "ok",
  "trace_id": "uuid"
}
```

> 旧格式保留兼容。新开发请使用 V12 envelope。

### 错误格式（RFC 9457 Problem Details）

```json
{
  "type": "https://truthnet/errors/module-timeout",
  "title": "Module execution timed out",
  "status": 503,
  "detail": "Equity analysis exceeded its deadline.",
  "instance": "/api/v1/companies/600518.SH/risk",
  "error_code": "EQUITY_TIMEOUT",
  "trace_id": "trace_01",
  "recoverable": true
}
```

---

## 端点列表

### 1. 健康检查

**`GET /api/v1/healthz`**

状态：✅ V12 稳定

返回进程存活状态。lite profile 下不检查外部服务。

**`GET /api/v1/readyz`**

状态：✅ V12 稳定

返回就绪状态。lite profile 下始终 ready。full profile 下检查 MySQL/Neo4j 等。

### 2. 公司搜索

**`GET /api/v1/companies?query={keyword}&limit={n}`**

状态：🔶 V12 MVP

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | 否 | 公司名称或代码搜索关键词 |
| `limit` | int | 否 | 最大返回数（默认 10，最大 50） |

### 3. 对话接口

**`POST /api/v1/chat`**

状态：🔶 V12 MVP

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `question` | string | ✅ | 用户问题 |
| `session_id` | string | 否 | 会话 ID |
| `context` | object | 否 | `{company_code, fiscal_year, report_type}` |

### 4. WebSocket 对话

**`WS /api/v1/chat/ws`**

状态：🔶 V12 MVP

使用 V12 event envelope 格式。

---

## 兼容策略

| 端点 | 旧路径 | V12 路径 | 兼容 |
|------|--------|---------|------|
| 健康检查 | `GET /health` | `GET /api/v1/healthz` | 旧路径保留，标记 deprecated |
| 对话 | `POST /api/v1/chat` (旧格式) | `POST /api/v1/chat` (V12 envelope) | 旧格式保留 |
| WebSocket | `WS /api/v1/chat/ws` (旧格式) | `WS /api/v1/chat/ws` (V12 envelope) | 旧格式保留 |
