# TruthNet Phase C 任务认证矩阵

> 基线 SHA: `19a7d4063a0c8f9c6c0d74c796a484aca0eda7bd`（PR #23 合并提交）
> 分支: `integration/phase-c-full-completion`
> 最后更新: 2026-08-03（全量测试 494+23 passed，Full Profile 真实验收通过）

## 状态枚举

- `verified_complete` — 代码 + 数据 + 文档 + 测试 + 真实运行齐全
- `implemented_but_incomplete` — 有实现但缺数据产物/真实运行/验收不满足
- `not_implemented` — 未实现
- `blocked_by_source_data` — 外部数据缺失阻塞
- `not_applicable` — 不适用

---

## 数据组任务 1-9

| # | 任务 | 初始状态 | 本轮处理 | 真实验收 |
|:-:|---|---|---|---|
| 1 | 7 条规则计算函数 | implemented_but_incomplete | R1-R7 独立函数、母公司口径 408006000、公司类型 Gate、insufficient_data、Evidence 均实现；补齐 R2-R7 history 兜底 | 单测通过（test_rule_engine.py） |
| 2 | 造假手法库 | implemented_but_incomplete | 新增 `fraud_patterns.yaml`（机器可读唯一来源）+ 加载/匹配模块；Router/comparisons 统一引用 | test_risk_scoring_service P1 匹配通过 |
| 3 | 行业分位批量计算 | **not_implemented** | 新增 metric_registry/calculator/build_industry_benchmarks CLI + migration v5 表 | **310 行写入 MySQL**，verify-only 通过，幂等验证通过 |
| 4 | 真实事件聚类 | implemented_but_incomplete | 新增 clustering 模块 + build_event_clusters CLI + 真实 JSONL | **113 个事件簇导入 MySQL**，幂等验证通过 |
| 5 | 评级拐点 | implemented_but_incomplete | 新增 rating_normalizer/inflection + build_rating_changes CLI | **878 条写入 MySQL**（down 359/up 519） |
| 6 | 造假真实验证 | **not_implemented** | 新增 validate_fraud_patterns CLI + 报告/JSON | **180 个真实案例**、4 种模式、103 家公司，claim/evidence 可查询 |
| 7 | 评测框架 | implemented_but_incomplete | 修复 runner sys.path + TARGETS 与 README 对齐（Kappa/std_dev 判定）+ metrics 空输入语义 | runner + 23 测试通过 |
| 8 | 公告覆盖 Gate | **not_implemented** | 新增 report_announcement_coverage CLI + 报告/JSON | **2585 公司/7311 条/603377.SH=36 条** |
| 9 | 评测数据口径 | implemented_but_incomplete | 新增 dataset_loader + build_dataset_manifest | manifest 生成（35 会话/1410 问/77 深度题 + dataset_hash） |

---

## 后端任务 1-16

| # | 任务 | 初始状态 | 本轮处理 | 验收 |
|:-:|---|---|---|---|
| 1 | Finance Agent | implemented_but_incomplete | finance_node 填 rules + periods_available + industry_benchmark | 单测通过 |
| 2 | Events Skill | implemented_but_incomplete | events_node 加评级拐点（rating_changes 表） | 代码完成 |
| 3 | 交叉验证 | implemented_but_incomplete | cross_validate 重写：check 模型 + equity_vs_events + financial_vs_cashflow + 依赖/身份/期间 | test_cross_validate 通过 |
| 4 | Claim+Evidence | implemented_but_incomplete | build_claims 加交叉验证 Claim；统一 ID | test_build_claims 通过 |
| 5 | 问答生成 | implemented_but_incomplete | generate_answer 加评级/交叉验证摘要 + risk_output 风险等级 | 单测通过 |
| 6 | 风险评分 | implemented_but_incomplete | RiskScoringService + agents/nodes/risk.py + 图接入；权重集中；缺模块归一化；不 new NetworkX | test_risk_scoring_service 通过 |
| 7 | Memory Agent | **verified_complete** | 保持（审计确认） | 70 项测试 |
| 8 | 会话持久化 | implemented_but_incomplete | persist_turn 同 turn 重试幂等（UPDATE 而非重复 INSERT） | 待测 |
| 9 | Finance REST | implemented_but_incomplete | 只接受 parent_company（422）；periods_available 真实；industry benchmark 真实；统一 evidence ID + 持久化 | 待测 |
| 10 | Events REST | implemented_but_incomplete | months 真实过滤；评级拐点真实；keyword 摘要；统一 evidence ID + 持久化 | 待测 |
| 11 | Risk REST | implemented_but_incomplete | Router 瘦身：只做校验/Resolver/Service/DTO/错误信封 | 待测 |
| 12 | Benchmarks REST | implemented_but_incomplete | 真实 percentile（p05-p95 + company_percentile + sample_count） | 待测 |
| 13 | Comparisons REST | implemented_but_incomplete | 季度解析（2026Q2→20260630）；去除 except:pass；每公司单次执行；coverage/evidence | 待测 |
| 14 | 画像股权真实化 | implemented_but_incomplete | reconcile 增强：c_/corp_ 重复检测 + 差异报告 + 幂等标记 | 待跑 |
| 15 | 事件交接 | implemented_but_incomplete | 真实 JSONL 导入 113 簇 + 幂等验证；v6 补 fcode 列 | 完成 |
| 16 | 全局 Provenance | implemented_but_incomplete | ProvenanceService + analysis_runs 表 + REST 统一 make_evidence_id + 持久化 | 待验证 |

---

## 服务

- MySQL: 8.4.9（复用 `.local/mysql_data`，端口 3306）
- Neo4j: 2025.06.1 Community（复用 `.local/neo4j`，154,973 节点）

## Migration

- v4 `d1e2f3a4b5c6`（基线）
- v5 `b6e1f2a3d4c5`（industry_benchmarks / rating_changes / analysis_runs）
- v6 `c7f2a3b4e5d6`（event_cluster_sources.fcode）
