# 相似历史案例检索 · 接口 Schema

> 数据组任务④ 交付物 · 给后端 #14「相似历史案例接口适配」对接用
> 权威实现：`backend/app/application/services/similar_case_provider.py`（`RealSimilarCaseProvider`，PR #42 已移植并合入 main）；数据组原型脚本 `scripts/similar_cases.py` 已由该实现取代，不再维护。

---

## 1. 检索函数签名（权威实现）

后端按 Port 协议调用（`backend/app/application/services/similar_case_provider.py`）：

```python
class SimilarCaseProvider(Protocol):
    def find(
        self,
        rule_id: str,                           # "R1" ~ "R7"
        company_code: str,                      # "600518.SH"
        metric_value: dict[str, float] | None,  # 当前公司指标值（必传，缺失 → empty）
        industry: str | None,                   # 申万一级行业（None 则查库）
        as_of: str,                             # 报告期 YYYYMMDD
    ) -> SimilarCasesResult: ...
```

业务封装入口（节点与 REST 共用，`comp_type_code != 1` 直接 `not_supported`）：

```python
def compute_similar_cases(
    provider: SimilarCaseProvider, *,
    rule_id: str, company_code: str,
    current: dict,        # 规则引擎 RuleResult.current
    industry: str | None, as_of: str,
    comp_type_code: int | None,
) -> SimilarCasesResult: ...
```

- `metric_value` 由 `extract_metric_value(rule_id, current)` 从规则引擎提取；**绝不内部自算目标公司指标**——任一指标缺失/非数值 → `None` → 结果 `empty`。
- `limit` 固定为 5（实现内常量），不在调用参数中暴露。

---

## 2. 响应格式（后端 #14 应透传给前端 #8 的载荷）

权威返回为 `SimilarCasesResult` 信封（`app/api/v1/schemas/finance.py`），
不再返回裸数组：

```json
{
  "status": "ok",
  "reason": null,
  "cases": [
    {
      "company_code": "920992.BJ",
      "company_name": "中科美菱",
      "industry": "医药生物",
      "period": "20260331",
      "metric": {"gap": 13.32},
      "distance": 0.003,
      "statement_type": "observed",
      "report_statement_type": "408006000",
      "sources": [
        {
          "table": "balance_sheet",
          "report_period": "20260331",
          "fields": ["acct_rcv"]
        }
      ],
      "evidence_ids": []
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| status | string | `ok` / `empty` / `not_supported`（comp_type_code≠1）/ `error` |
| reason | string \| null | 非 `ok` 时的人类可读原因 |
| cases | SimilarCase[] | 相似案例数组（`empty` 时为 `[]`） |
| company_code | string | 相似公司 Wind 代码 |
| company_name | string | 证券简称 |
| industry | string | 申万一级行业 |
| period | string | 报告期 |
| metric | object | 该规则的核心指标值（key 见下表） |
| distance | float | 归一化距离（越小越相似，同行业 IQR 标准化） |
| report_statement_type | string | 母公司报表口径（固定 408006000） |
| sources | SimilarCaseSource[] | 原始行回查来源（表 + 报告期 + 参与列） |

**空态**：样本不足或指标缺失时 `status=empty`、`cases=[]`，前端 #8 展示「暂无相似案例」。

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
2. 空态必须返回 `status=empty` + `cases=[]` + 「暂无相似案例」，不得伪造。
3. `metric_value` 必须来自规则引擎的 `RuleResult.current`（经 `extract_metric_value` 提取），**缺失/None → empty**；Provider 绝不内部自算目标公司指标（保证口径统一）。
4. `comp_type_code != 1`（金融企业）不套用非金融规则 → 返回 `status=not_supported`。
