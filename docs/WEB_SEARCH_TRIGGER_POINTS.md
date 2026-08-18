# Web Search 触发点清单 — Phase E 会5 B1

> 会5「联网搜索贯穿各环节」的触发点登记表。本文档是「Provider 接入 + 触发点清单」交付物。

## Provider 接入（抽象层）

| 项 | 值 | 说明 |
|---|---|---|
| 配置开关 | `WEB_SEARCH_BACKEND` | `off`（默认）/ `mock` / `bocha` |
| 具体 Provider | **Bocha 博查**（国产、免费额度、中文友好、国内直连） | 数据源由开发组选定；可换（工厂注册表 + `.env` 改后端名） |
| 守卫服务 | `app.application.services.web_search_service.web_search()` | 同步入口：off 门 → 缓存 → 限流 → 超时 → 失败空列表 |
| 默认状态 | **off**（行为与现状完全一致） | 数据源拍板后再启用；`.env` 置 `WEB_SEARCH_BACKEND=bocha` + `WEB_SEARCH_API_KEY` |

关键文件：
- 端口：`backend/app/application/ports/web_search_provider.py`
- 实现：`backend/app/infrastructure/web_search/{mock,bocha}/provider.py`
- 工厂：`backend/app/infrastructure/web_search/factory.py`
- 守卫：`backend/app/application/services/web_search_service.py`
- 配置：`backend/app/core/config.py`（`WEB_SEARCH_*`）

## 触发点

所有触发点共同铁律：**库内有数据不搜；无数据才搜；搜不到/开关关闭 → 走原降级分支（行为与现状逐字节一致）；来源一律标注。**

| # | 环节 | 文件 | 「无数据」判据 | 触发查询 | 来源标注 |
|---|---|---|---|---|---|
| 1 | **问答 · 公司事实**（首个示范触发点） | `app/agents/nodes/generate_answer.py` `_answer_company_fact` | 公司事实库内无值（如 `listing_date` 为空） | `"{sec_name} 上市日期"` | `EvidenceRef`：`source_type="web_search"`、`source_uri`=命中 URL、`source_excerpt`=摘要、`retrieved_at`；Claim `limitations` 追加「联网检索来源，建议以官方披露为准核验」 |
| 2 | **画像 · 企业画像** | `app/api/v1/routers/companies.py` `company_profile` | 画像 `listing_date` 库内为空 | `"{sec_name} 上市日期"` | `profile.listing_date` 回填 + `WarningItem(code="WEB_SEARCH_SOURCE")` 附来源 URL |
| 3 | **舆情 · 公告无数据** | `app/agents/nodes/events.py` `events_node` | 库内无公告记录（`no_announcement`）且非查询异常 | `"{sec_name} 公告 舆情 最新"` | 命中（前 3 条）作为 `source_type="web_search"` 的 `EvidenceRef` 附到 `EventsResult.evidence`；模块状态仍诚实保持 `NO_ANNOUNCEMENT_DATA` |

## 诚实边界（防幻觉）

- 上市日期等值解析使用纯函数 `extract_listing_date_from_hits`（`app/application/services/web_search_fact_fill.py`），只读 `SearchResult.snippet/title/published_at`，解析不出 → 不填充、不编造。
- `verification_status` 维持既有枚举（`unsupported/partial/verified`），联网来源通过 `source_type` + `limitations` 表达，不发明新状态值。
- 舆情环节：联网结果只作补充证据，**不改变** `NO_ANNOUNCEMENT_DATA` 模块状态与降级语义。

## 测试

- `backend/tests/unit/test_web_search_service.py` — 守卫服务（off/mock/缓存/限流/超时）
- `backend/tests/unit/test_web_search_provider.py` — Bocha 解析 + 工厂
- `backend/tests/unit/test_web_search_fact_fill.py` — 日期解析纯函数 + 问答触发点
- `backend/tests/unit/test_web_search_companies.py` — 画像触发点
- `backend/tests/unit/test_web_search_events.py` — 舆情触发点

## 启用步骤（拍板后）

1. `.env`：`WEB_SEARCH_BACKEND=bocha`、`WEB_SEARCH_API_KEY=<博查key>`
2. 按需调 `WEB_SEARCH_TIMEOUT_SECONDS` / `WEB_SEARCH_RATE_LIMIT_RPM` / `WEB_SEARCH_MAX_RESULTS`
3. 拿真实响应校准 `bocha/provider.py` 解析（当前按文档契约防御式实现，未真机验证）
