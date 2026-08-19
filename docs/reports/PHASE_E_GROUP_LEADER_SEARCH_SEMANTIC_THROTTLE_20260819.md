# Phase E 组长三项收口 — Web Search · 语义识别 · industry_fill 限流恢复（2026-08-19）

> 组长三项要求的统一收口报告。BASE_SHA=`21d8c6c`（main PR #47+#48，分支
> `feature/yuanyi-phasee-search-semantic-throttle`）。只连 truthnet_test；
> 不写库；无 --apply；无 --replace；无 git commit/push/merge。报告不含任何
> 完整密钥 / 本地个人路径 / 代理地址。

## 三项总览

| 任务 | 状态 | 报告 |
|------|------|------|
| A Web Search 真正调通 | ✅ 完成（真实联网最终 smoke 因本地无 Key 标记 BLOCKED，未伪造） | [TASK_A_WEB_SEARCH_CHECKPOINT_20260819.md](TASK_A_WEB_SEARCH_CHECKPOINT_20260819.md) |
| B 语义识别回归测试 | ✅ 完成（B0-B9 全交付） | [PHASE_E_TASK_B_SEMANTIC_20260819.md](PHASE_E_TASK_B_SEMANTIC_20260819.md) |
| C industry_fill 限流恢复 | ✅ 完成（C1-C12，全部 dry-run/probe/report-only） | 本文档 §3 |

安全约束全程保持：只连 truthnet_test、禁 --apply/--replace、禁自动 git 操作、
「搜不到比搜错好 / 识别不确定比绑定错好 / 数据没下完比打爆上游好」、报告无密钥。

---

## §1 Task A — Web Search 真正调通（摘要）

详见 [Task A checkpoint](TASK_A_WEB_SEARCH_CHECKPOINT_20260819.md)。要点：

- **A1 官方契约核验**：POST `api.bocha.cn/v1/web-search`，响应 `data.webPages.value[]`
  —— 当前代码解析路径与官方契约一致；任务 prompt 的「顶层 webPages」假设未证实，
  已加顶层兼容兜底（不改 `data.webPages` 优先路径）。
- **A2 上市日期事实提取**（核心修复）：禁止 `published_at` 作 listing_date，日期必须
  伴随「上市/挂牌」语义（±16 字符窗口）+ 反例排除；多结果互异 fail-closed 返回 None。
- **A4 缓存语义**：非空常驻；空结果短 TTL（30s）防永久污染；窗口内防重复空搜。
- **A5 HTTP 可诊断**：401/403/429/5xx/timeout/connection/空结果分类统计，日志无完整 key。
- **A7 真实 smoke**：本地 `WEB_SEARCH_API_KEY` 未配置 → **BLOCKED_BY_MISSING_LOCAL_API_KEY**；
  已交付 `scripts/web_search_real_smoke.py`（无 key 时正确输出 BLOCKED、零网络、未伪造）。
- **A8/A9**：三触发点 E2E 5 passed（truthnet_test，mock 后端）；`WEB_SEARCH_BACKEND=off`
  零 Provider 创建、零网络、原降级保持。
- 测试：web_search 三文件 + E2E 共 **70 passed**。

---

## §2 Task B — 语义识别回归测试（摘要）

详见 [Task B 阶段报告](PHASE_E_TASK_B_SEMANTIC_20260819.md)。要点：

- 新增 suggest 安全定义：`fabricated_code`（绑定不在候选集）、`auto_bind_on_ambiguity`
  （需确认样本上出现基线外新绑定）——B0/B1 双实验 + B6 全模块 **safety 零违规**。
- B4 手标数据集 50 条（A-J 十类，判别性样本清单见 `data/evaluation/README.md`）。
- B0 确定性基线：sample_acc 0.86 / identity_set 0.9091 / safety 0。
- B1 suggest 实验（never auto，真实 DeepSeek）：identity_set **0.9394（+0.0303）**；
  LLM 裁决 3 次被验证器拒绝、只读不应用（**never auto 实证**）；代价 2 条已知退化
  （否定语境重链误绑、确认消解），均不改绑定安全不变量。
- B6 路由模块级：finance/equity/events/comparison/unsupported **全 safety 0**；
  unsupported 全零绑定（最关键安全不变量）。
- B7 题库词表审计（数据1 1410 题）：100% 多轮、35.9% 点名词表内公司、64% 无公司名、
  「平安」多义为真实歧义压力源。
- B8 语义单测：178 passed，2 failed 在 stash 后干净基线复现（pre-existing）。
- B9 对比表：identity_set 0.9091→0.9394，llm_call_sample_rate 0→0.10。

---

## §3 Task C — industry_fill 限流恢复（C1-C12，禁 --apply）

### C1-C3 根因定位（核心缺陷）

`_fetch_batch`（push2 批量 `ulist.np/get`，`_BATCH_CHUNK=60`）在限流/降级时抛
`_Push2Throttled` → `query_many` 的**裸 `except Exception`** 把整块落入
`batch_miss.extend(chunk)` → 60 码整块转到逐股 `stock/get` 逐码查询 =
**1 个批量请求被放大成 60 个逐股请求**。全量缺失数千码时，这正是「限流重试风暴
把上游打死」的机制。C1-C3 不满足（批量限流时不得转逐股 + 需有界退避 + 需可诊断统计）。

### C4 批量熔断（`akshare_provider.py`）

- 常量 `_BATCH_CIRCUIT_FAIL_LIMIT=3`、`_BATCH_CIRCUIT_COOLDOWN=60.0`。
- 连续 3 次批量失败 → 熔断打开（`_batch_open_until`）→ 期间 `_fetch_batch` **fail-fast
  零网络**（`_batch_circuit_fail_fast` 直接抛 `_Push2Throttled`）→ 冷却后半开重试一次；
  成功 `_record_batch_success` 清零。
- 幂等保护：熔断已打开期间 fail-fast 抛出的失败不再重复累计（否则 opens 计数刷爆且
  重置冷却窗口）。

### C5 限流分类：批量限流 ≠ 连接失败（风暴根因修复）

```python
is_throttle = isinstance(batch_exc, _Push2Throttled) or throttled_flag[0]
if is_throttle:
    batch_throttled.extend(chunk)   # 整块 ERROR(throttled)，不转逐股（resume 重试）
else:
    batch_miss.extend(chunk)        # 连接/网络失败 → 整块转逐股（换源恢复合理）
```

- 限流 → 整块标记 `ERROR`（`throttled=True`, `last_error="批量限流，整块未转逐股
  （防风暴，resume 重试）"`），**零逐股**；
- 连接失败 → 仍转逐股（换源恢复是合法来源切换，非风暴）。

### C6 有界自适应节流（既有 `throttle.py`，复核贯穿）

RateController 复核：并发钳制 [1,8]、`RECOVER_EVERY=25` 恢复、`PRESSURE_MAX=3.0`、
`HOST_FAIL_LIMIT=3` 冷却 30s、负载感知 sleep + 抖动；CLI `--max-retries/--backoff-seconds`
已贯穿到请求层。本轮在 `query_many` 批量路径确认整块限流只计一次降并发（不放大成
60 次）。

### C7 运行统计

`report_stats()` 新增可诊断键（mock + 真机均可观测）：
`provider_batch_throttled` / `provider_batch_circuit_opens` /
`provider_batch_circuit_failfast`。

### C8 单元测试（mock HTTP，不发真实请求）

`backend/tests/unit/test_industry_fill_provider.py::TestBatchThrottleAndCircuit`
+ 新增 C11 resume 恢复循环测试；新增 `test_industry_fill_report.py`（报告白名单透出）。

- 批量限流整块 ERROR(throttled)、零逐股（`_fetch_direct` 置 boom 验证不触发）；
- 批量成功但块内个别 miss → 仅 miss 转逐股（合法）；连接错误仍转逐股；
- 熔断：190 码 4 chunk → 前 3 chunk × 3 主机 = 9 次请求，第 4 chunk fail-fast **零网络**
  （请求计数冻结 9），opens=1、failfast=1；
- **C11 resume 恢复循环**：Phase1 批量限流 → ERROR(throttled) 零逐股；Phase2 以该批为
  cached 再 resume（仍限流）→ 保持 ERROR(throttled) 零逐股（风暴不复发）；Phase3 上游
  恢复 → 收敛 SUCCESS。证明 `cached_skip` 对 ERROR 不跳过（档案 §6.1 重试契约）；
- 报告白名单含 Task C 三诊断键（build_report/render_text 透出）。

**结果：industry_fill 全套 7 文件 106 passed。**

### C9 阶梯 canary E0-E5（全部 dry-run / probe / report-only）

truthnet_test 基线覆盖 100%（10/10 无缺失）→ 批量路径无法触发。经自查后向
truthnet_test 种入 **3 条可逆夹具**（工商银行/招商银行/美的集团，`industry_l1=NULL`，
`source_type=fixture_c11_canary`），跑完阶梯后**已删除并复验恢复 10/10**。全程 `--apply`
零次、`--replace` 零次。

| 阶梯 | 命令形态 | 结果 |
|------|---------|------|
| E0 | `--probe`（不连库） | ✓ push2 批量 f100 + 逐股 f127 真机连通（600519→白酒Ⅱ）；akshare 未安装（fallback 不可用，预期） |
| E1 | `--dry-run --limit 2`（覆盖 100% 时） | ✓ 守卫链通过（profile→SELECT DATABASE()→快照→报告），0 批量请求 |
| E2 | 夹具后就绪 `--dry-run --limit 2` | ✓ 真机批量主路径：`provider_batch_requests=1`、success=2、miss=0；主机轮换活体（push2/82 重试后 push2delay 命中，`host_distribution={push2delay:1}`） |
| E3 | `--dry-run --limit 3` | ✓ 3 缺失全解析（success=3，主站直连 retries=0） |
| E4a | `--resume <E3 run_dir> --limit 3` | ✓ **C11 恢复语义真机证明**：复用 staging 3 条、`cached=3`、**零网络**（`batch_requests=0`） |
| E4b | `--resume <E3 run_dir> --limit 2`（改切片） | ✓ **fail-closed 真机证明**：input_hash 不匹配 → `[FAIL] resume 拒绝`，退出码 1 |
| E5 | `--report-only` | ✓ 只读覆盖率报告（13/10/3，夹具期） |

### C10/C12 门禁与诊断透出

- **零 `--apply`**：全部阶梯命令为 probe/dry-run/report-only，报告 `companies_updated=0`、
  `dry_run_no_change_ok` 保持；夹具清理后复验 `total=10, with_industry=10`。
- **C12 报告白名单修复**：发现 `report.py::REPORT_METRIC_KEYS` 为白名单，
  `report_stats()` 计算的 Task C 三诊断键被 `build_report()` **静默丢弃**（报告看不到）。
  已补白名单 + 单测锁定（`test_industry_fill_report.py` 5 passed）。

### C11 offset/resume 语义核验（结论）

- `--offset` 切片 `missing[offset:]`，不改 staging 内容；`--resume` 复用 run 目录，
  元数据门禁要求**输入清单一致**（input_hash 匹配）——**换 offset/limit 切片 resume
  fail-closed**（E4b 真机证明；`test_input_hash_diff_rejected` 单测锁定）。这是设计意图：
  resume = 同切片重试失败项，推进到下一切片请开新 run。
- ERROR(throttled) 记录 resume 时**必被重查**（`cached_skip` 对 ERROR 返回 False），
  熔断计数跨 query_many 不重置 → 限流风暴后可安全收敛（C8 恢复循环测试 + E4a 真机）。

---

## §4 质量门禁

| 门禁 | 结果 |
|------|------|
| ruff check（18 个改动/新增文件） | ✅ 通过 |
| ruff format --check | ✅ 通过（5 文件格式化后） |
| `python scripts/doctor.py` | ✅ 60/61 PASS（1 WARN = 直接调用 conda env python 未走 activate 的检测假象，环境本为 truthnet） |
| `python scripts/encoding_path_audit.py` | ✅ 无 CRLF / 无硬编码盘符 / .env 未 track（1 WARN 在未改动的 migrate_finance_evidence.py:321） |
| `git diff --check` | ✅ 无空白错误 |
| 全量 `pytest backend/tests` | 1749 passed + 59 skipped |
| 定向套件 industry_fill(7 文件)+web_search(4 文件) | ✅ 161 passed |

### 全量 7 failed — 全部 pre-existing（基线复核）

在 `git stash push -- backend/`（剥离本次全部改动）后的干净基线 HEAD `21d8c6c`
上逐一复现**同样的 7 个失败** → 均为本分支既有问题，与本次三项任务无关，按
「不得删除失败测试使其变绿 / 不得跳过错」原则**未修改**：

| 失败测试 | 根因 |
|---------|------|
| test_company_entity_resolver.py ×4（ambiguous_mention_kept / override_resume / override_comparison ×2） | 注入库 贵州茅台 `aliases=None`，"茅台" 简称无法 exact 命中（分割不再产出 茅台 mention）→ KeyError / reason_code 断言失败 |
| test_mentionness_classifier.py::test_sub_span_absent_keeps_whole_span | 陈旧期望：断言整句 not_found，但当前 segmentation 已正确剥离子实体 |
| test_ws_confirm_mentions.py::test_multi_mention_only_unconfirmed_needs_confirm | 同上：注入 贵州茅台 无 alias，"茅台" 缺失 |
| test_audit_four_hop_paths.py::test_audit_script_runs_without_driver_warning | **Neo4j 未启动**（127.0.0.1:7687 WinError 10061 拒绝连接）→ ENVIRONMENT_BLOCKED |

---

## §5 修改文件清单（待组长审阅，未提交）

**Task A（Web Search）**
- `backend/app/application/services/web_search_fact_fill.py`（A2 上市日期提取重写）
- `backend/app/application/services/web_search_service.py`（A4 缓存语义）
- `backend/app/infrastructure/web_search/bocha/provider.py`（A5 分类统计）
- `backend/app/agents/nodes/events.py`、`backend/app/agents/nodes/generate_answer.py`、
  `backend/app/api/v1/routers/companies.py`（触发点接线）
- `scripts/web_search_real_smoke.py`（新增，A7）
- `backend/tests/unit/test_web_search_provider.py`、`test_web_search_service.py`、
  `test_web_search_fact_fill.py`（修改）、`test_web_search_phaseE_e2e.py`（新增）

**Task B（语义识别）**
- `scripts/evaluate_company_entity_linking.py`（_safety 修正 + --score-target/--authority-strict）
- `scripts/validate_entity_linking_routes.py`（新增，B6）、`scripts/audit_question_bank_wordlist.py`（新增，B7）
- `data/evaluation/`（B4 数据集 + README）、`data/reports/`（B0/B1/B6/B7 输出）

**Task C（industry_fill 限流恢复）**
- `backend/app/application/services/industry_fill/akshare_provider.py`（C4 熔断 + C5 限流分类 + C7 统计）
- `backend/app/application/services/industry_fill/report.py`（C12 白名单透出）
- `backend/tests/unit/test_industry_fill_provider.py`（TestBatchThrottleAndCircuit + C11 恢复循环）
- `backend/tests/unit/test_industry_fill_report.py`（新增，C12 锁定）

**报告**：本报告 + Task A checkpoint + Task B 阶段报告（`docs/reports/`）。

### 推荐 commit message（多原子提交）

```text
fix(industry_fill): 批量限流不转逐股防风暴 + 批量熔断 fail-fast（C4/C5/C7）
fix(industry_fill): report 白名单透出批量限流/熔断诊断键（C12）
fix(web_search): 上市日期事实提取 + 缓存语义 + HTTP 分类统计（Task A）
test(semantic): 评估器 _safety 修正 + suggest 实验 + 路由验证 + 词表审计（Task B）
test(industry_fill): 熔断/限流分类/resume 恢复循环/report 白名单单测（C8/C11）
docs: Phase E 组长三项收口报告（Search/Semantic/Throttle）
```

### 推荐 PR title

`Phase E 收口：Web Search 调通 · 语义识别回归 · industry_fill 限流恢复（禁 --apply）`

---

## §6 未完成 / 阻塞

- **Task A 真实联网 smoke**：本地无 Bocha key → `BLOCKED_BY_MISSING_LOCAL_API_KEY`
  （配置 `WEB_SEARCH_BACKEND=bocha` + `WEB_SEARCH_API_KEY=<key>` 后运行
  `scripts/web_search_real_smoke.py` 即可完成最后一步）。
- **Task B auto 模式**：未获授权运行（suggest 只读是本次边界）；「康美的存贷比」动作词
  吞 sub_span 是 auto 模式价值场景，留给后续授权。
- **全量 7 个 pre-existing 失败**（含 Neo4j 未启动）非本次引入，建议数据组/后端组
  另行修复（给贵州茅台 seed 补 alias、更新 stale 断言、启动 Neo4j）。
- **truthnet_test 夹具**：E2-E4 用 3 条可逆夹具已清理并复验 10/10，无残留。
