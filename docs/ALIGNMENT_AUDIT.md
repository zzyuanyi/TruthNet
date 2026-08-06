# TruthNet 前后端契约对齐审计

> 审计日期：2026-08-06
> 审计仓库：`feature/zhiyuhan0703-github-skill-test`
> 审计原则：只读核验，不修改业务代码、数据库、`DESIGN_V12.md` 或冻结契约，不执行 commit/push/merge。
> 伪流式 `answer.delta` 按项目约定排除，不作为本次缺陷；真流式仍属于 Phase D。

## 1. 结论摘要

> ⚠️ **本节为修复前摘要**（2026-08-06 首次审计时点）。全部 P0/P1/P2 已按第 10-12 章修复并复核，当前 OpenAPI 19/19、面板数据已持久化；数据库会话/轮次为易过期快照，以各章记录日期为准。

**修复前**：后端业务 GET 链路和企业画像页面的主要字段已经能够对上，但系统仍存在两处会直接影响核心体验的 P0 错位：

1. **WS 会话 ID 没有从前端真正传到后端**。前端把 ID 放在 URL query，后端只读取 `payload.session_id`；因此 WS 产生的 turn 可能写入后端随机会话，连续对话和历史回读存在错位风险。
2. **V12 结构化 WS 事件没有驱动 `AnalysisPanel`**。后端发送 `artifact.upsert` 和 `turn.completed` 中的风险/财务信息，前端只处理旧事件以及回答文本，`panelData` 没有正式 V12 生产者，分析面板会保持空态。

其他优先问题：报告端点与页面完全缺失；对比页默认入口没有 `codes` 参数；公司搜索返回结构与前端类型不一致且没有页面消费；风险证据 DTO 与画像页证据组件使用的 DTO 不一致；大多数 REST 路由没有 `response_model`，OpenAPI 无法作为前端类型来源。

### 实测基线

| 检查 | 命令/证据 | 结果 |
|---|---|---|
| 路由/OpenAPI | `app.openapi()` | `PATH_COUNT 17`；实际 HTTP 路径为 `/health` 加 16 个 `/api/v1` 路径；仅 `/health`、`/api/v1/chat`、`/api/v1/companies/{code}/equity` 声明了非空 200 response schema，其余业务路径的 schema 为 `{}`。 |
| REST 只读冒烟 | truthnet Python `TestClient` GET `/health`、`healthz`、`readyz`、companies、finance、equity、events、risk、benchmarks、sessions | 全部返回 200；实际 `data` 顶层键见第 3 节。未执行会话写入接口。 |
| 前端类型检查 | `D:/anaconda/envs/truthnet/node.exe node_modules/typescript/bin/tsc -p tsconfig.app.json --noEmit`（`frontend/`） | 退出码 0。该结果只证明手写类型内部可编译，不证明与后端 schema 一致。 |
| 后端测试收集 | `D:/anaconda/envs/truthnet/python.exe -m pytest backend/tests --collect-only -q` | `614 tests collected`。本次未运行全量测试，因为 WS/集成测试会向本地 MySQL 写入测试会话；“592 passed”是已有基线，不是本次重跑结果。 |

## 2. 契约来源和实际路由

`docs/API_CONTRACT.md:3-5` 明确声明它是旧 mock 文档并指向 `API_CONTRACT_V1.md`；但它仍保留旧端点和旧 WS 信封。本审计同时盘点两份文档：V1 作为当前设计基线，旧文档中的端点作为需要清理或明确归档的历史契约。

OpenAPI 实际登记的路径如下：

| 实际方法/路径 | 路由文件 | OpenAPI 200 schema |
|---|---|---|
| `GET /health` | `backend/app/main.py:76-90` | `UnifiedResponse[HealthResponse]` |
| `GET /api/v1/healthz` | `backend/app/api/v1/routers/health.py:19-35` | `{}` |
| `GET /api/v1/readyz` | `backend/app/api/v1/routers/health.py:138-201` | `{}` |
| `GET /api/v1/companies` | `backend/app/api/v1/routers/companies.py:83-105` | `{}` |
| `GET /api/v1/companies/{code}` | `backend/app/api/v1/routers/companies.py:108-158` | `{}` |
| `GET /api/v1/companies/{code}/finance` | `backend/app/api/v1/routers/finance.py:71-81` | `{}` |
| `GET /api/v1/companies/{code}/equity` | `backend/app/api/v1/routers/equity.py:80-89` | `V12Response[EquityResponseData]` |
| `GET /api/v1/companies/{code}/events` | `backend/app/api/v1/routers/events.py:203` | `{}` |
| `GET /api/v1/companies/{code}/risk` | `backend/app/api/v1/routers/risk.py:40-44` | `{}` |
| `GET /api/v1/companies/{code}/benchmarks` | `backend/app/api/v1/routers/benchmarks.py:39-43` | `{}` |
| `POST /api/v1/comparisons` | `backend/app/api/v1/routers/comparisons.py:70-72` | `{}` |
| `POST /api/v1/chat` | `backend/app/api/v1/routers/chat.py:153-154` | `V12Response[ChatDataV1]` |
| `GET /api/v1/sessions` | `backend/app/api/v1/routers/sessions.py:65-66` | `{}` |
| `POST /api/v1/sessions` | `backend/app/api/v1/routers/sessions.py:137-138` | `{}` |
| `GET /api/v1/sessions/{session_id}` | `backend/app/api/v1/routers/sessions.py:202-203` | `{}` |
| `DELETE /api/v1/sessions/{session_id}` | `backend/app/api/v1/routers/sessions.py:334-335` | `{}` |
| `GET /api/v1/evidence/{evidence_id}` | `backend/app/api/v1/routers/provenance.py:171-173` | `{}` |
| `GET /api/v1/claims/{claim_id}` | `backend/app/api/v1/routers/provenance.py:227-229` | `{}` |
| `GET /api/v1/traces/{trace_id}/provenance` | `backend/app/api/v1/routers/provenance.py:264-266` | `{}` |
| `WS /api/v1/chat/ws` | `backend/app/api/v1/routers/chat.py:219-220` | 不在 HTTP OpenAPI paths 中 |

注意：OpenAPI 输出的 `PATH_COUNT 17` 是去重后的 HTTP path 数量（`/health` 加 16 个 `/api/v1` path）；由于 `/sessions` 和 `/sessions/{session_id}` 各自同时有多个 HTTP method，上表展开为 19 个 HTTP 操作行，WS 另列一行。

## 3. REST 三列差异表

“契约”列以 `API_CONTRACT_V1.md` 为当前 V12 口径；涉及 `API_CONTRACT.md` 的旧端点在表中单列。后端“实际”同时依据路由源码、OpenAPI 和 GET 冒烟；前端“实际”依据 `api-client.ts` 和页面引用。

| 级别 | 契约端点/字段 | 后端实际实现 | 前端实际消费 | 差异与最小修复建议 |
|---|---|---|---|---|
| P2 | `GET /healthz` | 返回 V12 envelope，`data={status,version,profile}`；`health.py:19-35`。OpenAPI response `{}`。 | `api-client.ts:119` 请求的是不存在的 `/api/v1/health`；无页面调用。 | 路径错位。将 health client 改为 `/healthz`，并为 `healthz` 加 `response_model`；或删除未用方法。 |
| P2 | `GET /readyz` | 返回 `data={status,profile,checks}`；`health.py:138-201`。OpenAPI `{}`。 | 无 API 方法、无页面消费。 | 后端能力未被前端使用；若需要启动状态页，新增 client 方法并生成类型，否则在契约中标为后端/运维专用。 |
| P1 | `GET /companies?query&limit` | `data={query,total,candidates}`，候选字段含 `wind_code/sec_name/entity_id/...`；`companies.py:83-105`。实测 200，data keys=`candidates,query,total`。 | `api-client.ts:121-123` 声明 `V12Response<Company[]>`，但真实 data 不是数组；`rg` 显示没有页面调用 `searchCompanies`。 | 结构和类型均错位，搜索能力没有 UI 入口。最小修复：定义 `CompanySearchData`，让方法返回它；在搜索/候选组件接入，或明确本期不交付搜索 UI。 |
| P1 | `GET /companies/{code}` 企业画像 | 返回 `data` 含 `wind_code/sec_name/entity_id/aliases/exchange/industry*/listing_date/data_quality/risk_summary`；`companies.py:62-80,108-158`。实测 200。 | `CompanyProfilePage.tsx:119-132` 调用并消费 `sec_name/wind_code`；类型 `Company` 在 `truthnet.ts:61-70` 仅覆盖部分字段，且使用 `list_date` 而后端为 `listing_date`。 | 页面当前使用字段能渲染，但类型不完整且存在字段名漂移。补齐 generated DTO；不应把 `list_date` 当后端别名继续扩散。 |
| P1 | `GET /companies/{code}/finance` | `FinanceResponseData` 定义在 `finance.py:64-77`；路由 `finance.py:71-81` 未声明 response model。实测 data keys=`claim_ids,data_quality,evidence_ids,industry_benchmark,risk_level,rules,sec_name,warnings,wind_code`；规则 item 含 `industry_metrics`。 | `CompanyProfilePage.tsx:121,127` 使用 `rules`；`RuleCard.tsx:94-171` 使用 `current/history/industry_metrics`；接口类型基本对应。 | 运行时主字段已对齐；OpenAPI 无 schema 是 P1 类型治理缺口。给路由加 `V12Response[FinanceResponseData]`，前端从生成类型导入。 |
| P1 | `GET /companies/{code}/equity` | `V12Response[EquityResponseData]`，`equity.py:80-188`；实测 data keys=`target,nodes,edges,paths,as_of,graph_version,source_system,partial,warnings`。 | `CompanyProfilePage.tsx:122,128,286-295`、`EquityGraph`、`RelatedPartyTable` 消费 `source/target/relation_type/ownership_pct`；类型与后端 schema 对齐。 | 当前字段链基本对齐；仍需补 OpenAPI/前端生成校验。 |
| P1 | `GET /companies/{code}/events` | `EventsResponseData` 在 `events.py:88-101`；路由 `events.py:203` 未声明 response model。实测 data keys=`wind_code,sec_name,sentiment_summary,event_clusters,timeline,rating_changes,keyword_summary,evidence_ids,announcements_available,months_covered,warnings`。 | `CompanyProfilePage.tsx:123,129-130` 消费 `timeline/event_clusters`；`RiskTimeline.tsx` 使用 `date/title/category/sentiment/summary/evidence_ids`，字段匹配。 | 运行时主字段对齐；OpenAPI schema 缺失。给路由加 response model 并生成类型。 |
| P1 | `GET /companies/{code}/risk` | `RiskResponseData` 在 `risk.py:68-99`；路由 `risk.py:40-169` 未声明 response model。实测 data keys=`as_of,confidence,data_coverage,evidence,mitigating_factors,overall_score,pattern_matches,risk_level,risk_tags,rule_set_version,sec_name,strategy_version,sub_scores,warnings`。 | 页面调用 `CompanyProfilePage.tsx:124,131-132`；但前端把风险证据声明为 `ChatEvidenceV1[]`（`truthnet.ts:301`），组件按 `field/value/source_title/period/dataset_version` 渲染（`EvidenceChain.tsx:167-187`）。后端 `RiskEvidence` 只有 `evidence_id/source_type/claim_ids/summary`（`risk.py:59-65`）。 | **真实字段级错位**：风险证据区会出现空字段或无意义内容。最小修复二选一：前端为 `/risk` 使用 `RiskEvidence` 专用组件/DTO；或后端扩充 RiskEvidence 为可展示的 canonical evidence。不要把两种证据 DTO 继续混用。 |
| P1 | `GET /companies/{code}/benchmarks` | `BenchmarksResponseData` 在 `benchmarks.py:28-44`；路由 `benchmarks.py:39-162` 未声明 response model。实测 data keys=`wind_code,sec_name,industry_l1,period,percentiles,peer_count,is_sample_sufficient,generic_thresholds_only,dataset_version,statement_scope,warnings`。 | 有 `api-client.ts:147-149` 方法，但 `rg` 显示没有页面调用；画像页通过 `/finance` 的 `industry_metrics` 间接展示，不消费独立 benchmarks 端点。 | 端点存在但前端未消费，行业对比独立入口不完整。为页面增加调用/入口，或明确 finance 内嵌指标是唯一前端能力并在契约说明。 |
| P1 | `POST /comparisons` | 请求 `company_codes[2..5],period,indicators,statement_scope`；`comparisons.py:6-18`。响应 `ComparisonsResponseData`；路由 `comparisons.py:70-285`，OpenAPI `{}`。 | `ComparePage.tsx:51-84` 只在 query `codes` 非空时调用；`api-client.ts:151-159` 发送 `company_codes/period/indicators`，不发送 `statement_scope`（后端固定母公司口径，当前结果仍可用）。 | `/compare` 默认入口没有 codes：`SessionSidebar.tsx:53-59`、`app-header.tsx:9-10` 都导航 `/compare`；页面必然显示“请选择要对比的公司”。最小修复是入口携带 codes 或页面提供选股流程。另给路由加 response model。 |
| P1 | `POST /chat` | 请求 `ChatRequestV1`：`question/session_id/context`，`chat.py:8-13`。响应 `ChatDataV1`：`answer/evidence/claims/module_status/risk_level/graph/timeline/risk_score/warnings/missing_modules/trace_id/follow_ups`，`chat.py:142-164`、`chat.py:153-183`。 | client 方法存在于 `api-client.ts:181-189`，但 ChatPage 实际只使用 WS（`ChatPage.tsx:285-309`）；前端 `ChatDataV1`（`truthnet.ts:464-474`）缺 `claims/module_status/risk_level`，所以无法消费这些已公开字段。 | 端点存在但不是当前页面主链路；前端类型落后于后端。补齐生成类型并决定 REST 是否作为评测/降级主路径。 |
| P2 | `GET /sessions` | `data={sessions,total}`；`sessions.py:65-134`，实测 data keys=`sessions,total`。 | `api-client.ts:161-162` 类型正确；`ChatPage.tsx:34-49` 兼容对象/数组并消费。 | 当前对齐。 |
| P2 | `POST /sessions` | `data={session_id,title,status,created_at,updated_at}`，不返回 `turn_count`；`sessions.py:137-199`。 | `api-client.ts:168-171` 用 `Omit<Session,'turn_count'>`，`ChatPage.tsx:96-106` 本地补 0。 | 当前对齐；应把响应 DTO 纳入生成类型，避免依赖注释约定。 |
| P1 | `GET /sessions/{id}` | `data={session,turns}`；turn 含 `turn_id/turn_index/question/answer/company_code/trace_id/module_status/evidence_ids/created_at`，`sessions.py:202-331`。 | `api-client.ts:164-166`、`ChatPage.tsx:52-91` 已消费；前端 `SessionTurnData` 也含 `evidence_ids`。 | 本轮已对齐。需补契约测试，防止 `evidence_ids` 回归缺失。 |
| P2 | `DELETE /sessions/{id}` | 返回 `data={deleted,session_id}`；`sessions.py:334` 起。 | `api-client.ts:174-179`、`ChatPage.tsx:120-135` 已消费。 | 当前对齐；删除的全局证据保护属于后端数据安全，不是字段错位。 |
| P2 | `GET /evidence/{id}` | 返回 `data={evidence,claims,source}`，`provenance.py:171-224`；无 response model。 | 无 client 方法、无页面调用。 | 端点可用但前端证据详情未接入；若证据徽章需要详情，应增加方法和 canonical DTO。 |
| P2 | `GET /claims/{id}` | 返回 `data={claim,evidence,turn}`，`provenance.py:227-261`；无 response model。 | 无 client 方法、无页面调用。 | 端点未消费；Claim 详情链路未打通。 |
| P2 | `GET /traces/{trace_id}/provenance` | 返回 `data={trace_id,claims,evidence}`，`provenance.py:264-315`；无 response model。 | 无 client 方法、无页面调用。 | 端点未消费；可作为调试/评测专用，但应在契约标明用途。 |

### 3.1 旧 `API_CONTRACT.md` 中的端点

| 级别 | 旧契约端点 | 后端实际 | 前端实际/处理 |
|---|---|---|---|
| P1 | `POST /api/v1/files/upload`（`API_CONTRACT.md:238-263`） | OpenAPI 无此路径，路由目录无 upload router。 | 无 client、无页面。应从旧文档删除或在 V1 明确“未实现”，不要让前端按此开发。 |
| P1 | `GET /api/v1/companies/{company_id}/ownership`（`API_CONTRACT.md:301-339`） | 实际只有 `/companies/{code}/equity`；OpenAPI 无 ownership。 | 前端使用 `/equity`；旧 ownership 契约已失效。应归档/标明迁移映射。 |
| P1 | `GET /api/v1/companies/{company_id}/timeline`（`API_CONTRACT.md:343-381`） | 实际只有 `/companies/{code}/events`；OpenAPI 无 timeline。 | 前端使用 `/events`；旧 timeline 契约已失效。 |
| P1 | `POST /api/v1/reports` | `API_CONTRACT_V1.md:119-122` 列出但 OpenAPI 无 reports，路由目录也无 reports。 | `frontend/src/pages` 无 `ReportPage.tsx`，`App.tsx:15-21` 无 `/reports/:reportId`。报告能力端到端缺失。 |
| P1 | `GET /api/v1/reports/{report_id}` | 同上，后端/前端均无实现。 | 同上。 |
| P1 | `GET /api/v1/reports/{report_id}/file` | 同上，后端/前端均无实现。 | 同上。 |

## 4. WS 事件逐项对照

后端统一信封由 `chat.py:250-263` 生成，实际包含契约要求的 9 个字段；前端 `api-client.ts:195-210` 将这些字段定义为可选，且未做 schema 校验。

| 级别 | 契约事件/字段 | 后端实际 | 前端实际消费 | 结论/建议 |
|---|---|---|---|---|
| P0 | `chat.query.payload={text,session_id}`（`WEBSOCKET_CONTRACT_V1.md:40-47`） | 后端从 `payload.session_id` 读取并覆盖会话 ID：`chat.py:281-288`；问题文本从 `payload.text` 读取：`chat.py:357-368`。URL query 未读取。 | `wsClient.create` 把 ID放 query：`api-client.ts:213-215`；`send` 的 payload 只有 `{text}`：`api-client.ts:237-244`。 | **核心错位**。每次连接会使用后端 `chat.py:244` 生成的随机 session，而不是前端当前会话。最小修复：把 `session_id` 加入 payload；同时保留/明确 query 兼容，增加四轮同会话持久化回归。 |
| P2 | `chat.follow_up` | 后端将它纳入有效 query 类型：`chat.py:334-345`，但没有单独语义处理。 | 前端所有消息都发送 `chat.query`：`api-client.ts:237-244`；没有 follow_up 方法。 | 当前多轮可能仍能跑，但事件语义丢失。统一发送 `chat.follow_up` 或明确服务端 query/follow-up 等价，并在契约注明。 |
| P2 | `company.confirm` | 接受后仅发送 `turn.accepted` 和 mock `turn.completed`：`chat.py:347-355`，不消费 `company_ref`。 | `ChatPage.tsx:274-275` 空分支；无发送方法。 | 候选消歧闭环未实现。仅在确有候选事件时排期，不应把当前 mock 完成事件当作真实确认。 |
| P2 | `turn.cancel` | 后端设置取消标志并发送 `turn.cancelled`：`chat.py:311-317`；`turn.cancelled` 不在 V1 server event 表 `WEBSOCKET_CONTRACT_V1.md:49-62`。 | 无 cancel 方法；只在 `onclose` 造一个内部旧格式 `done`：`api-client.ts:232-244`。 | 事件集合不一致。最小修复是把 `turn.cancelled` 纳入契约或改为契约规定的 `turn.failed`，同时增加前端 cancel API。 |
| P2 | `stream.resume` | 后端返回 `turn.failed/STREAM_RESUME_UNAVAILABLE`：`chat.py:319-332`，没有补发历史事件。 | 无 resume 方法。 | 契约允许服务端恢复，但当前明确不支持；归 Phase D 重连任务，并在契约中标为当前不可用。 |
| P2 | `ping`/`heartbeat` | 收到 `ping` 发送 `heartbeat`：`chat.py:301-309`。 | 无 ping 方法；收到 `heartbeat` 空处理：`ChatPage.tsx:276-277`。 | 当前无功能阻断，但没有客户端保活。 |
| P2 | `company.candidates` | V1 表列为可选，后端没有发送分支。 | `ChatPage.tsx:274-275` 空处理。 | 当前无候选选择闭环；需要消歧时再补 server event 和 `CandidateSelector`。 |
| P2 | `warning.raised` | V1 表列为可选，后端把 warning 汇总进 `turn.completed.payload.warnings`：`chat.py:479-517`，不发送独立事件。 | 无 warning.raised 处理；`turn.completed` warnings 也未映射 panel。 | 可以保持“汇总在 completed”的实现，但应更新契约或补独立事件，不要两套语义并存。 |
| P0 | `artifact.upsert` | 后端只发送一个 `risk_assessment`，`data` 只有 `risk_level`：`chat.py:462-475`；虽契约支持 `finance_rules/equity_graph/event_timeline/...`（`WEBSOCKET_CONTRACT_V1.md:89-104`），当前没有这些 artifact。 | `ChatPage.tsx:137-279` 没有 `artifact.upsert` 分支；`setPanelData` 只在旧 `structured_data` 分支 `157-160` 被调用。 | **分析面板数据链断裂**。最小修复：在 ChatPage 映射 `risk_assessment` 和 `turn.completed` 的 finance/risk/follow_ups 为 `PanelData`；后续再补完整 artifact 类型。 |
| P1 | `turn.completed` payload | 后端实际包含 `answer/risk_level/claims_count/follow_ups/evidence_count/evidence_ids/warnings/finance`：`chat.py:499-519`。 | 前端只读取 `answer/follow_ups/evidence_ids`：`ChatPage.tsx:219-268`，忽略 `risk_level/finance/claims_count/warnings`。 | 主回答可显示，但结构化结果丢失；与 `AnalysisPanel` 需求不匹配。 |
| P2 | `module.started/completed` | 后端发送执行模块和 `duration_ms`：`chat.py:423-449`。 | 前端没有对应分支。 | 右侧“模块状态”无法反映真实执行进度；若当前 UI 只展示最终状态，至少在 `turn.completed` 使用 typed module status。 |
| P2 | `answer.delta` | 后端 payload 使用 `text`：`chat.py:451-460`。这是按句切块的既定 Phase C 伪流式。 | 前端同时兼容 `text/content`：`ChatPage.tsx:205-217`。 | 字段已对齐；本次不修伪流式。 |
| P2 | `turn.accepted`/`turn.failed` | 后端实际发送；`chat.py:375-380,411-419,529-537`。 | 前端处理 accepted/failed：`ChatPage.tsx:202-204,270-273`。 | 基本对齐；建议用事件 schema 做运行时/测试校验。 |

## 5. 页面级联调结论

| 页面 | 数据依赖链 | 结论 |
|---|---|---|
| `ChatPage` | `GET /sessions` → `SessionSidebar`；选中后 `GET /sessions/{id}` → `SessionTurnData` → 消息；`wsClient.create` → WS `chat.query` → `ChatInterface`；WS artifact/completed → `AnalysisPanel` | **有 2 处 P0/P1 错位**：WS session ID 未进入 payload；V12 artifact/completed 未写 `panelData`，分析面板缺风险/规则/指标。历史会话详情和 `evidence_ids` 已在当前工作树接入（`ChatPage.tsx:52-91`、`sessions.py:249-291`）。 |
| `CompanyProfilePage` | `getCompanyProfile` + `getFinance` + `getEquity` + `getEvents` + `getRisk`（`CompanyProfilePage.tsx:119-132`）→ 概览、RuleCard、股权图/关联方、时间线、证据链 | **有 2 处错位**：风险 `evidence` 使用了错误的 `ChatEvidenceV1` 类型，证据卡字段不匹配；独立 `/benchmarks` 端点未消费。其余企业/财务/股权/事件主字段当前对齐。 |
| `ComparePage` | `/compare?codes=a,b` → `compareCompanies` → `ComparisonsResponseData` → 公司卡、风险/coverage/规则指标 | **有 1 处 P1 错位**：`/compare` 默认入口来自 `SessionSidebar.tsx:53-59` 和 `app-header.tsx:9-10`，不带 codes，页面必然先显示选择错误。 |
| `ReportPage` | 设计要求 `/reports/:reportId` → 创建/查询/下载 reports API | **整体未实现**：`frontend/src/pages` 无报告页，`App.tsx:15-21` 无路由，后端无 reports router。 |
| `AnalysisPanel` | 组件需要 `PanelData={risk_level,triggered_rules,key_metrics,follow_ups}`（`truthnet.ts:111-116`），由 ChatPage 产生 | **有 1 处 P0 错位**：组件字段本身可渲染，但 ChatPage 只从旧 `structured_data` 设置 `panelData`，没有把正式 V12 WS 事件映射进去；实际完成事件后 `data` 通常仍为 `null`。 |

## 6. 前端类型与后端 schema 交叉核验结果

### 已发现的字段级问题

| 级别 | 前端类型/消费 | 后端 schema/实际 | 证据 |
|---|---|---|---|
| P1 | `ChatDataV1` 没有 `claims/module_status/risk_level` | `ChatDataV1` 后端包含三者，且 `module_status` 是 `ModuleStatusV1` typed 对象 | `frontend/src/types/truthnet.ts:464-474` vs `backend/app/api/v1/schemas/chat.py:142-164` |
| P1 | `RiskResponseData.evidence: ChatEvidenceV1[]` | `/risk` 返回 `RiskEvidence[]`，字段仅 `evidence_id/source_type/claim_ids/summary` | `frontend/src/types/truthnet.ts:280-302` vs `backend/app/api/v1/schemas/risk.py:59-65,98` |
| P2 | `searchCompanies: V12Response<Company[]>` | `/companies` data 是 `{query,total,candidates}` | `frontend/src/lib/api-client.ts:121-123` vs `backend/app/api/v1/routers/companies.py:97-105` |
| P2 | `Company.list_date` | 后端字段为 `listing_date` | `frontend/src/types/truthnet.ts:61-70` vs `backend/app/api/v1/routers/companies.py:33-47` |
| P2 | WS `WSMessageType` 仍是 `thinking/text_chunk/structured_data/evidence/done/error` | V1 事件是 `turn.accepted/module.started/...` | `frontend/src/types/truthnet.ts:478-484` vs `docs/WEBSOCKET_CONTRACT_V1.md:49-62` |
| P1 | 大多数 client 返回类型只能靠手写接口推断 | OpenAPI 17 paths 中 14 个业务响应为 `{}` | `app.openapi()` 实测；路由 decorators 如 `companies.py:83,108`、`finance.py:71`、`events.py:203`、`risk.py:40`、`sessions.py:65,137,202,334` 未声明 response model |

### 建议的交叉校验方案（本次只提出，不实现）

1. **后端先完整声明 response model**：为 healthz/readyz、companies、finance、events、risk、benchmarks、comparisons、sessions、provenance 的成功响应及关键错误响应补 `response_model`/统一 Problem Details schema。否则 OpenAPI 生成出来仍是空对象，无法成为可靠事实源。
2. **CI 生成类型并做 diff**：用固定 truthnet 环境运行 `app.openapi()`，将 JSON 交给 `openapi-typescript` 或 `datamodel-code-generator` 生成 `frontend/src/generated/api.ts`；CI 比较生成文件与提交版本，禁止只修改手写 DTO 而不更新生成物。
3. **WS 独立 schema**：将 `WEBSOCKET_CONTRACT_V1.md` 中 envelope 和每种 payload 落成 Pydantic/JSON Schema，生成或共享 TypeScript discriminated union；`event_type` 必须决定 payload 类型，禁止 `payload: unknown` 作为长期类型。
4. **关键路径契约测试**：REST 至少覆盖 company search/profile、finance、equity、events、risk、benchmarks、sessions、comparisons、chat；断言响应 `data` 的前端消费字段存在。WS 至少断言 session/turn/trace 一致、`chat.query.payload.session_id` 生效、`artifact.upsert`/`turn.completed` 能形成 `PanelData`。
5. **页面联调测试**：Playwright mock/真实后端各跑 ChatPage 历史加载、WS 四轮、CompanyProfile 五请求、Compare 带 codes 和无 codes、Report 缺失路由；检查 console error、空白面板和关键字段渲染，而不是只跑 tsc。

## 7. 分级修复清单

### P0：本期应优先处理

| 编号 | 问题 | 最小改动位置 |
|---|---|---|
| P0-1 | WS 当前会话 ID未进入后端 payload | `frontend/src/lib/api-client.ts:237-244` 发送 `session_id`；后端 `chat.py:281-288` 保持 payload 为主并增加回归测试：同一 session 四轮、REST 回读同一 session。 |
| P0-2 | V12 artifact/completed 未驱动分析面板 | `frontend/src/pages/ChatPage.tsx:137-279` 增加 `artifact.upsert`、`turn.completed` 映射，至少构造 `PanelData.risk_level/follow_ups` 和 finance 规则/指标；由后端已有字段支撑，不改伪流式。 |

### P1：核心联调完成前处理

| 编号 | 问题 | 最小改动位置 |
|---|---|---|
| P1-1 | 风险证据 DTO 与证据组件错位 | 前端新增 RiskEvidence 展示类型/组件，或后端扩充 DTO；优先前端按 `/risk` 的正式 schema 消费。 |
| P1-2 | `/compare` 默认入口没有 codes | `SessionSidebar.tsx`/`app-header.tsx` 传真实选择结果，或 `ComparePage` 提供选择器后再调用。 |
| P1-3 | 报告端点、页面、路由全缺失 | 先在契约中标注未实现；按 Phase E/报告任务单独交付 `reports` router、`report_jobs` schema、ReportPage 和 App 路由。 |
| P1-4 | OpenAPI 大量 response `{}` | 为所有正式 REST 端点补 response models，再建立生成类型流程；这项是后续防止同类错位的基础设施。 |
| P1-5 | Chat 前端类型没有 claims/module_status/risk_level | 更新生成类型/`truthnet.ts`，并在 ChatPage 将 `turn.completed` 载荷或 REST data 映射到 UI。 |
| P1-6 | 公司搜索类型错误且无 UI | `api-client.ts:121-123` 改为 `CompanySearchData`；接入搜索/候选组件，或将搜索明确降级为未交付能力。 |

### P2：可排期一致性和完整消费

| 编号 | 问题 | 最小改动位置 |
|---|---|---|
| P2-1 | `/api/v1/health` client 路径不存在 | `api-client.ts:119` 改 `/healthz`，或删除未使用方法。 |
| P2-2 | benchmarks/provenance/readyz 未被前端消费 | 增加页面入口或在契约中标明运维/评测专用，避免“端点已实现即前端可用”的误解。 |
| P2-3 | WS 客户端缺 cancel/resume/ping/candidates 的类型和方法 | 单独按 Phase D 重连/取消任务排期；当前先把 `turn.cancelled` 与契约状态写清楚。 |
| P2-4 | 旧 `API_CONTRACT.md` 仍列 files/upload、ownership、timeline 和旧 WS | 不在本次改代码；由负责人确认后归档旧文档或补迁移表，避免继续被当作实现契约。 |
| P2-5 | 各 REST router 未声明 response model 的问题在 P1 基础设施完成后继续覆盖 provenance 等辅助端点 | 统一补 schema 和生成类型，不再靠 `Record<string, unknown>`/手写字段维持。 |

## 8. 遗留风险和范围边界

- 本次只读审计没有执行全量 pytest，也没有运行 POST chat、WS 或 DELETE；`614 tests collected` 仅证明可收集。已有 `592 passed` 基线未在本次重复确认，原因是本地 WS 集成测试会产生 MySQL 会话写入。
- `answer.delta` 目前是 Agent 完成后按句切块发送的伪流式，属于 Phase D，明确不列为本次契约错位修复。
- `stream.resume`、取消/重连、候选消歧应单独排期；它们是 WS 能力未完成，不应通过前端静默兼容掩盖。
- `GET /companies/{code}` 的 `risk_summary` 当前明确为 `null`，后端注释说明不伪造风险；这是数据交付状态，不是前后端字段错位。
- OpenAPI response schema 缺失会让“tsc 通过”继续产生假安全感：类型内部能编译，并不代表前端消费字段由后端保证。

## 9. 最终验收判定

> ⚠️ **本节为修复前结论，已被第 10 章（修复执行记录）与第 11 章（复核结论）覆盖。**

**修复前：** 不满足“前后端契约完全对齐”的验收标准。企业画像的财务/股权/事件主链路可以继续联调，但对话页的 WS 会话归属和分析面板结构化数据是 P0，必须先确认修复方案；报告页/报告 API 属于独立 P1 未交付能力。除上述问题外，会话历史 `GET /sessions/{id}` 与 `evidence_ids` 的当前工作树修复已在本审计中确认到位。

本报告完成后暂停在审计结论，等待人工确认，不自动开始修复。

## 10. 修复执行记录（2026-08-06 晚间）

按本报告第 7 节分级清单执行（用户确认三阶段全做 + 决策：报告排期、compare 加选股器）。

### 已修复

| 编号 | 修复 | 验证 |
|------|------|------|
| P0-1 | 前端 `wsClient.send` payload 补 `session_id`；后端保留 payload 优先 + URL query 兼容；新增 `test_payload_session_id_persists`（信封 session_id 一致 + REST 回读同会话） | 594 passed（+2） |
| P0-2 | ChatPage 新增 `artifact.upsert` 分支（risk_assessment → risk_level）+ `turn.completed` 映射（risk_level/triggered_rules/follow_ups → PanelData） | tsc |
| P1-5 | `ChatDataV1` 补 `claims/module_status/risk_level` | tsc |
| P1-4 | finance/events/risk/benchmarks/comparisons/companies 搜索+画像 共 7 路由加 `response_model`；新建 `schemas/companies.py`（CompanySearchData/CompanyProfileV1） | OpenAPI 19 个 HTTP 操作全有 200 schema（主链路 10 个为正式泛型引用）；冒烟字段完整 |
| P1-1 | `RiskResponseData.evidence → RiskEvidence[]`；EvidenceChain/CompanyProfilePage 按 `/risk` 正式 schema 消费（summary 摘要卡，移除 ChatEvidenceV1 字段） | tsc |
| P1-6 | `searchCompanies → CompanySearchData`（{query,total,candidates}）；`Company.list_date → listing_date` | tsc |
| P2-1 | health client 改 `/healthz` | — |
| P1-2 | ComparePage 无 codes 时渲染内置选股器（搜索→候选→2~5 家→navigate 带 codes） | tsc |
| P2-4 | API_CONTRACT.md 头部归档标注（files/upload 未实现、ownership→equity、timeline→events 迁移映射） | — |
| P2-3 | WEBSOCKET_CONTRACT_V1.md 补 `turn.cancelled` 事件行 | — |
| P1-3 | API_CONTRACT_V1.md 报告端点标注"排期 Phase D/E 报告任务" | — |
| 附加 | cleanup_sessions.py 清理后自动完整性复查（评级/事件簇缺失、无效 turn_id、断链 claim 四项，残留提示 restore --confirm）；本轮清理残留 14 条无效 turn_id 已用 restore_evidence --confirm 修复 | 复查全 0 |

### 仍为排期项（非本次范围）

- 真流式 answer.delta（Phase D #1）
- 报告端点 + ReportPage + 路由（Phase D/E 报告任务）
- WS cancel/resume/candidates 客户端能力（Phase D #1）
- sessions/provenance/healthz 的 response_model（P2-5，主链路 schema 已就位后可覆盖）
- 前端类型生成流水线（openapi-typescript 落地，前置 response_model 已完成）

### 数据库终态（修复后）

2 会话（ses_demo_teacher + c4bdbdd7）/ 8 轮 / claims 67 / evidence_refs 2421 / links 360；
评级 861 / 事件簇 1406 全绑定；完整性四项全 0。

## 11. 复核结论（2026-08-06 外部核查后修复）

外部核查提出 8 项问题（ruff format / OpenAPI 9 空 schema / 历史面板为空 / WS 测试污染 / 文档自相矛盾 / 契约状态过时 / Chat 类型不完整 / 白名单安全），已逐项修复：

| 项 | 修复 | 验证 |
|----|------|------|
| ruff format | test_chat_ws_agent 格式化 | `format --check` 263 文件全过、`ruff check` 通过、`git diff --check` 通过 |
| OpenAPI 9 空 schema | 新增 schemas/health.py、provenance.py、sessions.py（10 个 DTO）+ 9 路由接入 response_model + 错误响应（404/422/503 ProblemDetail）+ 契约测试 | **19/19 HTTP 操作全有非空 200 schema**；test_openapi_schema 新增 6 断言全过 |
| 历史面板为空 | v7 迁移（conversation_turns.panel_data JSON）+ persist_turn 构建面板摘要（risk_level/triggered_rules 取 rule_details.rule_name/follow_ups）+ GET /sessions/{id} 返回 panel_data + 前端历史加载恢复 + turn.completed/artifact 合并更新 | REST 返回 panel_data；旧数据 None 不崩溃；迁移已在本地 MySQL 执行 |
| WS 测试污染 | tests/_ws_cleanup.py 共享 helper + websocket/contract/smoke 三处 autouse fixture（仅 mysql 生效，测试后删除新增会话，失败告警） | **WS 测试前后会话数不变（5→5）** |
| 文档自相矛盾 | 第 9 章标注"修复前结论"；本文第 11 章复核 | — |
| 契约状态过时 | API_CONTRACT_V1 实现状态标记 ✅/⚠️/排期（见第 12 章说明） | — |
| Chat 类型不完整 | frontend types 新增 ClaimV1/ModuleStatusV1 完整类型（见第 13 章说明） | tsc 通过 |
| 白名单安全 | cleanup_sessions.py `--confirm` 未显式 `--keep` 时拒绝执行 | 见第 14 章说明 |

**数据库实测状态（外部核查时）**：1 会话 / 4 轮 / 44 claims / 2335 evidence / 207 links；
评级证据缺失 0 / 事件簇证据缺失 0 / 无效 turn_id 0 / 断链 Claim 0（四项完整性保留为 0）。

**OpenAPI 结论更新**：第 10 章此前写"19 个全有"是修复前中间态；本次修复后为 **19/19 全部正式 schema**（含 sessions/provenance/healthz 9 个新 DTO），OpenAPI 已可完整作为前端类型来源。

## 12. 运行态复核（2026-08-06 深夜，重启服务后）

外部核查发现"代码已修但 8000 服务未加载"的阻塞点，处理完毕：

| 核查项 | 结论 |
|--------|------|
| 8000 服务旧进程 | ✅ 已重启（bpgc2ia64），`/openapi.json` 实测 19/19 非空 schema + `SessionTurnV1.panel_data` 存在 |
| 旧演示会话无 panel_data | ✅ 按建议不反解析回填；新建四轮 WS 演示会话 `a416f5db-6f92-476d-9006-8cff77cc5103`（demo_ws_multi_turn 48/48 通过），4 轮全带 panel_data |
| 规则级 evidence_ids 为空 | ✅ 最终实现：`persist_turn._build_panel_data` 与 `chat.py finance_payload.triggered_rules` 均取 `rule_details[rid]["evidence_ids"]`（canonical ev_fin_*，与 evidence_refs 一致）；新增单测 + DB 存在性测试；新演示会话实测 **13/13 命中** |
| WS 测试会话污染 | ✅ 最终实现：各测试按 WS 信封显式跟踪（`ws_session_tracker`，只删本测试归属的 session_id，REST chat 测试先建会话显式传 session_id）；全局 pytest_sessionfinish 只检查告警、不删除；批次实测会话数不变 |

**面板验证实测**（新演示会话 GET /sessions/{id}）：

```
turn1: panel_data=有 risk=red rules=5 rule_evidence=13
turn2: panel_data=有 risk=red rules=5 rule_evidence=13
turn3: panel_data=有 risk=unknown rules=0 rule_evidence=0
turn4: panel_data=有 risk=red rules=5 rule_evidence=13
```

**当前演示白名单**：`0c23088d-b19e-40d5-b6de-1f0dc9182f2b`（五轮 WS 演示，5/5 轮含 panel_data、52 条规则级证据）；
（`a416f5db` 曾在验证中误删后重建为 `0c23088d`）
清理必须 `--keep` 显式保护（`--confirm` 无 `--keep` 已被脚本拒绝）。
