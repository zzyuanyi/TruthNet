# API 接口契约 V1

> **更新**: 2026-08 | 本文描述当前服务接口；V12 与 `docs/API_CONTRACT.md` 均保留为设计/历史参考。

---

## 基础信息

- 本地演示基础 URL: `http://127.0.0.1:8001`（Docker 容器内部仍监听 `8000`）
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
| `statement_scope` | `parent_company`（固定母公司报表口径 408006000；`auto/consolidated` 已停用） |
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
| 公司搜索 | GET | `/api/v1/companies?query=康美&limit=10` | P0 | ✅ 已实现（真实数据，2026-08-06 对齐审计） |
| 企业画像摘要 | GET | `/api/v1/companies/{code}` | P0 | ✅ 已实现（真实数据） |
| 财务分析 | GET | `/api/v1/companies/{code}/finance` | P0 | ✅ 已实现（真实数据） |
| 股权穿透 | GET | `/api/v1/companies/{code}/equity` | P0 | ✅ 已实现（Neo4j/NetworkX） |
| 舆情事件 | GET | `/api/v1/companies/{code}/events` | P0 | ✅ 已实现（真实数据） |
| 综合风险 | GET | `/api/v1/companies/{code}/risk` | P0 | ✅ 已实现（真实数据） |
| 行业对标 | GET | `/api/v1/companies/{code}/benchmarks` | P0 | ✅ 已实现（⚠️ 前端独立入口未接，经 /finance 内嵌指标间接展示） |
| 会话列表 | GET | `/api/v1/sessions` | P0 | ✅ 已实现 |
| 创建会话 | POST | `/api/v1/sessions` | P0 | ✅ 已实现 |
| 非流式问答 | POST | `/api/v1/chat` | P0 | ✅ 已实现（⚠️ 当前页面主链路走 WS） |
| 流式问答 | WS | `/api/v1/chat/ws` | P0 | ✅ 已实现（⚠️ answer.delta 为伪流式，真流式 Phase D #1） |
| 创建比较 | POST | `/api/v1/comparisons` | P1 | ✅ 已实现（⚠️ 需 /compare?codes= 或选股器入口） |
| 创建报告 | POST | `/api/v1/reports` | P1 | ✅ 已实现（Phase D #8：202 + 幂等键 + report_jobs） |
| 报告状态 | GET | `/api/v1/reports/{report_id}` | P1 | ✅ 已实现（Phase D #8：状态/进度/错误/可下载标志） |
| 报告下载 | GET | `/api/v1/reports/{report_id}/file` | P1 | ✅ 已实现（Phase D #8：仅 succeeded，PDF） |

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

响应（V12 envelope `data` 字段）:
- `answer`: string — Markdown 主回答
- `evidence`: list — 证据项（ChatEvidenceV1：source/field/value + canonical 字段）
- `claims`: list — 结论声明（ClaimV1：claim_id/text/claim_type/severity/confidence/rule_id/rule_version/evidence_ids/verification_status/limitations）※ 2026-08-04 追加
- `module_status`: dict[string, ModuleStatusV1] — 各模块状态 typed 对象 `{state, error_code, recoverable, duration_ms}`（state ∈ pending/running/success/partial/failed/skipped/cancelled）※ 2026-08-04 追加，8/4 类型化
- `risk_level`: string — 风险等级 red/orange/yellow/green/unknown（优先 final_response，不从 risk_score 换算）※ 2026-08-04 追加
- `graph` / `timeline` / `risk_score` / `warnings` / `missing_modules` / `trace_id` / `follow_ups`

### WS /api/v1/chat/ws — 流式问答 ✅

V12 event envelope 格式，支持 turn.accepted / module.started / answer.delta / artifact.upsert / turn.completed / turn.failed / turn.cancelled / stream.resume_ack / heartbeat。

Phase D 增强（#5/#6/#10）：
- `turn.cancel` → `turn.cancelled`（协作式取消：当前节点结束、下一节点不启动、≤2s 确认、幂等）
- `stream.resume` → `stream.resume_ack`（断线补发：原 event_id/sequence/turn_id 原样回放；gap → STREAM_GAP）
- `answer.delta` 为真流式（generate_answer 实时分段，拼接 == 最终答案）
- `turn.completed` 增补 `pattern_matches`（模式三要素）与 `equity_chains`（股权链路）

### GET /api/v1/reports — 创建报告 ✅ (Phase D #8)

```http
POST /api/v1/reports
{
  "company_code": "600518.SH",
  "session_id": "ses_xxx",           // 可选
  "idempotency_key": "report-001",   // 可选：同一键重试不重复建任务
  "as_of": "2026-03-31"              // 可选
}
```

响应 202：`{data: {report_id, status:"queued", progress:0, ...}, meta, warnings}`。

### GET /api/v1/reports/{report_id} — 报告状态 ✅

返回 `{report_id, status, progress, created_at, started_at, completed_at, error_code, error_message, download_available, file_sha256, company_code, session_id}`。

### GET /api/v1/reports/{report_id}/file — 报告下载 ✅

仅 `succeeded` 可下载；返回 `application/pdf`；路径穿越防护；文件不存在返回明确错误。

### 股权链路载荷（Phase D #12）

`GET /api/v1/companies/{code}/equity` 与 `POST /api/v1/chat` 的 `equity_chains` 字段：
每条链含 `chain_id/path_names/depth/final_control_pct/evidence_ids/risk_label/risk_level/risk_reasons/merge_explanation/source_system/as_of`。

### 股权穿透多跳口径（8.09 审查）

`GET /api/v1/companies/{code}/equity`（Phase C 真实图谱契约）：

- **深度定义**：`hop_count = len(edge_ids) = len(node_ids) - 1`；`depth` 字段一律为 hop_count（边数），不混用实体数量。严格 >3 层 = hop_count ≥ 4（3 跳链 = 4 个实体，4 跳链 = 5 个实体）。
- **as_of 参数**：支持 `YYYYMMDD` / `YYYY-MM-DD` / `YYYYQn`（如 2026Q2 → 20260630），适配器边界统一规范化为八位期次；无法解析返回 **422**（不静默返回空图）。
- **时点快照语义**：与导入侧 `is_latest` 快照级标记一致——按目标公司（endNode）取 `report_period <= as_of` 的最新报告期**整体快照**（同一目标公司的全部股东边一起切换，已退出前十大的旧股东被排除）；`as_of` 晚于全图最新快照期时结果与不传 `as_of` 完全一致。
- **响应新增字段**：
  | 字段 | 类型 | 说明 |
  |------|------|------|
  | `requested_depth` | int | 请求穿透深度（hop_count 口径） |
  | `max_observed_hops` | int | 实际观测最大跳数（len(edge_ids) 口径） |
  | `truncated` | bool | 路径超过 200 条被截断（深链优先取前 200；截断时 `partial=true` + `PATH_LIMIT_REACHED` warning） |
  | `coverage_note` | str | 诚实覆盖说明（按公司维度）：**该公司**未发现 4 跳及以上持股链路时输出"在当前图版本及已覆盖的十大股东数据中，未发现可验证的4跳及以上股权链路…"，不推断现实中不存在更深关系。注意：全局统计存在 10 条四跳持股路径（如中央汇金→南京高科→南京银行→江苏国信→江苏新能），与单公司查询为 0 不矛盾 |
- **路径排序**：`ORDER BY length(path) DESC` 深链优先，查询 201 条取前 200 条。
- **链路类型**：`equity_chains[*].path_type` 为 `ownership`（默认，持股关系）或 `control`（存在明确控制证据）。回答/Claim/PDF 按此措辞——ownership 链路称"股权链穿透/最终持股/持股比例集中"，不得一律称"控制链/最终控制"。
- **快照缓存运维约束**：历史时点快照聚合结果在进程内缓存 300 秒（TTL）。同一 `graph_version` 下重建图后，最多返回 300 秒旧快照。运维要求三选一：① 图导入期间不对外提供股权查询；② 导入完成后重启后端；③ 接受最多 300 秒最终一致性。不建议增加更复杂缓存机制。

### 模式三要素（Phase D #16）

`/risk` 的 `pattern_matches`、`/chat` 的 `pattern_matches`、WS `turn.completed`：
每条含 `phase / alternative_explanation / regulatory_hint`（监管提示固定存在）。

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
