# Interface Changelog

> 记录所有接口、Schema、数据库结构的变更历史。
> 破坏性修改必须在此记录并请求项目负责人审阅。

---

## 模板

```markdown
## YYYY-MM-DD

### Changed
- 修改了什么字段 / 接口 / 表
- 原因
- 影响范围

### Added
- 新增了什么

### Deprecated
- 废弃了什么，预计何时删除

### Breaking Changes
- 是否有破坏性修改：
- 影响前端：
- 影响后端：
- 迁移方式：
- 是否已由项目负责人审阅：
```

---

## 2026-07-02 — Prompt4：前端初始化 + 接口冻结 + GitHub 协作简化

### Changed
- `POST /api/v1/chat` 响应：`risk_score` 字段从 `float` 升级为 `RiskScore` 对象
  - 新结构：`{"overall": 0.15, "financial": 0.10, "ownership": 0.20, "sentiment": 0.05}`
  - **破坏性变更**：类型从 float 变为 object
  - 已同步更新：backend schema, frontend types, 后端测试, API 文档
- `WS /api/v1/chat/ws` final_answer.data 结构同步 HTTP ChatData（含新 risk_score）
- GitHub 协作模型从 `main→dev→feature` 简化为 `main←PR←feature`

### Added
- 前端 React + Vite + TypeScript 项目初始化（22 个文件）
- 前端类型 `frontend/src/types/api.ts` 与 backend schema 完全对齐
- 前端组件：ChatPanel, RiskPanel, EvidenceList, TimelinePanel, GraphPanel
- HTTP 客户端 + WebSocket 客户端代码
- CI frontend job（typecheck + build）
- `reports/prompt4/` 全部报告

### Breaking Changes
- `risk_score` 从 float 变为 RiskScore 对象 — **破坏性变更**
- 影响前端：需更新 RiskPanel 组件（已完成）
- 影响后端：所有引用 risk_score 的代码（已更新）
- 迁移方式：前端使用 `risk_score.overall` 替代 `risk_score`
- 是否已由项目负责人审阅：✅ Prompt4 冻结评审

### Deprecated
- dev 分支不再强制要求（保留为历史参考）

---

## 2026-07-02 — Prompt3：WebSocket 最小 mock 实现

### Changed
- `WS /api/v1/chat/ws` 从「合同占位」升级为「最小 mock 实现」
  - 接收 `{"type": "question", "data": {"question": "..."}}` 格式
  - 返回 status → partial_answer → final_answer 三类消息
  - 错误时返回 error 消息
  - 所有消息包含 trace_id
  - 不调用真实 LLM，不访问真实数据
- `docs/API_CONTRACT.md` 更新 WebSocket 章节：
  - 补充客户端发送消息格式表
  - 补充每条消息的详细字段说明
  - 状态从 🔶 MVP 更新为 🔶 MVP（已实现最小 mock 端点，Prompt3）

### Added
- 新增 `backend/tests/test_websocket_smoke.py` WebSocket smoke 测试
- 新增 `backend/app/schemas/chat.py` 中的 WSMessage/WSStatusData/WSPartialAnswerData schema（Prompt1 已创建）
- WebSocket 端点错误处理：无效 JSON、缺少 question 字段

### Breaking Changes
- 无破坏性修改
- 是否已由项目负责人审阅：✅ Prompt3 基线

---

## 2024-07-02 — 初始工程基线

### Added
- 创建 `docs/API_CONTRACT.md` MVP 版接口草案
  - `POST /api/v1/chat` (REST)
  - `WS /api/v1/chat/ws` (WebSocket)
  - `POST /api/v1/files/upload`
  - `GET /api/v1/companies/{company_id}/risk`
  - `GET /api/v1/companies/{company_id}/ownership`
  - `GET /api/v1/companies/{company_id}/timeline`
  - `GET /health`
- 创建 `docs/DATA_CONTRACT.md` SQLite / NetworkX / ChromaDB 数据边界定
- 创建 `backend/app/schemas/common.py` 统一响应格式
- 创建 `backend/app/schemas/chat.py` 对话相关 schema

### Changed
- 无（初始版本）

### Deprecated
- 无

### Breaking Changes
- 无破坏性修改（初始版本）
- 是否已由项目负责人审阅：✅ 初始基线
