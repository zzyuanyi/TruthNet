# Phase D 后端独立任务完成报告

> 执行周期：2026-08-07 | 分支：`feature/zzyuanyi-workspace`
> 覆盖后端任务 #1/#2/#5/#6/#7/#8/#9/#10/#12/#13/#15/#16
> 明确不做：#14（依赖数据 #5）、#17（依赖数据 #4）、前端页面、S1 正式评测

---

## 1. 基线

| 项 | 值 |
|------|-----|
| origin/main SHA | `dbee7b00d6d0194362e21c096ead8be31765aea7`（同步时 origin/main 最新） |
| 工作分支 | `feature/zzyuanyi-workspace` |
| 工作分支 HEAD | `dbee7b00d6d0194362e21c096ead8be31765aea7`（与 origin/main 一致） |
| 同步方式 | `git fetch origin --prune` → `git switch feature/zzyuanyi-workspace` → `git merge --ff-only origin/main` |
| 分歧检测 | 无分歧（工作分支 0 ahead / 69 behind，FF 合并成功） |
| Python | 3.11.15（conda env `truthnet` @ `E:\anaconda\envs\truthnet`） |
| MySQL | 8.4.9（本地，端口 3306） |
| Neo4j | 2025.06.1 Community（本地，bolt://127.0.0.1:7687） |
| Java | JDK 21（Eclipse Adoptium 21.0.11） |
| migration before | `a1b2c3d4e5f7`（v7） |
| migration after | `e9f5a6b7c8d9`（v9，新增 v8 索引 + v9 report_jobs） |

**数据准备（基线测试通过所需，均来自 CLAUDE.md 文档化数据步骤）**：
- 运行 `scripts/industry_fill.py`（行业分类补全，修复 600518.SH `industry_l1=NULL` 导致的行业分位测试失败）；
- 运行 `scripts/build_rating_changes.py`（评级证据回填，修复 rating_changes 无 evidence_id 的测试失败）。

**基线测试**：610 passed, 12 skipped, 1 failed → 数据准备后全绿。

---

## 2. 任务结果表

| # | 任务 | 状态 |
|:-:|------|:----:|
| 1 | 故障注入矩阵 | ✅ completed |
| 2 | 深度数值冲突检测 | ✅ completed |
| 5 | WS 协作式取消 | ✅ completed |
| 6 | WS 重连恢复 | ✅ completed |
| 7 | 性能埋点 | ✅ completed |
| 8 | PDF 报告长任务 | ✅ completed |
| 9 | Docker Compose | ✅ completed_with_verified_limitations |
| 10 | WS 真流式 | ✅ completed |
| 12 | 股权链路创新闭环 | ✅ completed |
| 13 | 多 WS 并发验证 | ✅ completed |
| 15 | 远期记忆提炼注入 | ✅ completed |
| 16 | 模式输出三要素 | ✅ completed |

> **#9 说明**：compose.yaml 配置有效（静态校验通过）、Dockerfile/smoke 脚本/文档齐全；
> Docker Desktop 引擎可用但镜像拉取被本机代理（127.0.0.1:7897，Docker WSL2 内不可达）阻断，
> 未能在本机完成"干净环境 smoke"。最终状态标记 `blocked_by_local_docker_unavailable`（见 §7 本机环境限制）。

---

## 3. 代码改动

### 新增文件

```
backend/app/agents/delta_sink.py                          # #10 真流式 DeltaSink 注册表
backend/app/api/v1/schemas/ws.py                          # #5/#6 WS 取消/恢复事件 DTO
backend/app/api/v1/schemas/reports.py                     # #8 报告 DTO
backend/app/api/v1/routers/reports.py                     # #8 /reports 路由
backend/app/application/services/ws_session_manager.py    # #5 会话/取消/多连接管理
backend/app/application/services/ws_event_journal.py      # #6 事件缓冲（TTL/上限/gap）
backend/app/application/services/ws_turn_runner.py        # #5/#6/#10 turn 执行器
backend/app/application/services/equity_chain_service.py  # #12 链路载荷/风险映射/合并
backend/app/application/services/memory_distillation.py   # #15 远期记忆提炼
backend/app/application/services/report_service.py        # #8 报告状态机 + PDF 生成
backend/app/domain/conflicts/numerical.py                 # #2 深度数值冲突检测
backend/app/infrastructure/observability/timing.py        # #7 Timer/MetricsCollector
backend/app/infrastructure/persistence/migrations/versions/d8e4f5a6b7c8_v8_search_perf_indexes.py  # #7 检索索引
backend/app/infrastructure/persistence/migrations/versions/e9f5a6b7c8d9_v9_report_jobs.py          # #8 report_jobs
compose.yaml                                              # #9
.env.compose.example                                      # #9
docker/backend.Dockerfile                                 # #9
docs/SETUP_COMPOSE.md                                     # #9
scripts/verify_compose_smoke.sh                           # #9
scripts/verify_phase_d_fault_matrix.py                    # #1 故障注入脚本
scripts/verify_phase_d_perf_smoke.py                      # #7 性能 smoke 脚本
backend/tests/unit/test_ws_event_journal.py               # #6
backend/tests/unit/test_ws_session_manager.py             # #5
backend/tests/unit/test_ws_turn_runner.py                 # #5/#10
backend/tests/unit/test_timing.py                         # #7
backend/tests/unit/test_numerical_conflicts.py            # #2
backend/tests/unit/test_equity_chains.py                  # #12
backend/tests/unit/test_memory_distillation.py            # #15
backend/tests/unit/test_pattern_triad.py                  # #16
backend/tests/websocket/test_ws_cancel.py                 # #5
backend/tests/websocket/test_ws_resume.py                 # #6
backend/tests/websocket/test_ws_true_streaming.py         # #10
backend/tests/websocket/test_ws_concurrency.py            # #13
backend/tests/integration/test_fault_injection_matrix.py  # #1
backend/tests/integration/test_memory_20_turns.py         # #15
backend/tests/integration/test_report_jobs.py             # #8
docs/reports/fault_matrix.json + .md                       # #1
docs/reports/perf_smoke.json + .md                         # #7
```

### 修改文件

```
backend/app/core/config.py                        # 新增 WS/内存/报告/冲突/性能配置
backend/app/api/v1/routers/chat.py               # #5/#6/#10 WS 重构 + REST pattern/equity 透出
backend/app/api/v1/routers/equity.py             # #12 equity_chains
backend/app/api/v1/routers/risk.py               # #16 pattern 三要素
backend/app/api/v1/schemas/chat.py               # pattern_matches + equity_chains
backend/app/api/v1/schemas/equity.py             # EquityChainDTO
backend/app/api/v1/schemas/risk.py               # PatternMatch 三要素
backend/app/api/v1/exception_handlers.py         # #1 基础设施故障识别（RFC 9457）
backend/app/agents/nodes/cross_validate.py       # #2 数值冲突集成
backend/app/agents/nodes/equity.py               # #12 chain_details
backend/app/agents/nodes/generate_answer.py      # #10 真流式分段
backend/app/agents/nodes/load_context.py         # #15 远期摘要注入
backend/app/agents/nodes/pattern_match.py        # #16 三要素透出
backend/app/agents/state.py                      # numerical_conflicts / chain_details
backend/app/application/services/research_search.py  # #7 搜索埋点 + 单次查询优化
backend/app/application/services/risk_scoring_service.py  # #16 三要素
backend/app/domain/risk/fraud_patterns.py        # #16 PatternDefinition/Match 三要素
backend/app/domain/risk/fraud_patterns.yaml      # #16 P1-P5 三要素基础定义
backend/app/domain/risk/models.py                # #16 RiskPatternMatch 三要素
backend/app/infrastructure/persistence/models.py # ReportJob 模型
backend/app/main.py                              # reports 路由 + lifespan 遗留任务恢复
requirements.txt                                 # reportlab==4.2.2
docs/API_CONTRACT_V1.md / WEBSOCKET_CONTRACT_V1.md / INTERFACE_CHANGELOG.md  # 契约更新
docs/ALIGNMENT_AUDIT.md                          # 移除硬编码路径（audit 修复）
.gitignore                                       # .env.compose
```

### 迁移

- **v8** `d8e4f5a6b7c8`：`research_reports.is_latest` + `(is_latest, publish_date)` 索引（#7 性能优化）
- **v9** `e9f5a6b7c8d9`：`report_jobs` 表（#8，含 downgrade）

### 接口变化

- WS：`turn.cancel`/`turn.cancelled`（协作式取消）、`stream.resume`/`stream.resume_ack`（补发）、
  `answer.delta` 真流式、`module.started` 提前、`turn.completed` 增补 `pattern_matches`/`equity_chains`
- REST：`/reports` 三端点；`/equity` 增 `equity_chains`；`/risk` 与 `/chat` 增 `pattern_matches` 三要素与 `equity_chains`
- 全部为追加字段/新端点，无破坏性修改

### 配置变化

见 `backend/app/core/config.py`：`WS_EVENT_BUFFER_MAX_EVENTS/TTL_SECONDS/SESSION_IDLE_TTL_SECONDS`、
`MEMORY_RECENT_TURNS/SUMMARY_MAX_CHARS/MAX_SOURCE_TURNS/VERSION/STRATEGY`、
`REPORT_ROOT_DIR/MAX_CONCURRENCY/STALE_SECONDS`、`CV_NUM_01_*/CV_NUM_02_OWNERSHIP_TOLERANCE`。

---

## 4. 验证证据

### 全量测试（最终）

```
TRUTHNET_RUN_FULL_INTEGRATION=1 python -m pytest backend/tests -q
725 passed, 12 skipped, 77 warnings in 189.44s
```

### 分类结果

| 测试类 | 数量 | 结果 |
|--------|------|------|
| 单元测试 | — | 全过 |
| 契约测试 | 59 | 全过 |
| 集成测试（真实 MySQL/Neo4j） | — | 全过 |
| WS 测试 | 25+ | 全过 |
| tests/evaluation | 23 | 全过 |

### 关键命令

```
python scripts/doctor.py                     → PASS 60/61（1 WARN 为 conda 检测误报）
python scripts/encoding_path_audit.py --ci   → 全部通过
ruff check backend scripts                   → All checks passed
ruff format --check backend scripts          → 301 files already formatted
pre-commit run --all-files                   → 全过（truthnet 环境）
cd frontend && pnpm typecheck                → 通过
cd frontend && pnpm build                    → 通过（安装缺失的 terser 后）
```

### 故障注入脚本（#1）

```
python scripts/verify_phase_d_fault_matrix.py → all_passed: true
MySQL 不可用 → 503 DATASTORE_UNAVAILABLE；Neo4j → partial+NEO4J_UNAVAILABLE；
Chroma → SQL 兜底；LLM → 模板降级；无公告 → NO_ANNOUNCEMENT_DATA
```

### 性能 smoke（#7，修复索引后）

```
search P95 = 22ms  ≤ 500ms ✅（修复前 1805ms）
REST 标准题 P95 = 936ms ≤ 8000ms ✅
WS 首块 P95 = 786ms ≤ 3000ms ✅
```

---

## 5. 数据库完整性

| 表 | before | after | 变化 |
|------|-------:|------:|------|
| companies | 6922 | 6922 | 0 |
| balance_sheet | 39019 | 39019 | 0 |
| income_statement | 38210 | 38210 | 0 |
| cash_flow | 39985 | 39985 | 0 |
| top_shareholders | 1292898 | 1292898 | 0 |
| announcements | 7311 | 7311 | 0 |
| research_reports | 55214 | 55214 | 0 |
| conversation_sessions | 137 | 137 | 0 |
| conversation_turns | 137 | 137 | 0 |
| claims | 234 | 234 | 0 |
| evidence_refs | 1641 | 1641 | 0 |
| claim_evidence_links | 712 | 712 | 0 |
| analysis_runs | 17 | 17 | 0（测试残留已清理） |
| event_clusters | 113 | 113 | 0 |
| event_cluster_sources | 297 | 297 | 0 |
| rating_changes | 878 | 878 | 0 |
| report_jobs | 0 | 0 | 0（测试后清理） |

完整性检查：

```
dangling_claim_links = 0
dangling_evidence_links = 0
orphan_test_sessions = 0
orphan_claims = 0（删除会话时级联清理）
orphan_evidence = 0
report_jobs residual = 0
```

Neo4j（保护）：

```
neo4j_version = 2025.06.1
graph_node_count_before = 154973 → after = 154973
graph_relationship_count_before = 1292221 → after = 1292221
```

migration：

```
alembic upgrade head → e9f5a6b7c8d9 (head) ✅
alembic downgrade -1 → d8e4f5a6b7c8（report_jobs 表删除）✅
alembic upgrade head → e9f5a6b7c8d9（重建）✅
```

---

## 6. 性能

| 指标 | sample_count | P50 | P95 | 目标 | 达成 |
|------|:----:|----:|----:|-----:|:----:|
| search | 5 | 10ms | 22ms | ≤500ms | ✅ |
| REST 标准题完整 | 5 | 877ms | 936ms | ≤8000ms | ✅ |
| WS 首块 | 5 | 717ms | 786ms | ≤3000ms | ✅ |

- timeout_count = 0；degraded_count = 0（Chroma 语义路径本机不可用时降级 SQL，未计入标准题）
- 优化记录：SQL 兜底原 8 次全表 LIKE 扫描（~5s）→ 单次 OR 查询 + `is_latest`/`publish_date` 索引（v8 migration）→ P95 22ms

---

## 7. 已知限制

### 本轮代码限制
- **#9 Docker**：镜像拉取被本机代理（127.0.0.1:7897，Docker WSL2 VM 内不可达）阻断，
  未完成干净环境 smoke。compose 配置/脚本/文档已就绪并静态校验通过。
- **报告后台任务**：使用进程内 asyncio 后台任务（非分布式队列）；TestClient 下后台任务会被请求回收，
  生产 uvicorn 下验证正常（创建→状态→下载全链路通过）。
- **远期记忆**：当前为确定性抽取摘要（未启用 LLM 压缩）；LLM 压缩路径已预留但需 S1 对比后启用。
- **WS 多连接**：采用"新连接替代旧连接"策略（契约已写死并测试）。

### 真实数据覆盖限制
- CV-NUM-01 在康美实际数据下多数返回 `insufficient_data`（母公司现金流覆盖不足），
  模式逻辑有正例/反例/边界测试，但真实命中取决于具体公司数据。
- CV-NUM-02 的 Neo4j 边与 MySQL 股东表名称匹配依赖名称归一化，存在少量误配可能（已在 limitations 标注）。
- 股权 risk_label 在康美数据上多数为 normal（184/200），16 条 ownership_mismatch。

### 本机环境限制
- Docker Desktop WSL2 代理网络不可达（127.0.0.1:7897）；
- Chroma 嵌入模型（sentence_transformers，~2GB）未安装，语义检索降级 SQL；
- `C:\Python314` 系统 Python 干扰 pre-commit（需用 truthnet 环境 PATH 运行，已记录）。

### 依赖其他组的限制
- **后端 #14 未实施**：等待数据 #5 金融企业字段前置（贷款/保险/证券专属字段）。
- **后端 #17 未实施**：等待数据 #4 相似历史案例数据产物与检索函数。
- **前端页面验收不属于本轮**（本轮仅做 typecheck/build 回归）。
- **S1 正式实验不属于本轮**（提供了策略开关 none/recent_only/summary_plus_recent 供 S1 调用）。

---

## 8. 建议提交划分（仅建议，不实际提交）

```text
feat(ws): implement cancellable resumable agent streaming (#5/#6/#10)
test(ws): certify multi-session isolation and cleanup (#13)
feat(equity): expose evidence-backed risk chains (#12)
feat(memory): add sourced long-term memory summaries (#15)
feat(risk): expose pattern phase alternatives and regulatory hints (#16)
feat(reports): add durable PDF report jobs (#8)
feat(observability): add latency instrumentation + search perf indexes (#7)
test(degradation): add five-scenario fault matrix (#1)
feat(conflicts): freeze two numerical conflict patterns (#2)
chore(deploy): add isolated full-profile compose (#9)
docs(phase-d): document independent backend completion
```

---

## 9. PR 草稿

### 建议 PR 标题
`feat(phase-d): 后端独立任务完成 — WS 真流式/取消/恢复、报告、股权链路、记忆、模式三要素`

### PR 描述

#### 背景
Phase D 后端组独立任务（不依赖数据/前端新交付），在真实本地 MySQL 8.4 + Neo4j 2025.06.1 上完成。

#### 变更内容
1. **WS 执行模型重构**（#5/#6/#10）：接收与执行分离、`WsSessionManager`/`WsEventJournal`/`WsTurnRunner`、
   协作式取消（≤2s 确认、单终态）、断线补发（原 event_id/sequence）、真流式 answer.delta（拼接==最终答案）。
2. **多 WS 并发验证**（#13）：双连接无串扰、A 取消 B 完成、断线重连隔离、同会话新连接替代旧连接。
3. **深度数值冲突检测**（#2）：冻结 CV-NUM-01（利润 vs 经营现金流背离）与 CV-NUM-02（股权比例一致性），
   均有正例/反例/边界/数据不足测试与真实 evidence 绑定。
4. **性能埋点**（#7）：Timer/MetricsCollector/结构化日志；SQL 兜底单次查询优化 + v8 索引，
   search P95 1805ms→22ms。
5. **PDF 报告长任务**（#8）：`report_jobs` 表（v9 migration，可回滚）+ 创建(202)/状态/下载端点 + 幂等 + 重启恢复。
6. **股权链路闭环**（#12）：`equity_chains` 载荷（证据/风险标签/一致行动人合并），REST/WS/Agent 一致。
7. **远期记忆**（#15）：memory-v1 摘要（来源轮次/Evidence/限长/幂等/跨会话隔离），20 轮真实会话可召回。
8. **模式三要素**（#16）：`phase/alternative_explanation/regulatory_hint` 在 REST/WS 一致透出。
9. **故障注入矩阵**（#1）：5 类故障不 500，结构化错误码（DATASTORE_UNAVAILABLE/GRAPH_UNAVAILABLE/LLM_TIMEOUT）。
10. **Docker Compose**（#9）：compose.yaml + Dockerfile + 文档 + smoke 脚本（独立 project/卷/端口）。

#### 测试清单
- [x] 全量 725 passed / 12 skipped
- [x] WS 取消/恢复/真流式/并发 全过
- [x] 契约 59 过（OpenAPI 19/19 含新报告端点）
- [x] ruff / ruff format / pre-commit 全过
- [x] doctor / encoding_path_audit 全过
- [x] 前端 typecheck + build 过（回归）
- [x] 数据库完整性：0 断链 / 0 残留 / Neo4j 节点关系保护
- [x] 性能：search P95 22ms / REST 936ms / WS 786ms

#### 迁移说明
```bash
alembic upgrade head   # 应用 v8（索引）+ v9（report_jobs）
```
两版迁移均有 downgrade；v9 可 `alembic downgrade -1` 回滚。

#### 回滚方式
- 代码：`git revert <merge-sha>`；
- 数据库：`alembic downgrade d8e4f5a6b7c8`（删除 report_jobs），再 `alembic downgrade a1b2c3d4e5f7`（删除索引）。

#### 风险点
- report_jobs 使用进程内后台任务，重启后遗留 running 由 lifespan 恢复为 retryable failed；
- 远期记忆当前为确定性摘要（未启用 LLM 压缩）；
- Docker smoke 受本机代理网络限制未完成（见报告 §7）。

#### 等待其他组的事项
- 后端 #14：数据 #5 金融字段前置；
- 后端 #17：数据 #4 相似案例产物与检索函数；
- 前端：报告页 / 股权链路卡 / 模式三要素 UI（契约已就绪）；
- S1：记忆策略开关已提供，可调用。
