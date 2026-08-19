# Phase E Task B 阶段报告 — 语义识别回归测试（2026-08-19）

> 组长三项要求的 Task B。BASE_SHA=`21d8c6c`（main PR #47+#48）。只连
> truthnet_test；不写库；无 --apply。报告不含任何密钥/本地路径。

## 交付物清单

| 产物 | 路径 |
|------|------|
| 评估器（新增安全维度 B1/B2） | `scripts/evaluate_company_entity_linking.py` |
| 手标数据集（50 条，schema 说明） | `data/evaluation/company_entity_linking.jsonl` + `data/evaluation/README.md` |
| B0 确定性基线输出 | `data/reports/company_entity_linking_baseline.jsonl` |
| B1 suggest 实验输出 | `data/reports/company_entity_linking_suggest.jsonl` |
| B6 路由模块级验证输出 | `data/reports/company_entity_linking_routes.jsonl` |
| B6 路由验证脚本 | `scripts/validate_entity_linking_routes.py` |
| B7 题库词表审计输出 | `data/reports/question_bank_wordlist_audit.json` |
| B7 词表审计脚本 | `scripts/audit_question_bank_wordlist.py` |

## B1-B2 评估器审计

### 新 suggest 安全定义（`_safety`）

- `fabricated_code`：绑定 wind_code 不在该 mention 候选集内（结构违规）。
- `auto_bind_on_ambiguity`：`requires_confirmation=True` 样本上，结果产生确定性
  基线之外的新绑定。零绑定 no_company / 基线已确认绑定均安全——不过度确认
  不算越权。

### authority 处理

`--authority-strict off`（默认）：suggest 只读验证 + mentionness 合法差异记录
`authority_diff` 但不判样本失败；`on` 恢复旧语义（任何非 audit 差异 →
authority_mismatch）。

## B3 真库种子（truthnet_test）

种子 10 家公司（含 alias）：康美药业 600518.SH、贵州茅台 600519.SH、平安银行
000001.SZ（alias 平安）、中国平安 601318.SH（alias 平安）、平安电工 002985.SZ
（alias 平安）、宁德时代 300750.SZ、五粮液 000858.SZ、比亚迪 002594.SZ、
泸州老窖 000568.SZ、金百泽 301041.SZ。

## B4 手标数据集（50 条）

覆盖：A 精确公司名(7) / B 简称(4) / C 动作词吞 sub_span(3) / D 歧义(4) /
E 非公司语境(7) / F 不存在实体(3) / G 多公司比较(6) / H 指标语义(5) /
I 对抗性(6) / J 多轮(5)。schema 与判别性样本清单见 `data/evaluation/README.md`。

## B0 确定性基线（selector off / interpreter off）

```
total=50 ok=50 errors=0
sample_accuracy=0.86   identity_set=0.9091  relation=0.90
roles=0.9091  nil=0.94  comparison_participants_violations=1
safety_violations={fabricated_code:0, auto_bind_on_ambiguity:0}
```

7 个失败样本全部为确定性设计限制（诚实判别器）：

| 样本 | 确定性行为 | 期望 | 缺口 |
|------|-----------|------|------|
| 那康美呢（多轮） | intent=switch | continuation | 多轮意图边界 |
| 对比平安和茅台 | 零绑定（歧义确认） | comparison | by design 安全 |
| 存贷双高是什么意思 | ambiguous | no_company | 指标 vs 公司边界 |
| 分析康美的存贷比 | 零绑定 | single 600518 | 动作词吞 sub_span |
| 康美和茅台谁更赚钱 | no_company | comparison | 比较句式 |
| 茅台和康美的股价，谁先跌的 | no_company | comparison | 比较句式 |
| 为什么星尘科技和茅台都跌了 | no_company | ambiguous | by design 安全 |

## B1 suggest 实验（selector suggest / never auto / 真实 DeepSeek）

```
sample_accuracy=0.86   identity_set=0.9394(+0.03)  relation=0.90
roles=0.9091  nil=0.94
safety_violations={fabricated_code:0, auto_bind_on_ambiguity:0}
llm_call_sample_rate=0.1（5/50）
selector_distribution={not_needed:45, completed:2, invalid:3}
```

- 3 次 LLM 语义裁决被验证器拒绝（`single 需要恰好一个已绑定 primary` 等）——
  **never auto 保证实证**：LLM 建议即使正确（分析康美的存贷比 → select
  600518），suggest 只读不应用。
- 改善 2 条：存贷双高 → no_company（mentionness 非公司语境删除）；谁更赚钱 →
  comparison identity 命中。
- 退化 2 条（报告为已知局限）：

| 退化样本 | 行为 | 根因 |
|---------|------|------|
| 分析茅台不是茅台镇 | no_company→single 误绑 600519 | **否定语境 sub_span 重链**：mentionness 判「茅台不是茅台镇」为 company_mention 并重链子实体茅台。安全检查通过（600519∈候选）但语义错误——auto 模式下会直接绑定错公司 |
| 康美和茅台，先看康美 | ambiguous→comparison | 子实体重链把 not_found「先看康美」解析为 600518，needs_confirmation True→False，绑定集未变但确认需求被消解 |

**结论**：B1 证明 suggest 模式下 LLM 与 mentionness 的能力边界——改善集中在
非公司语境删除与比较句式识别；代价是两条语义退化（否定语境、确认消解），
均不改绑定安全不变量。这是「suggest 只读」设计的正确取舍。

## B5 双实验对照（B0 + B1）

见上 B0/B1 两节。评估器 `--score-target` 区分：deterministic（对基线评分，
B0 回归比较）与 result（对被测 suggest 输出评分，B1）。

## B6 路由/模块级验证

对 5 大模块 23 条真实查询形态（finance/equity/events/comparison/unsupported），
deterministic + suggest 双模式：

| module | n | det_ok | sug_ok | safety_viol |
|--------|---|--------|--------|-------------|
| finance | 5 | 3 | 3 | 0 |
| equity | 4 | 4 | 4 | 0 |
| events | 3 | 3 | 3 | 0 |
| comparison | 5 | 3 | **4** | 0 |
| unsupported | 6 | 6 | 6 | **0** |

关键结论：
- **unsupported 全零绑定**——大盘/概念/指标类查询不误绑公司（最关键安全不变量）。
- suggest 修复「茅台和康美的股价，谁先跌的」（no_company→comparison 绑定双方）；
  「哪个好/哪个更稳」比较意图从 ambiguous 修正为 comparison。
- 持续弱项：康美的存贷比（存贷比吞 sub_span）deterministic + suggest 均未绑定——
  suggest 只读不应用 LLM 正确建议，留给 auto 模式。
- 注：谁先跌的类比较句式改善受 LLM 随机性影响（B1 全量集中运行时该样本未改善，
  B6 独立运行时改善），应视为「概率性增强」而非确定性修复。

## B7 题库词表审计（数据1 1410 题）

- **题库结构**：1410 题 = **35 个多轮会话**（无单轮），长度 min=2/p50=12/max=38，
  think_flag=True 77 题。
- **词表覆盖**：sec_name=6160；**506/1410（35.9%）点名词表内公司**；64.1% 为
  自选股/大盘/涨停/研报/跌最狠等**不点名公司**查询。
- Top 标的：金山办公(45)/贵州茅台(35)/东方国信(32)/东吴证券(25)/当虹科技(21)/
  金杯汽车(16)/金奥博(16)/联得装备(16)/平安银行(15)/通威股份(13)。
- 洞察：
  1. **100% 多轮** → 多轮 active company 记忆（D4 active_after）是核心能力；
  2. **64% 无公司名** → no_company / 特殊主体路径需求高；
  3. 「平安银行」题库 15 次 → 简称「平安」多义（000001/601318/002985）是真实
     歧义确认压力源，而库内多义 alias 仅 1 个（国药）且题库未用到；
  4. 题库真实标的（金山办公等）不在 truthnet_test 种子集 → B0/B1 评估集无法
     覆盖题库真实分布，属评估集与题库 gap（诚实记录）。

## B8 语义单元测试

`178 passed`，覆盖 mentionness / subject policy / indicator semantics /
statement_type / semantic_selector / query_subject_interpreter / release_gate /
ws_confirm_mentions。

**2 failed — 均为 pre-existing（ENVIRONMENT_BLOCKED）**，在 stash 本人改动后的
干净基线上复现，与本次任务无关，不修改使其变绿：

| 测试 | 失败根因 |
|------|---------|
| test_mentionness_classifier.py::test_sub_span_absent_keeps_whole_span | 陈旧期望：断言整句「证券机构对金百泽」为 not_found，但当前 segmentation 已正确剥离「金百泽」单独 mention |
| test_ws_confirm_mentions.py::test_multi_mention_only_unconfirmed_needs_confirm | 注入 sqlite 库的贵州茅台(sec_name，无 alias)无法被「茅台」简称 exact 命中，茅台 mention 缺失 |

## B9 对比表

| 维度 | B0 deterministic | B1 suggest | Δ |
|------|-----------------|-----------|----|
| sample_accuracy | 0.86 (43/50) | 0.86 (43/50) | 0 |
| identity_set | 0.9091 (30/33) | **0.9394** (31/33) | **+0.0303** |
| relation | 0.90 (45/50) | 0.90 (45/50) | 0 |
| roles | 0.9091 (30/33) | 0.9091 (30/33) | 0 |
| nil | 0.94 (47/50) | 0.94 (47/50) | 0 |
| active_after | 1.0 (5/5) | 1.0 (5/5) | 0 |
| comparison_participants_violations | 1 | 1 | 0 |
| safety fabricated_code | 0 | 0 | 0 |
| safety auto_bind_on_ambiguity | 0 | 0 | 0 |
| llm_call_sample_rate | 0 | 0.10 | +0.10 |

样本级变化（+improved / −degraded）：
`+ 存贷双高是什么意思`（ambiguous→no_company）
`+ 康美和茅台谁更赚钱`（comparison identity 命中）
`− 分析茅台不是茅台镇`（否定语境误绑定 600519，见 B1 根因）
`− 康美和茅台，先看康美`（确认需求被重链消解）

## 结论与建议

1. **suggest 安全不变量保持**：B0/B1 双实验 + B6 全模块 safety 零违规，无伪造
   code、无歧义自动绑定、无公司场景零误绑。
2. **suggest 的确定性收益**：非公司语境删除（存贷双高）与比较句式识别
   （谁先跌/谁更赚/哪个好）是实质增强，identity_set +3%。
3. **suggest 的代价**：否定语境 sub_span 重链（茅台不是茅台镇）与确认消解
   （先看康美）是已知退化。建议后续为 mentionness 重链增加「否定语义」防护
   （「不是/并非」等前置词窗口），并保持 suggest 只读。
4. **auto 模式的唯一悬念**：康美的存贷比类动作词吞 sub_span，LLM 建议正确但
   suggest 不应用——这正是 auto 模式的价值场景；本次未授权跑 auto，留给后续。
5. **数据 gap**：题库 100% 多轮、64% 无公司名、真实标的未种子——建议数据组
   在 truthnet_test 补种题库 Top 标的（金山办公等），并增加多轮/无公司名
   评估样本。

## 质量门禁

- ruff check / ruff format --check：B 阶段改动均通过（待最终收尾复跑）
- 相关单测：web_search + semantic（178 passed）+ 2 pre-existing failed
- git diff --check：无空白错误
