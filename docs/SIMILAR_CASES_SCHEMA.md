# 相似历史案例检索 · 接口 Schema

> 数据组任务④ 交付物 · 给后端 #14「相似历史案例接口适配」对接用  
> 检索函数：`scripts/similar_cases.py`

---

## 1. 检索函数签名

```python
def find_similar_cases(
    rule_id: str,                              # "R1" ~ "R7"
    company_code: str,                         # "600518.SH"
    metric_value: dict[str, float] | None,     # 当前公司指标值（可空，空则内部计算）
    industry: str | None,                      # 当前公司申万一级行业（可空，空则查库）
    as_of: str = "20260331",                   # 报告期 YYYYMMDD
    limit: int = 5,
) -> list[dict]:
```

- `metric_value`：由后端在调用前，从规则引擎 `RuleResult.current` 里取对应的指标值传入（与规则引擎口径一致）。
- 若传入 `None`，函数内部会自行计算（用于数据组自测/兜底）。

---

## 2. 响应格式（后端 #14 应透传给前端 #8 的载荷）

```json
[
  {
    "company_code": "920992.BJ",
    "company_name": "中科美菱",
    "industry": "医药生物",
    "period": "20260331",
    "metric": {"gap": 13.32},
    "distance": 0.003,
    "source": "balance_sheet/income_statement/cash_flow@20260331"
  }
]
```

| 字段 | 类型 | 说明 |
|---|---|---|
| company_code | string | 相似公司 Wind 代码 |
| company_name | string | 证券简称 |
| industry | string | 申万一级行业 |
| period | string | 报告期 |
| metric | object | 该规则的核心指标值（key 见下表） |
| distance | float | 归一化距离（越小越相似，同行业 IQR 标准化） |
| source | string | 证据来源（表名 + 报告期） |

**空态**：样本不足或指标缺失时返回 `[]`，前端 #8 展示「暂无相似案例」。

---

## 3. 各规则的检索指标（与 financial_rules.yaml 对齐）

| rule_id | 规则名 | metric key | 单位 | 说明 |
|---|---|---|---|---|
| R1 | 应收–营收背离 | `gap` | pp | 应收增速 − 营收增速 |
| R2 | 现金流–利润背离 | `cf_to_profit_ratio` | ratio | 经营现金流 / 净利润 |
| R3 | 存贷双高 | `cash_to_assets` + `debt_to_assets` | percent | 货币资金占比 + 有息负债占比 |
| R4 | 存货–营收背离 | `growth_gap` | pp | 存货增速 − 营收增速 |
| R5 | 毛利率异常 | `gross_margin` | percent | 毛利率 |
| R6 | 其他应收款关联占用 | `oth_rcv_to_assets` | percent | 其他应收款 / 总资产 |
| R7 | 盈利质量 | `core_profit_ratio` | ratio | 扣非净利润 / 净利润 |

---

## 4. 相似度定义

- **口径**：母公司报表（`statement_type=408006000`）、非金融企业（`comp_type_code=1`），与规则引擎一致。
- **排序**：同行业优先（同行业样本 ≥ limit 时只取同行业；否则跨行业补足，同行业排前）。
- **距离**：单指标 = |指标差| / 行业 IQR（四分位距，抗离群值）；多指标（R3）= 各指标 IQR 标准化后欧氏距离。
- **排除**：自身不参与匹配；指标缺失的公司不参与。

---

## 5. 验证结果（康美药业 600518.SH @ 20260331）

| 规则 | 康美指标值 | 检索结果 | 状态 |
|---|---|---|---|
| R1 | gap=13.2pp | 中科美菱(13.32)、珈凯生物(14.38) 等 5 家医药生物 | ✅ |
| R2 | cf_to_profit=0.32 | 人福医药(0.23)、珈凯生物(0.48) 等 | ✅ |
| R3 | cash=2.53%, debt=0.0% | 生物谷(2.41%)、首药控股(2.06%) 等 | ✅ |
| R4 | growth_gap=-1.03pp | 鹿得医疗(-1.15)、和元生物(-1.67) 等 | ✅ |
| R5 | gross_margin=21.2% | 华北制药(20.18%)、川宁生物(22.92%) 等 | ✅ |
| R6 | oth_rcv 为空 | 返回 `[]`（暂无相似案例） | ✅ 空态 |
| R7 | 扣非利润为空 | 返回 `[]`（暂无相似案例） | ✅ 空态 |

> ⚠️ 康美药业在 20260331 的 gap=13.2pp，已不触发 R1（阈值 20pp）——因其 2018 年财务造假后已重组，当前财报已"正常化"。检索函数用的是**当前真实指标**，与规则引擎输出一致。

---

## 6. 约束（后端 #14 必须遵守）

1. **不得把相似性表述为同类造假**——只返回「指标值相似」，不输出「也是造假」。
2. 空态必须明确返回 `[]` + 「暂无相似案例」，不得伪造。
3. `metric_value` 必须来自规则引擎的 `RuleResult.current`，不得自行另算（保证口径统一）。
