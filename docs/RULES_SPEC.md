# 织网鉴真 · 财务反欺诈规则引擎规格说明书

> 版本：1.0.0 | 日期：2026-07-22 | 负责人：数据组
> 适用报表口径：母公司报表（statement_type=408006000），合并报表数据可用时切换口径
> 适用公司类型：非金融企业（comp_type_code=1），银行/保险/证券排除

---

## 0. 规则总览

| 编号 | 规则名称 | 核心信号 | 依赖表 |
|:---:|---|---|---|
| R1 | 应收–营收背离 | 应收账款增速显著高于营业收入增速 | BS + IS |
| R2 | 现金流–利润背离 | 净利润为正但经营现金流持续为负或极弱 | IS + CF |
| R3 | 存贷双高 | 货币资金与有息负债同时处于高位 | BS |
| R4 | 存货–营收背离 | 存货增速或存货周转天数显著恶化 | BS + IS |
| R5 | 毛利率/费用率异常 | 毛利率或费用率显著偏离自身历史与行业 | IS |
| R6 | 其他应收款与关联占用风险 | 其他应收款异常增长，存在关联方占用信号 | BS |
| R7 | 盈利质量与非经常性依赖 | 净利润增长与扣非利润、经营现金流不一致 | IS + CF |

---

## 1. 公共规则配置

### 1.1 数据口径

```text
statement_scope = "parent_company"   # 母公司报表（408006000）
fallback_scope  = "consolidated"     # 合并报表（408001000），仅在母公司字段缺失时用
comp_type_filter = [1]               # 仅非金融企业
```

### 1.2 增速计算约定

所有增速统一使用同比增长率（YoY），避免季节性误判：

```text
yoy_growth(t) = (value(t) - value(t-4)) / |value(t-4)|
```

- 若分母为 0 或 NULL，标记为 `insufficient_data`
- 若分母绝对值 < 1 万元（对营收/资产等大额科目），使用分母绝对值为 1 万元做下限保护，并在 quality 中标记 `denominator_small`
- 若 value(t) 和 value(t-4) 均 > 0 但 value(t-4) 极小，增速可能异常偏高，不影响触发但降低置信度
- **利润表科目（oper_rev, less_oper_cost, net_profit_excl_min_int_inc, net_profit_after_ded_nr_lp, less_selling_dist_exp, less_gerl_admin_exp, less_fin_exp, oper_profit, tot_profit）为累计值**（Q1=1-3月, Q2=1-6月, Q3=1-9月, Q4=1-12月）
- **YoY 比较仅限于同一报告期之间**（如 Q2 累计 vs 去年同期 Q2 累计），比值类指标（毛利率、费用率等）分子分母同口径，不受累计值影响
- **需要单季度值（如 R4 的周转天数年化）时，必须先用当期累计值减上期累计值还原单季值**（Q1 除外），即: `single_quarter(t) = cumulative(t) - cumulative(t-1Q)`

### 1.3 行业分位计算

- 使用申万一级行业（industry_l1）分组
- 有效同行样本数 ≥ 5 时才计算行业分位
- 样本不足 5 时：`industry_threshold` 不适用（status = `not_applicable`），仅用 absolute_threshold 判断
- 分位使用 `percentile_rank` 方法（非插值）

### 1.4 严重等级定义

```text
red     — 高风险，信号强且多期持续，建议重点关注
orange  — 中高风险，信号明确但程度或持续性不足
yellow  — 中等关注，单项指标偏离，需要结合其他规则判断
blue    — 当前未触发，仅记录
green   — 指标健康
```

### 1.5 规则版本号

```text
rule_version = "1.0.0"
rule_set_version = "finance-rules-1.0.0"
```

---

## 2. R1 · 应收–营收背离

### 2.1 规则定义

| 字段 | 值 |
|---|---|
| rule_id | R1 |
| rule_version | 1.0.0 |
| name | 应收–营收背离 |
| family | 收入确认质量 |
| description | 应收账款增速持续且显著高于营业收入增速，可能表明公司通过放宽信用政策、提前确认收入甚至虚构销售来粉饰营收。应收账款的增长应与营收增长大致同步；大幅背离意味着收入质量下降。 |
| effective_from | 2026-07-22 |
| effective_to | (null — 当前有效) |
| risk_weight | 1/7 (Phase B 等权重，Phase C 根据实证数据校准) |

### 2.2 输入字段

```text
input_fields:
  balance_sheet:
    - acct_rcv          # 应收账款（期末余额）
  income_statement:
    - oper_rev          # 营业收入（当期累计）- 累计值，详见§1.2
```

### 2.3 计算公式

```text
# Step 1: 计算同比增速
acct_rcv_yoy(t)  = (acct_rcv(t) - acct_rcv(t-4Q)) / |acct_rcv(t-4Q)|
oper_rev_yoy(t)  = (oper_rev(t) - oper_rev(t-4Q)) / |oper_rev(t-4Q)|

# Step 2: 计算背离幅度
gap(t) = acct_rcv_yoy(t) - oper_rev_yoy(t)

# Step 3: 行业分位
gap_percentile = percentile_rank(gap(t), industry_l1, gap of all peers)
```

### 2.4 阈值

| 阈值类型 | 值 | 说明 |
|---|---|---|
| absolute_threshold | gap > 20pp | 应收增速超过营收增速 20 个百分点 |
| absolute_threshold_orange | gap > 30pp | 背离扩大 |
| absolute_threshold_red | gap > 50pp | 严重背离 |
| industry_threshold | gap > P75 of peers | 高于同行业 75 分位 |
| history_window | 4 期（最近 4 个季度） | 至少 2 期背离才触发 |

### 2.5 适用条件（applicability_gate）

```text
条件 1: acct_rcv 字段不为 NULL，最近 4 期数据中至少 3 期有值
条件 2: oper_rev 字段不为 NULL，最近 4 期数据中至少 3 期有值
条件 3: 公司类型为"非金融企业"（comp_type_code = 1）
条件 4: 最近 2 期报表口径一致（同为母公司或同为合并）
条件 5: |acct_rcv(t-4Q)| >= 10,000 元（分母保护）

不满足任一条件 → status = "not_applicable" 或 "insufficient_data"
```

### 2.6 严重程度映射（severity_mapping）

```text
red:
  - gap(t) > 50pp AND acct_rcv_yoy(t) > 0 AND gap(t-1Q) > 30pp   # 连续两期严重背离
  - gap(t) > 30pp AND acct_rcv_yoy(t) > 50% AND oper_rev_yoy(t) < 0  # 应收暴增但营收下滑

orange:
  - gap(t) > 30pp AND acct_rcv_yoy(t) > 0
  - gap(t) > 20pp AND gap(t-1Q) > 20pp   # 连续两期中等背离

yellow:
  - gap(t) > 20pp
  - gap(t) > P75 AND gap(t) > 15pp       # 行业高分位 + 不低于 15pp

not_triggered:
  - gap(t) <= 20pp AND gap(t) <= P75
```

### 2.7 解释模板（explanation_template）

```text
[severity=red]
"康美药业应收账款增速（{acct_rcv_yoy}%）显著高于营业收入增速（{oper_rev_yoy}%），
差距达 {gap} 个百分点，连续 {consecutive_periods} 期背离。
应收账款/营业收入比率从 {ratio_t_minus_4Q} 升至 {ratio_t}，
收入质量存在明显下降风险。同行业中该差距处于第 {percentile} 百分位。"

[severity=orange]
"康美药业应收账款增速（{acct_rcv_yoy}%）明显高于营业收入增速（{oper_rev_yoy}%），
差距达 {gap} 个百分点，需关注收入确认节奏和回款情况。"

[severity=yellow]
"康美药业应收账款增速略高于营业收入增速，差距 {gap} 个百分点，
建议持续关注后续季度变化趋势。"

[severity=not_triggered]
"康美药业应收账款增速与营业收入增速基本匹配，未发现显著背离。"
```

### 2.8 质量标记

```text
quality:
  - statement_scope: parent_company | consolidated
  - denominator_protection_applied: true | false
  - missing_periods: 0-4
  - data_completeness: 0.0-1.0
```

---

## 3. R2 · 现金流–利润背离

### 3.1 规则定义

| 字段 | 值 |
|---|---|
| rule_id | R2 |
| rule_version | 1.0.0 |
| name | 现金流–利润背离 |
| family | 盈利质量 |
| description | 净利润持续为正但经营活动现金流持续为负或远低于净利润，表明利润缺乏现金支撑，可能存在虚增收入、应收挂账或激进确认利润的问题。健康的盈利应伴随着相应的现金流入。 |
| effective_from | 2026-07-22 |
| effective_to | (null — 当前有效) |
| risk_weight | 1/7 (Phase B 等权重，Phase C 根据实证数据校准) |

### 3.2 输入字段

```text
input_fields:
  income_statement:
    - net_profit_excl_min_int_inc   # 净利润（不含少数股东损益）
  cash_flow:
    - net_cash_flows_oper_act       # 经营活动产生的现金流量净额
```

### 3.3 计算公式

```text
# Step 1: 现金流利润比
cf_to_profit_ratio(t) = net_cash_flows_oper_act(t) / |net_profit_excl_min_int_inc(t)|

# Step 2: 连续负现金流检查
consec_neg_cf = count of consecutive quarters where (
    net_profit_excl_min_int_inc > 0
    AND net_cash_flows_oper_act < 0
), looking back 4 quarters

# Step 3: 现金流利润比均值
avg_cf_ratio = mean(cf_to_profit_ratio over last 4 quarters)
```

### 3.4 阈值

| 阈值类型 | 值 | 说明 |
|---|---|---|
| absolute_threshold | cf_to_profit_ratio < 0.3 | 不足 30% 利润有现金支撑 |
| absolute_threshold_neg | net_cash_flows_oper_act < 0 AND net_profit > 0 | 盈利但经营现金流为负 |
| industry_threshold | cf_to_profit_ratio < P25 of peers | 低于同行业 25 分位 |
| history_window | 4 期（最近 4 个季度） | 关注持续性与趋势 |

### 3.5 适用条件（applicability_gate）

```text
条件 1: net_profit_excl_min_int_inc 字段不为 NULL
条件 2: net_cash_flows_oper_act 字段不为 NULL
条件 3: 公司类型为"非金融企业"（comp_type_code = 1）
条件 4: 利润表和现金流量表的 report_period 对齐
条件 5: |net_profit_excl_min_int_inc(t)| >= 10,000 元（分母保护）
条件 6: 若 net_profit_excl_min_int_inc <= 0 且 net_cash_flows_oper_act > 0，规则仍适用但仅记录不评分
         若 net_profit_excl_min_int_inc <= 0 且 net_cash_flows_oper_act <= 0，标记"not_applicable"（公司本身亏损且现金流出，非粉饰信号）

不满足条件 1-5 → status = "insufficient_data"
```

### 3.6 严重程度映射（severity_mapping）

```text
red:
  - net_profit > 0 AND net_cash_flows_oper_act < 0
    AND consec_neg_cf >= 3   # 最近4期中3期盈利但无现金
  - net_profit > 0 AND avg_cf_ratio < 0 AND consec_neg_cf >= 2
    AND net_profit_growth > 20%   # 利润增长但现金越来越差

orange:
  - net_profit > 0 AND net_cash_flows_oper_act < 0
    AND consec_neg_cf >= 2
  - net_profit > 0 AND avg_cf_ratio < 0.3 AND avg_cf_ratio >= 0

yellow:
  - net_profit > 0 AND net_cash_flows_oper_act < 0
    AND consec_neg_cf = 1
  - net_profit > 0 AND avg_cf_ratio < 0.5 AND avg_cf_ratio >= 0.3

not_triggered:
  - avg_cf_ratio >= 0.5
```

### 3.7 解释模板（explanation_template）

```text
[severity=red]
"康美药业最近 {consec_neg_cf} 个季度净利润为正（合计 {sum_profit} 亿元），
但经营活动现金流持续为负（合计 {sum_cf} 亿元）。
近 4 季度平均现金流/净利润比率仅为 {avg_cf_ratio}，盈利缺乏现金支撑，
可能存在应收挂账或收入确认激进的问题。"

[severity=orange]
"康美药业净利润为正但经营现金流近 {consec_neg_cf} 个季度为负，
现金流/净利润比率（{avg_cf_ratio}）低于健康水平（0.5），
盈利质量需要关注。"

[severity=yellow]
"康美药业本季经营现金流为负（{cf_value} 亿元），与正利润（{profit_value} 亿元）背离，
建议持续关注下季度现金流改善情况。"
```

### 3.8 质量标记

```text
quality:
  - statement_scope: parent_company | consolidated
  - profit_sign: positive | negative
  - periods_aligned: true | false
  - denominator_protection_applied: true | false
```

---

## 4. R3 · 存贷双高

### 4.1 规则定义

| 字段 | 值 |
|---|---|
| rule_id | R3 |
| rule_version | 1.0.0 |
| name | 存贷双高 |
| family | 资产质量 |
| description | 公司同时持有大量货币资金和大量有息负债。正常经营逻辑下，企业不会在持有大量现金的同时高成本举债——这会无谓增加财务费用。存贷双高可能意味着货币资金存在虚增、受限或被关联方占用而不能自由使用。康美药业是此模式的典型案例（账面近 300 亿货币资金，同期大量借款，最终证实货币资金造假）。 |
| effective_from | 2026-07-22 |
| effective_to | (null — 当前有效) |
| risk_weight | 1/7 (Phase B 等权重，Phase C 根据实证数据校准) |

### 4.2 输入字段

```text
input_fields:
  balance_sheet:
    - monetary_cap               # 货币资金
    - st_borrow                  # 短期借款
    - lt_borrow                  # 长期借款
    - bonds_payable              # 应付债券（纳入有息负债）
    - non_cur_liab_due_within_1y # 一年内到期非流动负债（其中有息部分纳入）
    - tot_assets                 # 资产总计
  income_statement:
    - less_fin_exp               # 财务费用（用于辅助判断）
```

### 4.3 计算公式

```text
# Step 1: 有息负债总额（含应付债券 + 一年内到期的非流动负债）
interest_bearing_debt(t) = st_borrow(t) + lt_borrow(t)
                         + bonds_payable(t)
                         + non_cur_liab_due_within_1y(t)

# Step 2: 结构比率
cash_to_assets(t)  = monetary_cap(t) / tot_assets(t)
debt_to_assets(t)  = interest_bearing_debt(t) / tot_assets(t)

# Step 3: 有息负债利率估算
implied_interest_rate(t) = less_fin_exp(t) / avg(interest_bearing_debt)
  # 用于判断：货币资金收益率是否远低于借款利率？如果大量现金只产生微薄利息，说明现金可能不存在

# Step 4: 行业分位
cash_pct  = percentile_rank(cash_to_assets(t), industry_l1)
debt_pct  = percentile_rank(debt_to_assets(t), industry_l1)

# Step 5: 综合存贷双高标志
dual_high_flag = (cash_to_assets > 15% AND debt_to_assets > 20%)
```

### 4.4 阈值

| 阈值类型 | 值 | 说明 |
|---|---|---|
| absolute_threshold_cash | cash_to_assets > 15% | 货币资金占总资产比例偏高 |
| absolute_threshold_debt | debt_to_assets > 20% | 有息负债占总资产比例偏高 |
| absolute_threshold_dual | cash_to_assets > 15% AND debt_to_assets > 20% | 双高同时满足 |
| absolute_threshold_extreme | cash_to_assets > 25% AND debt_to_assets > 25% | 极端双高 |
| industry_threshold | cash_pct > P70 AND debt_pct > P70 | 两项均处行业前 30% |
| history_window | 2 期（当前及上一同期） | 判断是否持续而非偶然 |

### 4.5 适用条件（applicability_gate）

```text
条件 1: monetary_cap 字段不为 NULL
条件 2: st_borrow 或 lt_borrow 至少一个不为 NULL
条件 3: tot_assets 字段不为 NULL
条件 4: 公司类型为"非金融企业"（comp_type_code = 1）
        金融企业（银行、保险、证券）的存贷模式与实体企业不同，规则不适用
条件 5: tot_assets > 0

不满足条件 1-5 → status = "not_applicable" 或 "insufficient_data"

# 有息负债字段回退逻辑（bonds_payable / non_cur_liab_due_within_1y 不在 V12 MySQL Schema 中时）
若 bonds_payable 字段不可用（NULL 或列不存在）:
  → 有息负债公式中 bonds_payable(t) 替换为 0
  → quality.bonds_payable_included = false
  若 non_cur_liab_due_within_1y 字段不可用:
  → 有息负债公式中 non_cur_liab_due_within_1y(t) 替换为 0
  → quality.non_cur_liab_due_included = false
若两个可选字段均不可用:
  → interest_bearing_debt(t) = st_borrow(t) + lt_borrow(t)
  → 规则仍正常工作，仅债务口径偏保守（不纳入应付债券和即将到期的长期负债）
```

### 4.6 严重程度映射（severity_mapping）

```text
red:
  - cash_to_assets > 25% AND debt_to_assets > 25%
    AND implied_interest_rate > 5%
    # 极高双高 + 借款成本显著（说明大量借款在真实付息，而现金可能不存在/受限）
  - cash_to_assets > 15% AND debt_to_assets > 20%
    AND cash_to_assets(t) > cash_to_assets(t-4Q)
    AND debt_to_assets(t) > debt_to_assets(t-4Q)
    # 双高且持续扩大

orange:
  - cash_to_assets > 15% AND debt_to_assets > 20%
    AND (cash_pct > P70 OR debt_pct > P70)
  - cash_to_assets > 20% AND debt_to_assets > 15%
    AND implied_interest_rate > 4%

yellow:
  - cash_to_assets > 15% AND debt_to_assets > 20%
  - cash_to_assets > 20% AND st_borrow + lt_borrow > 0

not_triggered:
  - 不满足以上任何触发条件
```

### 4.7 解释模板（explanation_template）

```text
[severity=red]
"康美药业同时持有大量货币资金（{cash_to_assets}%，占总资产 {monetary_cap} 亿元）
和大量有息负债（{debt_to_assets}%，合计 {total_debt} 亿元）。
货币资金占总资产比处于行业第 {cash_pct} 百分位，有息负债处于第 {debt_pct} 百分位。
估算有息负债利率约 {implied_interest_rate}%，公司承担显著财务成本的同时保有大量现金，
此类'存贷双高'模式不符合商业逻辑，货币资金真实性需审慎核查。"

[severity=orange]
"康美药业货币资金占总资产 {cash_to_assets}%，同时有息负债占总资产 {debt_to_assets}%，
呈现'存贷双高'特征（均高于正常水平），建议关注货币资金受限情况及借款合理性。"

[severity=yellow]
"康美药业货币资金和有息负债占总资产比例均偏高（分别为 {cash_to_assets}% 和 {debt_to_assets}%），
建议结合业务特征判断合理性。"
```

### 4.8 质量标记

```text
quality:
  - statement_scope: parent_company | consolidated
  - bonds_payable_included: true | false     # 若应付债券字段有值则纳入有息负债
  - non_cur_liab_due_included: true | false  # 若一年内到期非流动负债字段有值则纳入
  - implied_rate_calculable: true | false
  - peer_count_dual_high: N
```

---

## 5. R4 · 存货–营收背离

### 5.1 规则定义

| 字段 | 值 |
|---|---|
| rule_id | R4 |
| rule_version | 1.0.0 |
| name | 存货–营收背离 |
| family | 资产质量 / 运营效率 |
| description | 存货增速持续显著高于营收增速，或存货周转天数大幅延长，表明公司可能存在产品滞销、存货积压，乃至通过少结转营业成本来虚增利润。存货积压占用了营运资金，且面临减值风险。 |
| effective_from | 2026-07-22 |
| effective_to | (null — 当前有效) |
| risk_weight | 1/7 (Phase B 等权重，Phase C 根据实证数据校准) |

### 5.2 输入字段

```text
input_fields:
  balance_sheet:
    - inventories         # 存货（期末余额）
  income_statement:
    - oper_rev            # 营业收入（当期累计）- 累计值，详见§1.2
    - less_oper_cost      # 营业成本（当期累计）- 累计值，详见§1.2
```

### 5.3 计算公式

```text
# Step 1: 存货与营收的同比增速背离
inventory_yoy(t) = (inventories(t) - inventories(t-4Q)) / |inventories(t-4Q)|
oper_rev_yoy(t)  = (oper_rev(t) - oper_rev(t-4Q)) / |oper_rev(t-4Q)|
growth_gap(t)    = inventory_yoy(t) - oper_rev_yoy(t)

# Step 2: 还原单季度营业成本（利润表科目为累计值，必须先拆出单季值再年化）
single_quarter_cost(t) =
  | Q1: less_oper_cost(t)
  | Q2: less_oper_cost(t) - less_oper_cost(t-1Q)
  | Q3: less_oper_cost(t) - less_oper_cost(t-1Q)
  | Q4: less_oper_cost(t) - less_oper_cost(t-1Q)

# Step 3: 存货周转天数（基于单季度成本年化）
avg_inventory(t)           = (inventories(t) + inventories(t-1Q)) / 2
annualized_cost(t)         = single_quarter_cost(t) * 4
inventory_turnover_days(t) = avg_inventory(t) / annualized_cost(t) * 365

# Step 4: 周转天数变化
turnover_change(t) = (inventory_turnover_days(t) - inventory_turnover_days(t-4Q))
                     / inventory_turnover_days(t-4Q)
```

### 5.4 阈值

| 阈值类型 | 值 | 说明 |
|---|---|---|
| absolute_threshold | growth_gap > 30pp | 存货增速超过营收增速 30 个百分点 |
| absolute_threshold_turnover | turnover_change > 50% | 存货周转天数同比延长超 50% |
| industry_threshold_gap | growth_gap > P75 of peers | 背离幅度高于行业 75 分位 |
| industry_threshold_turnover | inventory_turnover_days > P75 of peers | 周转天数高于行业 75 分位 |
| history_window | 4 期（最近 4 个季度） | 需要多期判断趋势 |

### 5.5 适用条件（applicability_gate）

```text
条件 1: inventories 字段不为 NULL，最近 4 期数据中至少 3 期有值
条件 2: oper_rev 字段不为 NULL
条件 3: less_oper_cost 字段不为 NULL（用于周转率计算）
条件 4: 公司类型为"非金融企业"（comp_type_code = 1）
条件 5: |inventories(t-4Q)| >= 10,000 元（分母保护）
条件 6: 行业为制造业或零售业等存货密集型行业时，规则权重提高
        若行业为服务业/软件/TMT 等存货天然低的行业，仅用 absolute_threshold，
        行业分位比较标记为"不适用"

不满足条件 1-5 → status = "insufficient_data"
```

### 5.6 严重程度映射（severity_mapping）

```text
red:
  - growth_gap > 50pp AND inventory_yoy > 50% AND oper_rev_yoy < 10%
    # 存货暴增但营收几乎停滞
  - turnover_change > 100% AND inventory_turnover_days > 365
    # 周转天数翻倍且超过一年

orange:
  - growth_gap > 30pp AND turnover_change > 50%
    # 增速背离 + 周转恶化
  - turnover_change > 50% AND inventory_turnover_days > P90 of peers

yellow:
  - growth_gap > 30pp
  - turnover_change > 50%

not_triggered:
  - growth_gap <= 30pp AND turnover_change <= 50%
```

### 5.7 解释模板（explanation_template）

```text
[severity=red]
"康美药业存货增速（{inventory_yoy}%）远超营业收入增速（{oper_rev_yoy}%），
差距达 {growth_gap} 个百分点。存货周转天数从 {days_t_minus_4Q} 天延长至 {days_t} 天，
延长幅度 {turnover_change}%，处于行业第 {days_percentile} 百分位。
存货大幅度积压而销售未同步增长，存在滞销或存货减值不足的风险。"

[severity=orange]
"康美药业存货增速（{inventory_yoy}%）明显快于营收增速（{oper_rev_yoy}%），
存货周转天数从 {days_t_minus_4Q} 天延长至 {days_t} 天，
需关注存货周转效率和潜在跌价风险。"

[severity=yellow]
"康美药业存货增速略快于营收增速（差距 {growth_gap} 个百分点），
建议持续关注存货周转变化。"
```

### 5.8 质量标记

```text
quality:
  - statement_scope: parent_company | consolidated
  - turnover_calculable: true | false
  - industry_inventory_intensive: true | false
  - missing_periods: 0-4
```

---

## 6. R5 · 毛利率/费用率异常

### 6.1 规则定义

| 字段 | 值 |
|---|---|
| rule_id | R5 |
| rule_version | 1.0.0 |
| name | 毛利率/费用率异常 |
| family | 利润操纵检测 |
| description | 毛利率或期间费用率在短期内发生显著变化，且与自身历史趋势和行业同行的变化方向不一致。毛利率异常提升可能意味着少结转成本、虚增收入；费用率异常下降可能是费用资本化或费用少计的粉饰手段。 |
| effective_from | 2026-07-22 |
| effective_to | (null — 当前有效) |
| risk_weight | 1/7 (Phase B 等权重，Phase C 根据实证数据校准) |

### 6.2 输入字段

```text
input_fields:
  income_statement:
    - oper_rev                  # 营业收入 - 累计值，详见§1.2
    - less_oper_cost            # 营业成本 - 累计值，详见§1.2
    - less_selling_dist_exp     # 销售费用
    - less_gerl_admin_exp       # 管理费用
    - less_fin_exp              # 财务费用
```

### 6.3 计算公式

```text
# Step 1: 核心比率计算
gross_margin(t)         = (oper_rev(t) - less_oper_cost(t)) / oper_rev(t)
selling_expense_ratio(t) = less_selling_dist_exp(t) / oper_rev(t)
admin_expense_ratio(t)   = less_gerl_admin_exp(t) / oper_rev(t)
fin_expense_ratio(t)     = less_fin_exp(t) / oper_rev(t)
total_expense_ratio(t)   = (less_selling_dist_exp(t) + less_gerl_admin_exp(t) + less_fin_exp(t))
                           / oper_rev(t)

# Step 2: 自身历史偏离
hist_avg_gm(t)  = mean(gross_margin over last 8 quarters)
gm_deviation(t) = gross_margin(t) - hist_avg_gm(t)

hist_avg_er(t)  = mean(total_expense_ratio over last 8 quarters)
er_deviation(t) = total_expense_ratio(t) - hist_avg_er(t)

# Step 3: 行业偏离
industry_median_gm = median(gross_margin of peer companies in same period)
gm_industry_deviation(t) = gross_margin(t) - industry_median_gm

# Step 4: 综合偏离幅度
combined_deviation = |gm_deviation(t)| + |er_deviation(t)|

# Step 5: 行业趋势方向判断（用于判断公司是否逆行业趋势操作）
industry_gm_change(t) = industry_median_gm(t) - industry_median_gm(t-4Q)
gm_change(t) = gross_margin(t) - gross_margin(t-4Q)
opposite_direction = (gm_change > 0 AND industry_gm_change < 0)
                  OR (gm_change < 0 AND industry_gm_change > 0)
# 当公司毛利率方向与行业整体趋势相反时，粉饰嫌疑更大
```

### 6.4 阈值

| 阈值类型 | 值 | 说明 |
|---|---|---|
| absolute_threshold_gm | gm_deviation > 10pp | 毛利率偏离自身 8 季均值超 10 个百分点 |
| absolute_threshold_er | er_deviation < -5pp | 费用率较自身均值下降超 5 个百分点 |
| absolute_threshold_combined | combined_deviation > 15pp | 综合偏离超 15 个百分点 |
| industry_threshold_gm | gm_industry_deviation > 15pp | 毛利率偏离行业中位数超 15 个百分点 |
| industry_threshold_er | selling_expense_ratio deviates from industry P25 by > 5pp | 费用率显著低于行业 |
| history_window | 8 期（最近 8 个季度） | 建立自身历史基线 |

### 6.5 适用条件（applicability_gate）

```text
条件 1: oper_rev 字段不为 NULL，近 8 期至少 6 期有值
条件 2: less_oper_cost 字段不为 NULL
条件 3: less_selling_dist_exp 或 less_gerl_admin_exp 至少一个不为 NULL
条件 4: 公司类型为"非金融企业"（comp_type_code = 1）
条件 5: oper_rev(t) > 0（当期有收入）
条件 6: 若自身历史数据不足 4 期，仅使用行业对比，置信度降低一级

不满足条件 1-5 → status = "insufficient_data"
```

### 6.6 严重程度映射（severity_mapping）

```text
red:
  - gm_deviation > 15pp AND gm_industry_deviation > 15pp
    AND opposite_direction = true
    # 自身毛利率异常提升但行业趋势却在下滑（逆行业趋势操作）
  - gm_deviation > 10pp AND er_deviation < -10pp
    # 毛利率提升的同时费用率大幅下降（利润两端同时优化，异常信号叠加）

orange:
  - gm_deviation > 10pp AND gm_industry_deviation > 10pp
  - er_deviation < -5pp AND selling_expense_ratio < P10 of peers
    # 费用率显著低于行业水平

yellow:
  - gm_deviation > 10pp
  - er_deviation < -5pp
  - combined_deviation > 15pp

not_triggered:
  - combined_deviation <= 15pp
```

### 6.7 解释模板（explanation_template）

```text
[severity=red]
"康美药业当期毛利率（{gross_margin}%）较自身 8 季度均值（{hist_avg_gm}%）提升
{gm_deviation} 个百分点，同时费用率较均值下降 {er_deviation} 个百分点。
值得注意的是，毛利率与同行业趋势（行业中位数 {industry_median_gm}%）方向相反，
存在通过少计成本或费用资本化调节利润的可能性。"

[severity=orange]
"康美药业毛利率（{gross_margin}%）明显偏离自身历史水平（+{gm_deviation}pp）
和行业水平（行业中位数 {industry_median_gm}%），
建议结合具体业务变化判断合理性。"

[severity=yellow]
"康美药业毛利率/费用率较自身历史均值有所偏离，
综合偏离幅度 {combined_deviation} 个百分点，建议持续关注。"
```

### 6.8 质量标记

```text
quality:
  - statement_scope: parent_company | consolidated
  - history_periods_available: 0-8
  - industry_median_calculable: true | false
  - peer_count: N
```

---

## 7. R6 · 其他应收款与关联占用风险

### 7.1 规则定义

| 字段 | 值 |
|---|---|
| rule_id | R6 |
| rule_version | 1.0.0 |
| name | 其他应收款与关联占用风险 |
| family | 关联交易 / 资产占用 |
| description | 其他应收款科目是财务造假的常见"垃圾桶"科目——用于隐藏关联方资金占用、虚假交易、费用挂账等。当其他应收款异常增长且占总资产比例偏高时，尤其是伴随关联方交易信号，可能表明实控人或关联方通过该科目违规占用上市公司资金。 |
| effective_from | 2026-07-22 |
| effective_to | (null — 当前有效) |
| risk_weight | 1/7 (Phase B 等权重，Phase C 根据实证数据校准) |

### 7.2 输入字段

```text
input_fields:
  balance_sheet:
    - oth_rcv            # 其他应收款（期末余额）
    - tot_assets         # 资产总计
    - acct_rcv           # 应收账款（用于对比：oth_rcv 不应显著超过 acct_rcv）
  graph:
    - 关联方关系         # 来自 Neo4j/NetworkX 的关联实体信息（Phase C 接入）
```

### 7.3 计算公式

```text
# Step 1: 规模比率
oth_rcv_to_assets(t)  = oth_rcv(t) / tot_assets(t)
oth_rcv_to_acct_rcv(t) = oth_rcv(t) / acct_rcv(t)  # 若 acct_rcv 有值

# Step 2: 增速
oth_rcv_yoy(t) = (oth_rcv(t) - oth_rcv(t-4Q)) / |oth_rcv(t-4Q)|

# Step 3: 绝对规模检查
oth_rcv_large = oth_rcv(t) > 50,000,000  # 超过 5000 万元（5×10^7）视为绝对大额
```

### 7.4 阈值

| 阈值类型 | 值 | 说明 |
|---|---|---|
| absolute_threshold_ratio | oth_rcv_to_assets > 5% | 其他应收款占总资产超 5% |
| absolute_threshold_extreme | oth_rcv_to_assets > 10% | 极度偏高 |
| absolute_threshold_growth | oth_rcv_yoy > 100% | 一年内翻倍以上增长 |
| absolute_threshold_large | oth_rcv > 50,000,000 (5000万元) | 绝对金额大 |
| industry_threshold | oth_rcv_to_assets > P90 of peers | 处于行业前 10% |
| history_window | 4 期（最近 4 个季度） | 判断是短期波动还是持续高位 |

### 7.5 适用条件（applicability_gate）

```text
条件 1: oth_rcv 字段不为 NULL
条件 2: tot_assets 字段不为 NULL
条件 3: 公司类型为"非金融企业"（comp_type_code = 1）
条件 4: tot_assets > 0

# 关联方增强条件（Phase C 启用）
条件 5(Phase C): 公司存在已知的关联方 / 一致行动人 / 同控实体
       若有关联方数据 → 规则权重 1.0
       若无关联方数据 → 规则权重 0.7（仅凭财务数据判断，置信度降低）

不满足条件 1-4 → status = "insufficient_data"
```

### 7.6 严重程度映射（severity_mapping）

```text
red:
  - oth_rcv_to_assets > 10% AND oth_rcv_yoy > 200%
    AND oth_rcv_large         # oth_rcv > 5000万元
    # 占比极高 + 增速极快 + 绝对额大
  - oth_rcv_to_assets > 10% AND oth_rcv_to_acct_rcv > 1.0
    AND 存在关联方关系信号
    # 其他应收款超过应收账款 + 有关联方（典型的占用模式）

orange:
  - oth_rcv_to_assets > 5% AND oth_rcv_yoy > 100% AND oth_rcv_large
  - oth_rcv_to_assets > 5% AND oth_rcv_to_acct_rcv > 0.5 AND 存在关联方关系信号

yellow:
  - oth_rcv_to_assets > 5% AND oth_rcv_yoy > 100%
  - oth_rcv_to_assets > 5% AND oth_rcv_large
  - oth_rcv_yoy > 200% AND oth_rcv_large

not_triggered:
  - oth_rcv_to_assets <= 5% AND oth_rcv_yoy <= 100%
```

### 7.7 解释模板（explanation_template）

```text
[severity=red]
"康美药业其他应收款（{oth_rcv} 亿元）占总资产比例高达 {oth_rcv_to_assets}%，
超过应收账款规模（{oth_rcv_to_acct_rcv} 倍），同比增速达 {oth_rcv_yoy}%。
结合股权穿透图谱，公司存在 {related_party_count} 个关联方实体，
可能存在实控人通过其他应收款占用上市公司资金的风险，
建议核查其他应收款的具体构成、交易对手方和商业实质。"

[severity=orange]
"康美药业其他应收款占总资产 {oth_rcv_to_assets}%，同比增速 {oth_rcv_yoy}%，
规模 {oth_rcv} 亿元，处于行业第 {percentile} 百分位。
建议关注其他应收款的具体构成和回收可能性。"

[severity=yellow]
"康美药业其他应收款增速较快（{oth_rcv_yoy}%）且绝对金额较大（{oth_rcv} 亿元），
建议持续关注后续季度变化。"
```

### 7.8 质量标记

```text
quality:
  - statement_scope: parent_company | consolidated
  - related_party_data_available: true | false (Phase C)
  - oth_rcv_to_acct_rcv_calculable: true | false
  - peer_count: N
```

---

## 8. R7 · 盈利质量与非经常性依赖

### 8.1 规则定义

| 字段 | 值 |
|---|---|
| rule_id | R7 |
| rule_version | 1.0.0 |
| name | 盈利质量与非经常性依赖 |
| family | 盈利可持续性 |
| description | 净利润的增长应来自主营业务经营的改善，而非非经常性损益（如资产处置、政府补贴、债务重组收益等）。当净利润增长显著高于扣非净利润增长、经营现金流增长和营收增长时，表明利润质量差，可能存在依赖一次性收益粉饰报表的情况。 |
| effective_from | 2026-07-22 |
| effective_to | (null — 当前有效) |
| risk_weight | 1/7 (Phase B 等权重，Phase C 根据实证数据校准) |

### 8.2 输入字段

```text
input_fields:
  income_statement:
    - net_profit_excl_min_int_inc   # 净利润（不含少数股东）- 累计值，详见§1.2
    - net_profit_after_ded_nr_lp    # 扣除非经常性损益后净利润 - 累计值，详见§1.2
    - oper_rev                      # 营业收入 - 累计值，详见§1.2
    - oper_profit                   # 营业利润 - 累计值，详见§1.2
    - tot_profit                    # 利润总额 - 累计值，详见§1.2
  cash_flow:
    - net_cash_flows_oper_act       # 经营活动现金流量净额 - 累计值，详见§1.2
```

### 8.3 计算公式

```text
# Step 1: 核心利润比率（扣非利润占净利润比重）
core_profit_ratio(t) = net_profit_after_ded_nr_lp(t) / net_profit_excl_min_int_inc(t)
  # 若 < 0.5，说明过半利润来自非经常性项目

# Step 2: 非经常性损益估算
non_recurring(t) = net_profit_excl_min_int_inc(t) - net_profit_after_ded_nr_lp(t)
non_recurring_ratio(t) = non_recurring(t) / |net_profit_excl_min_int_inc(t)|

# Step 3: 多维增速对比
net_profit_yoy(t)      = (net_profit_excl_min_int_inc(t) - net_profit_excl_min_int_inc(t-4Q))
                         / |net_profit_excl_min_int_inc(t-4Q)|
core_profit_yoy(t)     = (net_profit_after_ded_nr_lp(t) - net_profit_after_ded_nr_lp(t-4Q))
                         / |net_profit_after_ded_nr_lp(t-4Q)|
oper_rev_yoy(t)        = (oper_rev(t) - oper_rev(t-4Q)) / |oper_rev(t-4Q)|
oper_cf_yoy(t)         = (net_cash_flows_oper_act(t) - net_cash_flows_oper_act(t-4Q))
                         / |net_cash_flows_oper_act(t-4Q)|

# Step 4: 盈利质量背离度
quality_divergence = (net_profit_yoy - core_profit_yoy)   # 净利润增速 vs 扣非利润增速
revenue_divergence = (net_profit_yoy - oper_rev_yoy)       # 净利润增速 vs 营收增速
cash_divergence    = (net_profit_yoy - oper_cf_yoy)        # 净利润增速 vs 现金流增速

# Step 5: 营业外收支占比
non_operating_ratio = (tot_profit - oper_profit) / |tot_profit|
  # 衡量利润总额中非营业活动的贡献度

	# Step 6: 连续依赖非经常性损益的期数
	consec_periods = count of consecutive quarters (looking back from t)
	                 where core_profit_ratio < 0.5
	  # 用于判断公司是否持续依赖非经常性收益维持盈利
```

### 8.4 阈值

| 阈值类型 | 值 | 说明 |
|---|---|---|
| absolute_threshold_core_ratio | core_profit_ratio < 0.5 | 过半利润来自非经常性 |
| absolute_threshold_core_ratio_severe | core_profit_ratio < 0.3 | 超 7 成利润来自非经常性 |
| absolute_threshold_quality_div | quality_divergence > 30pp | 净利润增速远超扣非利润增速 |
| absolute_threshold_revenue_div | revenue_divergence > 20pp | 净利润增速远超营收增速 |
| absolute_threshold_cash_div | cash_divergence > 30pp | 净利润增速远超经营现金流增速 |
| absolute_threshold_non_operating | non_operating_ratio > 30% | 营业外收支占比过高 |
| industry_threshold | core_profit_ratio < P25 of peers | 扣非占比低于行业 25 分位 |
| history_window | 4 期（最近 4 个季度） | 关注持续性 |

### 8.5 适用条件（applicability_gate）

```text
条件 1: net_profit_excl_min_int_inc 字段不为 NULL
条件 2: net_profit_after_ded_nr_lp 字段不为 NULL
        → 若此字段为 NULL，标记 status = "not_applicable"，原因 "扣非净利润字段不可用"
        → V12 数据约束：扣非字段覆盖率可能不足，此时 R7 整体标记为不适用
条件 3: 公司类型为"非金融企业"（comp_type_code = 1）
条件 4: |net_profit_excl_min_int_inc(t)| >= 10,000 元（分母保护）
条件 5: net_profit_excl_min_int_inc(t) > 0（公司盈利时才判断盈利质量）

# 降级处理
若 net_profit_after_ded_nr_lp 不可用：
  → 仅使用 revenue_divergence + cash_divergence 判断，规则名称改为
    "盈利质量（简化版）"，置信度降低一级，严重等级上限为 orange
```

### 8.6 严重程度映射（severity_mapping）

```text
red:
  - core_profit_ratio < 0.3
    AND (quality_divergence > 30pp OR revenue_divergence > 20pp)
    # 扣非利润极少支持 + 增速严重背离
  - core_profit_ratio < 0.5 AND consec_periods >= 2
    AND cash_divergence > 30pp
    # 持续依赖非经常性 + 现金流不支撑

orange:
  - core_profit_ratio < 0.5 AND quality_divergence > 30pp
  - core_profit_ratio < 0.5 AND revenue_divergence > 20pp
  - core_profit_ratio < 0.3  # 单期极依赖非经常性
  - non_operating_ratio > 50%

yellow:
  - core_profit_ratio < 0.5
  - quality_divergence > 30pp
  - revenue_divergence > 20pp
  - non_operating_ratio > 30%

not_triggered:
  - core_profit_ratio >= 0.5
```

### 8.7 解释模板（explanation_template）

```text
[severity=red]
"康美药业当期净利润 {net_profit} 亿元中，扣除非经常性损益后仅 {core_profit} 亿元，
扣非利润占净利润比仅为 {core_profit_ratio}%，连续 {consec_periods} 期低于 50%。
净利润增速（{net_profit_yoy}%）远超扣非利润增速（{core_profit_yoy}%）
和经营现金流增速（{oper_cf_yoy}%），盈利对非经常性收益存在严重依赖，
主营业务盈利能力需要审视。"

[severity=orange]
"康美药业扣非净利润占净利润比（{core_profit_ratio}%）偏低，
净利润增速（{net_profit_yoy}%）与扣非利润增速（{core_profit_yoy}%）差距
{quality_divergence} 个百分点，盈利质量有待改善。"

[severity=yellow]
"康美药业当期非经常性损益占净利润比重偏高（{non_recurring_ratio}%），
建议关注盈利的可持续性。"
```

### 8.8 质量标记

```text
quality:
  - statement_scope: parent_company | consolidated
  - core_profit_available: true | false
  - simplified_mode: true | false   # 扣非字段不可用时的简化版
  - denominator_protection_applied: true | false
  - peer_count: N
```

---

## 9. 规则执行顺序与交叉验证

### 9.1 单规则执行流程

```text
1. 读取公司财务数据（最近 history_window 期）
2. 检查 applicability_gate → 判定状态
3. 若适用，执行公式计算
4. 应用 absolute_threshold + industry_threshold
5. 匹配 severity_mapping
6. 记录 evidence_ref（来源字段、报告期、具体值）
7. 生成 claim（一次性，一对一映射）
```

### 9.2 规则间交叉验证（CrossValidate 阶段）

交叉验证节点接收 7 条规则的输出，按以下结构化规则组合判断。每条组合返回 `cross_signal_id`、`signal_strength`、`action` 和 `new_claim_text` 四个字段，供 GenerateAnswer 节点使用。

```text
# 模式 1: 收入虚增型
trigger: R1.triggered AND R2.triggered
cross_signal_id: "revenue_fraud_pattern"
signal_strength: "high"          # R1+R2 独立命中，相互印证
action: "elevate_confidence"     # 两个相关规则同时命中 → 置信度提升 1 级
new_claim_text: "应收账款异常增长（R1触发）且经营现金流无法支撑利润（R2触发），收入质量存在系统性疑虑。"
related_mode: "模式1" (对应附录B)

# 模式 2: 渠道压货 / 虚增资产型
trigger: R1.triggered AND R4.triggered
cross_signal_id: "channel_stuffing_pattern"
signal_strength: "high"
action: "elevate_confidence"
new_claim_text: "应收账款（R1触发）与存货（R4触发）同时异常增长而营收增速跟不上，存在渠道压货或虚增资产的嫌疑。"
related_mode: "模式4" (对应附录B)

# 模式 3: 利润调节型
trigger: R2.triggered AND R7.triggered
cross_signal_id: "profit_manipulation_pattern"
signal_strength: "high"
action: "elevate_confidence"
new_claim_text: "经营现金流对利润支撑弱（R2触发），且盈利高度依赖非经常性损益（R7触发），利润质量存疑。"
related_mode: "模式3" (对应附录B)

# 模式 4: 资金占用型
trigger: R3.triggered AND R6.triggered
cross_signal_id: "fund_occupation_pattern"
signal_strength: "high"
action: "elevate_confidence"
new_claim_text: "公司呈现存贷双高特征（R3触发），同时其他应收款异常（R6触发），存在关联方资金占用的嫌疑。"
related_mode: "模式2" (对应附录B)

# 模式 5: 虚增收入与毛利率型
trigger: R5.triggered AND R1.triggered
cross_signal_id: "aggressive_revenue_recognition_pattern"
signal_strength: "medium"        # 毛利率异常可能由多种原因导致，与应收组合才增强信号
action: "elevate_confidence"
new_claim_text: "毛利率异常提升（R5触发）的同时应收账款增速显著高于营收（R1触发），存在通过放宽信用政策同时虚增收入和毛利率的嫌疑。"

# 通用规则
若 3+ 条规则同时触发:
  cross_signal_id: "multi_signal_overlap"
  signal_strength: "high"
  action: "elevate_confidence"
  new_claim_text: "共 {N} 条反欺诈规则同时触发，信号密度高，建议综合审视公司财务健康状况。"

若 0 条规则触发:
  cross_signal_id: none
  signal_strength: none
  action: none
  new_claim_text: ""（不生成交叉验证 claim）

# Phase B 实现约定
- CrossValidate 节点直接读取 AgentState.module_results 中已完成的规则结果
- 使用对象引用（规则结果已包含 severity、claim_ids、evidence_ids）
- 不得重新执行规则计算
- 输出写入 AgentState.claims，每条 cross_signal 对应一个 Claim
```

---

## 10. 规则版本管理与维护

### 10.1 版本号规则

```text
主版本号: 规则公式、字段或阈值发生实质性变更时递增
次版本号: 阈值微调、措辞修改等非实质性变更时递增
修订号:   文档修复、注释补充时递增

当前版本: 1.0.0
```

### 10.2 规则变更记录

| 日期 | 版本 | 变更内容 |
|---|---|---|
| 2026-07-22 | 1.0.0 | 初始版本，7 条规则完整定义 |

### 10.3 配置化管理目标

```text
Phase C 阶段目标: 将规则定义从文档迁移到 rule_definitions 数据库表，
使阈值、严重程度、历史窗口等参数可通过 API 动态配置和版本化。
本文档在代码化后转为规则的"人类可读参考"。
```

---

## 11. 错误与边界处理矩阵

| 场景 | 处理方式 |
|---|---|
| 字段为 NULL | 该字段不参与计算，若关键字段缺失 → `insufficient_data` |
| 分母为 0 | 应用分母下限保护（1 万元），标记 `denominator_small` |
| 历史数据不足 | 降低 `history_window`，置信度降级，标记 `short_history` |
| 行业样本 < 5 | 跳过行业分位比较，仅用 absolute_threshold |
| 金融企业 | `comp_type_code != 1` → 规则整体 `not_applicable` |
| 母公司字段缺失但合并表有值 | 使用合并表 fallback，标记 `statement_scope=consolidated`，置信度降级 |
| 单季度数据异常 | 用 `z-score` 或 `IQR` 检测离群值，标记 `outlier_detected` |
| 增速为负但背离方向相反 | 正常记录，不影响严重程度判定方向（如应收和营收同时大幅下滑不触发 R1） |

---

## 附录 A. 字段-规则依赖矩阵

| 字段 | R1 | R2 | R3 | R4 | R5 | R6 | R7 |
|---|---|---|---|---|---|---|---|
| acct_rcv (应收账款) | ● | | | | | ○ | |
| oper_rev (营业收入) | ● | | | ● | ● | | ● |
| net_profit_excl_min_int_inc (净利润) | | ● | | | | | ● |
| net_cash_flows_oper_act (经营现金流) | | ● | | | | | ● |
| monetary_cap (货币资金) | | | ● | | | | |
| st_borrow (短期借款) | | | ● | | | | |
| lt_borrow (长期借款) | | | ● | | | | |
| tot_assets (资产总计) | | | ● | | | ● | |
| less_fin_exp (财务费用) | | | ○ | | ● | | |
| inventories (存货) | | | | ● | | | |
| bonds_payable (应付债券) | | | ● | | | | |
| non_cur_liab_due_within_1y (一年内到期非流动负债) | | | ● | | | | |
| less_oper_cost (营业成本) | | | | ● | ● | | |
| less_selling_dist_exp (销售费用) | | | | | ● | | |
| less_gerl_admin_exp (管理费用) | | | | | ● | | |
| oth_rcv (其他应收款) | | | | | | ● | |
| net_profit_after_ded_nr_lp (扣非净利润) | | | | | | | ● |
| oper_profit (营业利润) | | | | | | | ○ |
| tot_profit (利润总额) | | | | | | | ○ |

> ● 核心依赖 · ○ 辅助依赖

---

## 附录 B. 造假模式匹配表（Phase C 扩展）

```text
模式 1: 收入虚增型
  触发组合: R1 + R2 + (R4)
  典型特征: 应收飙升 + 现金流弱 + 存货可能也异常
  置信条件: 3 条同时触发 → high | 2 条 → medium

模式 2: 资金占用型
  触发组合: R3 + R6
  典型特征: 存贷双高 + 其他应收款大
  置信条件: 2 条同时触发 + 关联方信号 → high

模式 3: 利润调节型
  触发组合: R5 + R7
  典型特征: 毛利率/费用率异常 + 依赖非经常性
  置信条件: 2 条同时触发 → high

模式 4: 资产虚增型
  触发组合: R1 + R4 + R2
  典型特征: 应收 + 存货同时扩张 + 现金流不支撑
  置信条件: 3 条同时触发 → high | 2 条 → medium

模式 5: 综合粉饰型
  触发组合: 5 条及以上规则同时触发
  典型特征: 多条信号叠加，系统性造假嫌疑
  置信条件: ≥5 条 → high | 3-4 条 → medium
```
