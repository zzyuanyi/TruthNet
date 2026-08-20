"""相似指标案例检索 Provider — 任务①（Phase D 后端 #14 接口适配）。

移植 PR #39 检索算法（scripts/similar_cases.py + docs/SIMILAR_CASES_SCHEMA.md），
并适配当前主线口径与契约：

- **指标值来源**：`metric_value` 必须由调用方传入（来自规则引擎
  `RuleResult.current`），Provider 绝不内部自算目标公司指标；缺失/None →
  `empty`。
- **检索口径**：固定母公司报表（statement_type=408006000）+ 非金融企业
  （comp_type_code=1），与规则引擎一致。
- **相似度**：同行业优先（同行业样本 ≥ limit 只取同行业；否则跨行业补足，
  同行业排前）+ IQR 标准化距离（多指标 R3 用欧氏）+ 自排除 + limit=5。
- **行级定位扩展**：加载原始行时保留 `id` / `source_record_id` / `wind_code` /
  `report_period`，为每条案例构建 `sources[]`（覆盖该规则指标计算涉及的
  全部报表表，每项含参与计算的具体列名），实现「原始行回查模式」
  （evidence_ids 恒为空，sources[] 全部可直接回查）。
- **措辞约束**：只表述「指标值相似」，绝不表述为「同类造假」。

口径对齐说明（相对 PR #39 的 metric spec）：
- R7 `core_profit_ratio` 在主线 `RuleResult.current` 中为百分比（×100），
  PR #39 为比值（未×100）。为保证 `metric_value`（来自 current）与 peer
  指标同尺度、距离有意义，本 Provider 按主线口径计算（×100，percent）。
- R2 `cf_to_profit_ratio` 分母取 |净利润|（与规则引擎 `safe_div(cf, abs(np))`
  一致），PR #39 用原始净利润；正利润下二者等价。
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.api.v1.schemas.finance import (
    SimilarCase,
    SimilarCasesResult,
    SimilarCaseSource,
)
from app.domain.finance.rule_utils import yoy_growth
from app.domain.finance.statement_type import PARENT_STATEMENT_TYPE

logger = logging.getLogger(__name__)

STATEMENT_TYPE = PARENT_STATEMENT_TYPE  # 408006000 母公司报表（固定分析口径）

# ── rule_id → 指标 key（与 SIMILAR_CASES_SCHEMA.md §3 / RuleResult.current 对齐）─
METRIC_KEYS: dict[str, tuple[str, ...]] = {
    "R1": ("gap",),
    "R2": ("cf_to_profit_ratio",),
    "R3": ("cash_to_assets", "debt_to_assets"),
    "R4": ("growth_gap",),
    "R5": ("gross_margin",),
    "R6": ("oth_rcv_to_assets",),
    "R7": ("core_profit_ratio",),
}

# ── rule_id → {table: (fields...)}（构建 sources[]，覆盖指标计算涉及的全部报表）─
RULE_TABLES: dict[str, dict[str, tuple[str, ...]]] = {
    "R1": {"balance_sheet": ("acct_rcv",), "income_statement": ("oper_rev",)},
    "R2": {
        "income_statement": ("net_profit_excl_min_int_inc",),
        "cash_flow": ("net_cash_flows_oper_act",),
    },
    "R3": {
        "balance_sheet": ("monetary_cap", "st_borrow", "lt_borrow", "tot_assets"),
    },
    "R4": {"balance_sheet": ("inventories",), "income_statement": ("oper_rev",)},
    "R5": {"income_statement": ("oper_rev", "less_oper_cost")},
    "R6": {"balance_sheet": ("oth_rcv", "tot_assets")},
    "R7": {
        "income_statement": (
            "net_profit_after_ded_nr_lp",
            "net_profit_excl_min_int_inc",
        ),
    },
}

# ── 各报表需要读取的字段（当前期 + 去年同期共用）─────────────────
_TABLE_FIELDS: dict[str, tuple[str, ...]] = {
    "balance_sheet": (
        "acct_rcv",
        "oth_rcv",
        "inventories",
        "monetary_cap",
        "tot_assets",
        "st_borrow",
        "lt_borrow",
    ),
    "income_statement": (
        "oper_rev",
        "less_oper_cost",
        "net_profit_excl_min_int_inc",
        "net_profit_after_ded_nr_lp",
    ),
    "cash_flow": ("net_cash_flows_oper_act",),
}

# 需要去年同期（YoY）计算指标的规则
_YOY_RULES = {"R1", "R4"}


class SimilarCaseProvider(Protocol):
    """相似案例检索端口 — 契约见 docs/SIMILAR_CASES_SCHEMA.md。"""

    def find(
        self,
        rule_id: str,
        company_code: str,
        metric_value: dict[str, float] | None,
        industry: str | None,
        as_of: str,
    ) -> SimilarCasesResult: ...


def extract_metric_value(rule_id: str, current: dict) -> dict[str, float] | None:
    """从 RuleResult.current 提取该规则的指标值（不得内部自算）。

    任一指标缺失 / 值非数值 → 返回 None（调用方将得到 empty）。
    """
    keys = METRIC_KEYS.get(rule_id)
    if not keys:
        return None
    metric_value: dict[str, float] = {}
    for key in keys:
        item = current.get(key)
        if not isinstance(item, dict) or item.get("value") is None:
            return None
        value = item["value"]
        if isinstance(value, float) and math.isnan(value):
            return None
        metric_value[key] = float(value)
    return metric_value


def compute_similar_cases(
    provider: SimilarCaseProvider,
    *,
    rule_id: str,
    company_code: str,
    current: dict,
    industry: str | None,
    as_of: str,
    comp_type_code: int | None,
) -> SimilarCasesResult:
    """为一条触发规则计算相似案例（节点与 REST 共用）。

    - comp_type_code != 1 → not_supported（金融企业不套用非金融规则）；
    - provider 抛异常 → error（不抛出、不阻塞主链路）。
    """
    if comp_type_code != 1:
        return SimilarCasesResult(
            status="not_supported",
            reason="公司类型非一般企业（comp_type_code != 1），不适用相似指标案例检索",
        )
    metric_value = extract_metric_value(rule_id, current)
    try:
        return provider.find(rule_id, company_code, metric_value, industry, as_of)
    except Exception as exc:  # noqa: BLE001 — 失败降级，不阻塞财务风险响应
        logger.warning(
            "相似案例检索异常 rule_id=%s company=%s: %s", rule_id, company_code, exc
        )
        return SimilarCasesResult(status="error", reason=str(exc))


def _is_missing(value: float | None) -> bool:
    """None 或 NaN 视为缺失。"""
    if value is None:
        return True
    return isinstance(value, float) and math.isnan(value)


def _get_engine() -> Engine:
    """8/19 全面审查：改用公共工厂（完整 profile key + 切 profile 即 dispose）。

    原实现自带 profile key 缓存但切库不 dispose 旧 Engine，连接池滞留旧库。"""
    from app.domain.finance._engine_utils import get_engine

    return get_engine()


def _prev_year(period: str) -> str:
    """去年同期报告期（如 20260331 -> 20250331）。"""
    return str(int(period) - 10000)


@dataclass
class _RawRow:
    """一张报表的原始行（保留行级定位信息）。"""

    row_id: int | None
    source_record_id: str | None
    wind_code: str
    report_period: str
    values: dict  # field -> value（float | None）


def _to_float(value):
    """DB 数值 → float（MySQL DECIMAL 会以 decimal.Decimal 返回，直接与 float
    运算会抛 TypeError；真机实测暴露，此处统一归一化）。非数值 → None。"""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def _load_companies(engine: Engine) -> dict[str, dict]:
    """非金融企业主表（comp_type_code=1 且 is_latest=1，仅最新快照）。"""
    with engine.connect() as conn:
        rows = (
            conn.execute(
                text(
                    "SELECT wind_code, sec_name, industry_l1 "
                    "FROM companies WHERE comp_type_code = 1 AND is_latest = 1"
                )
            )
            .mappings()
            .all()
        )
    return {
        r["wind_code"]: {"sec_name": r["sec_name"], "industry_l1": r["industry_l1"]}
        for r in rows
    }


def _load_rows(
    engine: Engine, table: str, period: str, statement_type: str
) -> dict[str, _RawRow]:
    """加载某报表在指定报告期 + 口径的原始行（含行级定位字段）。"""
    fields = _TABLE_FIELDS[table]
    cols = ["id", "source_record_id", "wind_code", "report_period", *fields]
    sql = text(
        f"SELECT {', '.join(cols)} FROM {table} "
        "WHERE report_period = :per AND statement_type = :stmt"
    )
    with engine.connect() as conn:
        rows = (
            conn.execute(sql, {"per": period, "stmt": statement_type}).mappings().all()
        )
    return {
        r["wind_code"]: _RawRow(
            row_id=r["id"],
            source_record_id=r["source_record_id"],
            wind_code=r["wind_code"],
            report_period=r["report_period"],
            values={f: _to_float(r[f]) for f in fields},
        )
        for r in rows
    }


def _load_prev_values(
    engine: Engine, table: str, period: str, statement_type: str
) -> dict[str, _RawRow]:
    """加载去年同期原始行（含行级定位字段，仅 YoY 派生指标需要）。

    与 _load_rows 同结构：保留 id / source_record_id / wind_code / report_period /
    字段值，供 _build_sources 构建 period_role="prior" 的可回查来源。
    """
    return _load_rows(engine, table, period, statement_type)


def _field(cur_rows: dict, table: str, wind_code: str, field: str) -> float | None:
    row = cur_rows.get(table, {}).get(wind_code)
    return _to_float(row.values.get(field)) if row is not None else None


def _prev_field(
    prev_rows: dict, table: str, wind_code: str, field: str
) -> float | None:
    row = prev_rows.get(table, {}).get(wind_code)
    return _to_float(row.values.get(field)) if row is not None else None


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _compute_metric(
    rule_id: str, cur_rows: dict, prev_rows: dict, wind_code: str
) -> dict[str, float | None]:
    """计算某公司在该规则下的指标值（与 RuleResult.current 同尺度）。"""
    if rule_id == "R1":
        ar_yoy = yoy_growth(
            _field(cur_rows, "balance_sheet", wind_code, "acct_rcv"),
            _prev_field(prev_rows, "balance_sheet", wind_code, "acct_rcv"),
        )
        or_yoy = yoy_growth(
            _field(cur_rows, "income_statement", wind_code, "oper_rev"),
            _prev_field(prev_rows, "income_statement", wind_code, "oper_rev"),
        )
        if ar_yoy is None or or_yoy is None:
            return {"gap": None}
        return {"gap": (ar_yoy - or_yoy) * 100}
    if rule_id == "R2":
        cf = _field(cur_rows, "cash_flow", wind_code, "net_cash_flows_oper_act")
        np_ = _field(
            cur_rows, "income_statement", wind_code, "net_profit_excl_min_int_inc"
        )
        return {"cf_to_profit_ratio": _ratio(cf, abs(np_) if np_ is not None else None)}
    if rule_id == "R3":
        cash = _field(cur_rows, "balance_sheet", wind_code, "monetary_cap")
        assets = _field(cur_rows, "balance_sheet", wind_code, "tot_assets")
        st = _field(cur_rows, "balance_sheet", wind_code, "st_borrow")
        lt = _field(cur_rows, "balance_sheet", wind_code, "lt_borrow")
        if assets is None or assets <= 0:
            return {"cash_to_assets": None, "debt_to_assets": None}
        cash_to_assets = cash / assets * 100 if cash is not None else None
        debt_to_assets = ((st or 0) + (lt or 0)) / assets * 100
        return {"cash_to_assets": cash_to_assets, "debt_to_assets": debt_to_assets}
    if rule_id == "R4":
        inv_yoy = yoy_growth(
            _field(cur_rows, "balance_sheet", wind_code, "inventories"),
            _prev_field(prev_rows, "balance_sheet", wind_code, "inventories"),
        )
        or_yoy = yoy_growth(
            _field(cur_rows, "income_statement", wind_code, "oper_rev"),
            _prev_field(prev_rows, "income_statement", wind_code, "oper_rev"),
        )
        if inv_yoy is None or or_yoy is None:
            return {"growth_gap": None}
        return {"growth_gap": (inv_yoy - or_yoy) * 100}
    if rule_id == "R5":
        rev = _field(cur_rows, "income_statement", wind_code, "oper_rev")
        cost = _field(cur_rows, "income_statement", wind_code, "less_oper_cost")
        if rev is None or rev <= 0:
            return {"gross_margin": None}
        return {"gross_margin": (rev - (cost or 0)) / rev * 100}
    if rule_id == "R6":
        oth = _field(cur_rows, "balance_sheet", wind_code, "oth_rcv")
        assets = _field(cur_rows, "balance_sheet", wind_code, "tot_assets")
        if oth is None or assets is None or assets <= 0:
            return {"oth_rcv_to_assets": None}
        return {"oth_rcv_to_assets": oth / assets * 100}
    if rule_id == "R7":
        core = _field(
            cur_rows, "income_statement", wind_code, "net_profit_after_ded_nr_lp"
        )
        np_ = _field(
            cur_rows, "income_statement", wind_code, "net_profit_excl_min_int_inc"
        )
        if core is None or np_ is None or np_ == 0:
            return {"core_profit_ratio": None}
        return {"core_profit_ratio": core / abs(np_) * 100}
    return {k: None for k in METRIC_KEYS.get(rule_id, ())}


def _quantile(sorted_vals: list[float], q: float) -> float:
    """线性插值分位数（对齐 pandas quantile 默认 method='linear'）。"""
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    if n == 1:
        return sorted_vals[0]
    pos = q * (n - 1)
    lo = int(pos)
    hi = lo + 1 if lo + 1 < n else lo
    frac = pos - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def _scale(values: list[float]) -> float:
    """IQR（四分位距）标准化尺度；IQR=0 回退 std，再回退 1.0（抗离群值）。"""
    sorted_vals = sorted(values)
    iqr = _quantile(sorted_vals, 0.75) - _quantile(sorted_vals, 0.25)
    if iqr > 0:
        return iqr
    n = len(sorted_vals)
    if n >= 2:
        mean = sum(sorted_vals) / n
        var = sum((v - mean) ** 2 for v in sorted_vals) / (n - 1)
        std = var**0.5
        if std > 0:
            return std
    return 1.0


def _build_sources(
    rule_id: str, cur_rows: dict, prev_rows: dict, wind_code: str
) -> list[SimilarCaseSource]:
    """为一条案例构建 sources[]（覆盖该规则指标计算涉及的全部报表行）。

    YoY 规则（R1/R4）额外追加去年同期行（period_role="prior"）；每条 source 的
    report_period / row_id / source_record_id 均取自真实行，去年行不填当前期。
    """
    sources: list[SimilarCaseSource] = []
    for table, fields in RULE_TABLES[rule_id].items():
        row = cur_rows.get(table, {}).get(wind_code)
        if row is None:
            continue
        sources.append(
            SimilarCaseSource(
                source_table=table,
                row_id=row.row_id,
                source_record_id=row.source_record_id,
                wind_code=wind_code,
                report_period=row.report_period,
                report_statement_type=STATEMENT_TYPE,
                period_role="current",
                fields=list(fields),
            )
        )
        if rule_id in _YOY_RULES:
            prev_row = prev_rows.get(table, {}).get(wind_code)
            if prev_row is not None:
                sources.append(
                    SimilarCaseSource(
                        source_table=table,
                        row_id=prev_row.row_id,
                        source_record_id=prev_row.source_record_id,
                        wind_code=wind_code,
                        report_period=prev_row.report_period,
                        report_statement_type=STATEMENT_TYPE,
                        period_role="prior",
                        fields=list(fields),
                    )
                )
    return sources


class RealSimilarCaseProvider:
    """真实相似案例检索 Provider（Engine 可注入，便于测试）。"""

    def __init__(self, engine: Engine | None = None):
        self._engine = engine

    def _resolve_engine(self) -> Engine:
        return self._engine if self._engine is not None else _get_engine()

    def find(
        self,
        rule_id: str,
        company_code: str,
        metric_value: dict[str, float] | None,
        industry: str | None,
        as_of: str,
        limit: int = 5,
    ) -> SimilarCasesResult:
        if rule_id not in METRIC_KEYS:
            return SimilarCasesResult(
                status="not_supported",
                reason=f"规则 {rule_id} 不在 R1-R7 范围内",
            )
        # metric_value 必须由调用方传入（来自 RuleResult.current），缺失 → empty
        if not metric_value or any(
            _is_missing(metric_value.get(k)) for k in METRIC_KEYS[rule_id]
        ):
            return SimilarCasesResult(
                status="empty", reason="暂无相似案例（指标值缺失）"
            )
        try:
            return self._search(
                rule_id, company_code, metric_value, industry, as_of, limit
            )
        except Exception as exc:  # noqa: BLE001 — 捕获所有异常，不抛出
            logger.warning(
                "相似案例检索失败 rule_id=%s company=%s as_of=%s: %s",
                rule_id,
                company_code,
                as_of,
                exc,
            )
            return SimilarCasesResult(status="error", reason=str(exc))

    def _search(
        self,
        rule_id: str,
        company_code: str,
        metric_value: dict[str, float],
        industry: str | None,
        as_of: str,
        limit: int,
    ) -> SimilarCasesResult:
        engine = self._resolve_engine()
        companies = _load_companies(engine)
        tables = RULE_TABLES[rule_id]
        cur_rows = {
            table: _load_rows(engine, table, as_of, STATEMENT_TYPE) for table in tables
        }
        prev_rows: dict[str, dict] = {}
        if rule_id in _YOY_RULES:
            prev_period = _prev_year(as_of)
            prev_rows = {
                "balance_sheet": _load_prev_values(
                    engine, "balance_sheet", prev_period, STATEMENT_TYPE
                ),
                "income_statement": _load_prev_values(
                    engine, "income_statement", prev_period, STATEMENT_TYPE
                ),
            }

        # 候选公司：非金融 + 涉及表均有当前期行 + 指标完整 + 排除自身
        candidates: list[tuple[str, dict[str, float]]] = []
        for wind_code in companies:
            if wind_code == company_code:
                continue
            if any(wind_code not in cur_rows[table] for table in tables):
                continue
            metric = _compute_metric(rule_id, cur_rows, prev_rows, wind_code)
            if any(_is_missing(metric.get(k)) for k in METRIC_KEYS[rule_id]):
                continue
            candidates.append((wind_code, metric))

        if not candidates:
            return SimilarCasesResult(status="empty", reason="暂无相似案例")

        # 同行业优先
        if industry:
            same = [
                (wc, m)
                for wc, m in candidates
                if companies[wc]["industry_l1"] == industry
            ]
            cross = [
                (wc, m)
                for wc, m in candidates
                if companies[wc]["industry_l1"] != industry
            ]
        else:
            same, cross = [], candidates

        scale_pool = same if same and len(same) >= limit else candidates
        scales = {
            k: _scale([m[k] for _, m in scale_pool]) for k in METRIC_KEYS[rule_id]
        }

        def _distance(metric: dict[str, float]) -> float:
            s = 0.0
            for k in METRIC_KEYS[rule_id]:
                d = (metric[k] - metric_value[k]) / scales[k]
                s += d * d
            return s**0.5

        same_sorted = sorted(same, key=lambda item: _distance(item[1]))
        cross_sorted = sorted(cross, key=lambda item: _distance(item[1]))
        if same and len(same) >= limit:
            selected = same_sorted[:limit]
        else:
            selected = (same_sorted + cross_sorted)[:limit]

        cases = [
            SimilarCase(
                company_code=wind_code,
                company_name=companies[wind_code]["sec_name"] or "",
                industry=companies[wind_code]["industry_l1"] or "",
                period=as_of,
                metric={k: round(float(metric[k]), 2) for k in METRIC_KEYS[rule_id]},
                distance=round(float(_distance(metric)), 4),
                statement_type="observed",
                report_statement_type=STATEMENT_TYPE,
                sources=_build_sources(rule_id, cur_rows, prev_rows, wind_code),
                evidence_ids=[],  # 原始行回查模式：sources[] 可回查，不伪造 evidence
            )
            for wind_code, metric in selected
        ]
        return SimilarCasesResult(status="ok", reason="", cases=cases)
