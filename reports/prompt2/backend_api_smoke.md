# 后端 API 契约 Smoke 验证

**验证日期**：2026-07-02

---

## 已验证端点

### 1. GET /health

**状态**：✅ passed

**请求**：`GET /health`

**响应**：
```json
{
  "code": 0,
  "data": {
    "status": "healthy",
    "version": "0.1.0"
  },
  "message": "ok",
  "trace_id": "uuid"
}
```

**验证项**：
- [x] HTTP 200
- [x] code = 0
- [x] data.status = "healthy"
- [x] data.version = "0.1.0"
- [x] message = "ok"
- [x] trace_id 存在且为字符串

---

### 2. POST /api/v1/chat

**状态**：✅ passed (mock 占位)

**请求**：`POST /api/v1/chat` (任意 body)

**响应**：
```json
{
  "code": 0,
  "data": {
    "answer": "Mock 回答：该功能正在开发中。",
    "evidence": [],
    "graph": {},
    "timeline": [],
    "risk_score": 0.0,
    "warnings": [],
    "missing_modules": ["编排Agent", "财务勾稽Agent", "股权穿透Skill", "舆情事件Skill"],
    "trace_id": "uuid"
  },
  "message": "ok",
  "trace_id": "uuid"
}
```

**验证项**：
- [x] HTTP 200
- [x] code = 0
- [x] data.answer 为字符串
- [x] data.evidence 为列表
- [x] data.graph 为字典
- [x] data.timeline 为列表
- [x] data.risk_score 在 0-1 范围
- [x] data.warnings 为列表
- [x] data.missing_modules 为列表（包含 4 个暂缺模块）
- [x] data.trace_id 存在

**与 API_CONTRACT.md 一致性**：
- [x] 所有必填字段存在
- [x] 字段类型正确
- [x] 统一响应格式正确

---

### 3. WebSocket /api/v1/chat/ws

**状态**：🔶 not_implemented

- `docs/API_CONTRACT.md` 中定义了 WebSocket 契约
- `websockets` 包已安装（12.0）
- `backend/app/schemas/chat.py` 中有 WSMessage/WSStatusData/WSPartialAnswerData schema
- 但 `backend/app/main.py` 中无 WebSocket 端点实现

**建议**：Prompt3 实现 minimal WebSocket 端点，支持：
- 客户端发送 `{"type": "question", ...}`
- 服务端返回 `{"type": "status", ...}` + `{"type": "final_answer", ...}`

---

## Pydantic Schema 与文档一致性

| Schema 文件 | API_CONTRACT 对应 | 一致性 |
|-------------|-------------------|--------|
| `backend/app/schemas/common.py::UnifiedResponse` | 统一响应格式 | ✅ 一致 |
| `backend/app/schemas/common.py::HealthResponse` | GET /health | ✅ 一致 |
| `backend/app/schemas/chat.py::ChatRequest` | POST /api/v1/chat request | ✅ 一致 |
| `backend/app/schemas/chat.py::ChatData` | POST /api/v1/chat response | ✅ 一致 |
| `backend/app/schemas/chat.py::Evidence` | response.evidence | ✅ 一致 |
| `backend/app/schemas/chat.py::GraphData` | response.graph | ✅ 一致 |
| `backend/app/schemas/chat.py::TimelineEvent` | response.timeline | ✅ 一致 |

---

## 接口稳定性状态

| 接口 | 状态 | 备注 |
|------|------|------|
| GET /health | ✅ 稳定 | 不变更 |
| POST /api/v1/chat | 🔶 MVP | 字段可追加，不删除/重命名 |
| WS /api/v1/chat/ws | 🔶 MVP | 合同已定，实现待完成 |
| POST /api/v1/files/upload | 🔸 草案 | 仅文档，未实现 |
| GET /api/v1/companies/{id}/risk | 🔸 草案 | 仅文档，未实现 |
| GET /api/v1/companies/{id}/ownership | 🔸 草案 | 仅文档，未实现 |
| GET /api/v1/companies/{id}/timeline | 🔸 草案 | 仅文档，未实现 |
