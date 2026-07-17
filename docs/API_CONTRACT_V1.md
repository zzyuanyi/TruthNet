# API 接口契约 V1 — V12 Baseline

> **版本**: 1.0 | **基线**: V12 (2026-07-15) | **状态**: 🔶 MVP
> 设计依据: `TruthNet_综合设计方案_V12(2).md` §11 REST API 契约
> 旧文档: `docs/API_CONTRACT.md` 保留作为历史参考（deprecated）

---

## 基础信息

- 基础 URL: `http://localhost:8000`
- API 前缀: `/api/v1/`
- Content-Type: `application/json`

## 响应格式

### V12 统一响应 Envelope

```json
{
  "data": {},
  "meta": {
    "request_id": "req_01",
    "trace_id": "trace_01",
    "schema_version": "1.0",
    "generated_at": "2026-07-15T10:00:00+08:00",
    "data_as_of": "2026-06-30",
    "dataset_version": "official-2026-07-12",
    "rule_set_version": "finance-rules-1.0.0",
    "graph_version": "equity-2026Q2"
  },
  "warnings": []
}
```

### 部分成功 (Partial Success)

```json
{
  "data": {
    "status": "partial",
    "finance": {},
    "equity": null,
    "events": {}
  },
  "meta": {},
  "warnings": [
    {
      "code": "EQUITY_TIMEOUT",
      "module": "equity",
      "message": "股权模块超过本轮时限，已返回其余结果。",
      "recoverable": true
    }
  ]
}
```

### 错误格式 (RFC 9457 Problem Details)

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

---

## 公共查询参数

| 参数 | 用途 |
|------|------|
| `as_of` | 指定数据快照日期 |
| `statement_scope` | `parent_company / consolidated / auto` |
| `include` | 指定摘要接口包含的可选区域 |
| `periods` | 财务历史期数 |
| `months` | 事件回溯月数 |
| `depth` | 股权穿透深度，1–10 |
| `include_related` | 是否包含关联方 |

---

## 端点总览

| 能力 | 方法 | 端点 | 优先级 | 状态 |
|------|:---:|------|:---:|:---:|
| 存活检查 | GET | `/healthz` | P0 | ✅ 已实现 |
| 就绪检查 | GET | `/readyz` | P0 | ✅ 已实现 |
| 公司搜索 | GET | `/api/v1/companies?query=康美&limit=10` | P0 | ✅ 已实现 (mock) |
| 企业画像摘要 | GET | `/api/v1/companies/{code}` | P0 | 🔸 待实现 |
| 财务分析 | GET | `/api/v1/companies/{code}/finance` | P0 | 🔸 待实现 |
| 股权穿透 | GET | `/api/v1/companies/{code}/equity` | P0 | 🔸 待实现 |
| 舆情事件 | GET | `/api/v1/companies/{code}/events` | P0 | 🔸 待实现 |
| 综合风险 | GET | `/api/v1/companies/{code}/risk` | P0 | 🔸 待实现 |
| 行业对标 | GET | `/api/v1/companies/{code}/benchmarks` | P0 | 🔸 待实现 |
| 会话列表 | GET | `/api/v1/sessions` | P0 | 🔸 待实现 |
| 创建会话 | POST | `/api/v1/sessions` | P0 | 🔸 待实现 |
| 非流式问答 | POST | `/api/v1/chat` | P0 | ✅ 已实现 (mock) |
| 流式问答 | WS | `/api/v1/chat/ws` | P0 | ✅ 已实现 (mock) |
| 创建比较 | POST | `/api/v1/comparisons` | P1 | 🔸 待实现 |
| 创建报告 | POST | `/api/v1/reports` | P1 | 🔸 待实现 |
| 报告状态 | GET | `/api/v1/reports/{report_id}` | P1 | 🔸 待实现 |
| 报告下载 | GET | `/api/v1/reports/{report_id}/file` | P1 | 🔸 待实现 |

---

## 已实现端点详情

### GET /healthz — 存活检查 ✅

进程存活探针，不依赖外部服务。

### GET /readyz — 就绪检查 ✅

lite profile: 始终 ready。full profile: 检查 MySQL/Neo4j/ChromaDB/LLM 状态。

### GET /api/v1/companies — 公司搜索 ✅

```http
GET /api/v1/companies?query=康美&limit=10
```

当前为 mock 实现（5 家公司硬编码数据）。

### POST /api/v1/chat — 非流式问答 ✅

请求: `{ "question": "...", "session_id": "...", "context": {...} }`

### WS /api/v1/chat/ws — 流式问答 ✅

V12 event envelope 格式，支持 turn.accepted / module.started / answer.delta / artifact.upsert / turn.completed / turn.failed / heartbeat。

---

## 兼容策略

| 旧路径 | V12 路径 | 状态 |
|--------|---------|------|
| `GET /health` | `GET /healthz` | deprecated, 保留兼容 |
| `POST /api/v1/chat` (旧格式) | `POST /api/v1/chat` (V12 envelope) | 旧格式保留兼容 |
| `WS /api/v1/chat/ws` (旧格式) | `WS /api/v1/chat/ws` (V12 envelope) | 旧格式保留兼容 |

---

## 接口稳定性约定

- **✅ 稳定**: 不计划修改
- **🔶 MVP**: 核心字段稳定，可能追加新字段
- **🔸 草案**: 仍在设计中

### 变更规则

1. 新字段只能追加，不删除已有字段
2. 破坏性修改必须在 `docs/INTERFACE_CHANGELOG.md` 中记录
3. 破坏性修改需要项目负责人审阅
4. 只有前端、评测脚本和测试都无旧路径依赖后，才删除兼容路由
