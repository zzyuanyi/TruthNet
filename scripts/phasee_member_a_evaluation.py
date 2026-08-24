#!/usr/bin/env python3
"""Phase E 数据组成员 A：工具路由统计与数值 Claim 独立盲评。

本脚本只允许连接隔离的 MySQL 测试库，并在启动时校验官方 77 题 sidecar 与
clean.xlsx 的来源行完全一致。路由评测和数值盲评均走完整 Agent 图（含实体解析、
计划、模块执行与回答生成），并在 finally 中清理评测会话；数值盲评为了隔离
实体识别误差，按 wind_code 预绑定公司后检查最终 Agent 输出的 Claim/Evidence。

输出：
  - data/reports/phasee_member_a_evaluation.json（逐条原始记录）
  - docs/reports/路由命中统计.md
  - docs/reports/盲评报告.md

示例（环境变量中的密码不要写进命令历史或仓库文件）：
  python scripts/phasee_member_a_evaluation.py --blind-limit 25
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(REPO_ROOT) not in sys.path:
    # 仓库根目录必须排在 backend 前，避免 backend/tests 遮蔽 tests/evaluation。
    sys.path.insert(0, str(REPO_ROOT))

CORE_MODULES = ("finance", "equity", "events")
RULE_ORDER = ("R1", "R2", "R3", "R4", "R5", "R6", "R7")
OFFICIAL_SIDECAR = REPO_ROOT / "tests/evaluation/official_questions_v1.jsonl"
OFFICIAL_CLEAN_XLSX = REPO_ROOT / "data/raw/1/clean.xlsx"

# 日期和股票代码没有以下单位，因此不会被误当作待审的业务数值陈述。
NUMERIC_FACT_RE = re.compile(
    r"(?<![\d.])[+-]?\d+(?:\.\d+)?\s*"
    r"(?:%|pp|亿元|万元|元|倍|个季度|个报告期|季度|期)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RouteCase:
    case_id: str
    category: str
    question: str
    expected_modules: tuple[str, ...]
    company_code: str = "600518.SH"


ROUTE_CASES = (
    RouteCase("F1", "财务", "分析康美药业股份有限公司的财务状况", ("finance",)),
    RouteCase(
        "F2", "财务", "康美药业股份有限公司的营业收入和净利润怎么样？", ("finance",)
    ),
    RouteCase("F3", "财务", "康美药业股份有限公司的毛利率是否异常？", ("finance",)),
    RouteCase(
        "F4", "财务", "康美药业股份有限公司经营现金流与净利润是否背离？", ("finance",)
    ),
    RouteCase("F5", "财务", "康美药业股份有限公司是否存在存贷双高？", ("finance",)),
    RouteCase("E1", "股权", "康美药业股份有限公司的前十大股东是谁？", ("equity",)),
    RouteCase(
        "E2", "股权", "康美药业股份有限公司控股股东是谁，持股比例多少？", ("equity",)
    ),
    RouteCase("E3", "股权", "康美药业股份有限公司的股权结构如何？", ("equity",)),
    RouteCase("E4", "股权", "康美药业股份有限公司的实际控制人是谁？", ("equity",)),
    RouteCase("E5", "股权", "请穿透分析康美药业股份有限公司的股权关系。", ("equity",)),
    RouteCase("V1", "公告/事件", "康美药业股份有限公司最近有哪些公告？", ("events",)),
    RouteCase(
        "V2", "公告/事件", "康美药业股份有限公司最近有什么监管处罚？", ("events",)
    ),
    RouteCase(
        "V3", "公告/事件", "康美药业股份有限公司最近发生了哪些重大事件？", ("events",)
    ),
    RouteCase("V4", "公告/事件", "康美药业股份有限公司的舆情风险如何？", ("events",)),
    RouteCase(
        "V5", "公告/事件", "康美药业股份有限公司有哪些负面公告和风险事件？", ("events",)
    ),
    RouteCase(
        "C1",
        "三模块综合",
        "康美药业股份有限公司有造假风险吗？",
        ("finance", "equity", "events"),
    ),
    RouteCase(
        "C2",
        "三模块综合",
        "综合分析康美药业股份有限公司的财务、股权和公告风险。",
        ("finance", "equity", "events"),
    ),
    RouteCase(
        "C3",
        "三模块综合",
        "康美药业股份有限公司是否存在财务异常、股权风险或负面事件？",
        ("finance", "equity", "events"),
    ),
    RouteCase(
        "C4",
        "三模块综合",
        "全面评估康美药业股份有限公司的经营、股东和舆情风险。",
        ("finance", "equity", "events"),
    ),
    RouteCase(
        "C5",
        "三模块综合",
        "从财务、股权、公告三个维度分析康美药业股份有限公司。",
        ("finance", "equity", "events"),
    ),
)

# 先放能覆盖 R1-R6 的公司；按规则分层轮询后截取 20-30 条，而不是只挑
# 某一家或某一条规则。所有公司仍以运行时真实触发结果为准。
BLIND_COMPANY_CODES = (
    "600476.SH",
    "688443.SH",
    "920680.BJ",
    "688266.SH",
    "000860.SZ",
    "002432.SZ",
    "603886.SH",
    "002482.SZ",
    "603565.SH",
    "920149.BJ",
    "600466.SH",
    "600656.SH",
    "000918.SZ",
    "002217.SZ",
    "600532.SH",
    "000615.SZ",
    "002157.SZ",
    "000078.SZ",
    "001330.SZ",
    "600247.SH",
    "000979.SZ",
    "000042.SZ",
    "002659.SZ",
    "002594.SZ",
    "300729.SZ",
    "600373.SH",
    "601615.SH",
    "002857.SZ",
    "688381.SH",
    "601003.SH",
    "600068.SH",
    "600271.SH",
)


def _model_dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def extract_numeric_mentions(text: str) -> list[str]:
    """提取业务数值，排除无单位的日期、股票代码和规则编号。"""
    return [m.group(0).strip() for m in NUMERIC_FACT_RE.finditer(text or "")]


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value or "").lower()


def detect_plausibility_flags(text: str) -> list[str]:
    """只标记需人工复核的极端/自相矛盾表述，不直接判定事实错误。"""
    flags: list[str] = []
    if re.search(r"近\s*0\s*个季度为负", text or ""):
        flags.append("触发风险 Claim 却写成“近 0 个季度为负”，需核对模板分支")
    for raw in re.findall(r"增速较快[（(]\s*([+-]?\d+(?:\.\d+)?)\s*%[）)]", text or ""):
        if float(raw) < 0:
            flags.append(f"负增长 {raw}% 被描述为“增速较快”，文案与数值方向矛盾")
    for raw in re.findall(r"([+-]?\d+(?:\.\d+)?)\s*pp", text or "", re.I):
        if abs(float(raw)) > 100:
            flags.append(f"百分点绝对值 {raw}pp 超过 100，需核对单位/缩放")
    if "现金流/利润比" in (text or ""):
        for raw in re.findall(
            r"现金流/利润比(?:仅|[（(])\s*([+-]?\d+(?:\.\d+)?)", text
        ):
            if abs(float(raw)) > 100:
                flags.append(f"现金流/利润比 {raw} 为极端值，需核对分母与单位")
    return flags


def _evidence_values(
    evidence_items: list[dict[str, Any]],
) -> dict[str, dict[str, float]]:
    values: dict[str, dict[str, float]] = defaultdict(dict)
    for item in evidence_items:
        try:
            value = float(str(item.get("value") or "").strip())
        except ValueError:
            continue
        field = str(item.get("field_path") or "")
        period = str(item.get("period") or "")
        if field and period:
            values[field][period] = value
    return dict(values)


def _claim_period(text: str) -> str:
    match = re.search(r"数据期[：:]\s*(\d{4})-(\d{2})-(\d{2})", text)
    return "".join(match.groups()) if match else ""


def _matches_rounded(actual: float, displayed: float, decimals: int = 1) -> bool:
    tolerance = 0.5 * 10 ** (-decimals) + 1e-9
    return abs(actual - displayed) <= tolerance


def _extract_number(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text)
    return float(match.group(1)) if match else None


def verify_claim_arithmetic(
    claim: dict[str, Any], evidence_items: list[dict[str, Any]]
) -> tuple[bool, str]:
    """按 R1-R7 公式从 Evidence 原值重算并核对 Claim 展示数值。"""
    text = str(claim.get("text") or "")
    rule_id = str(claim.get("rule_id") or "")
    values = _evidence_values(evidence_items)
    stated_period = _claim_period(text)
    checks: list[tuple[str, float, float, int]] = []

    def aligned_period(fields: set[str], *, prior_year: bool = False) -> str | None:
        candidates = set.intersection(*(set(values.get(field, {})) for field in fields))
        if prior_year:
            candidates = {
                period
                for period in candidates
                if len(period) == 8
                and f"{int(period[:4]) - 1}{period[4:]}" in candidates
            }
        if stated_period in candidates:
            return stated_period
        return max(candidates) if candidates else None

    if rule_id == "R1":
        current = aligned_period({"acct_rcv", "oper_rev"}, prior_year=True)
        if current:
            prior = f"{int(current[:4]) - 1}{current[4:]}"
            ar = (values["acct_rcv"][current] / values["acct_rcv"][prior] - 1) * 100
            rev = (values["oper_rev"][current] / values["oper_rev"][prior] - 1) * 100
            shown = _extract_number(text, r"应收账款增速[（(]([+-]?\d+(?:\.\d+)?)%")
            if shown is not None:
                checks.append(("应收账款增速", ar, shown, 1))
            shown = _extract_number(text, r"营业收入增速[（(]([+-]?\d+(?:\.\d+)?)%")
            if shown is not None:
                checks.append(("营业收入增速", rev, shown, 1))
            shown = _extract_number(
                text, r"增速差(?:达|\s)(?:约\s*)?([+-]?\d+(?:\.\d+)?)%"
            )
            if shown is not None:
                checks.append(("增速差", ar - rev, shown, 1))
    elif rule_id == "R2":
        profit = values.get("net_profit_excl_min_int_inc", values.get("net_profit", {}))
        cash = values.get("net_cash_flows_oper_act", values.get("oper", {}))
        periods = sorted(set(profit) & set(cash))
        current = (
            stated_period
            if stated_period in periods
            else (periods[-1] if periods else "")
        )
        recent = [period for period in periods if period <= current][-4:]
        ratios = [cash[p] / abs(profit[p]) for p in recent if profit[p] != 0]
        shown = _extract_number(
            text, r"现金流/利润比(?:仅|[（(])\s*([+-]?\d+(?:\.\d+)?)"
        )
        if shown is not None and ratios:
            checks.append(("平均现金流/利润比", sum(ratios) / len(ratios), shown, 2))
        shown_quarters = _extract_number(text, r"(?:最近|近)\s*(\d+)\s*个季度")
        if shown_quarters is not None:
            from app.domain.finance.period import next_quarter

            longest = current_run = 0
            previous_period = ""
            for period in recent:
                if previous_period and next_quarter(previous_period) != period:
                    current_run = 0
                if profit[period] > 0 and cash[period] < 0:
                    current_run += 1
                    longest = max(longest, current_run)
                else:
                    current_run = 0
                previous_period = period
            checks.append(("连续负现金流季度", float(longest), shown_quarters, 0))
    elif rule_id == "R3":
        current = aligned_period({"monetary_cap", "tot_assets"})
        if current:
            assets = values["tot_assets"][current]
            debt = sum(
                values.get(field, {}).get(current, 0.0)
                for field in ("st_borrow", "lt_borrow")
            )
            shown = _extract_number(
                text, r"货币资金(?:占总资产\s*|[（(])([+-]?\d+(?:\.\d+)?)%"
            )
            if shown is not None:
                checks.append(
                    (
                        "货币资金占比",
                        values["monetary_cap"][current] / assets * 100,
                        shown,
                        1,
                    )
                )
            shown = _extract_number(
                text, r"有息负债(?:占\s*|[（(])([+-]?\d+(?:\.\d+)?)%"
            )
            if shown is not None:
                checks.append(("有息负债占比", debt / assets * 100, shown, 1))
    elif rule_id == "R4":
        current = aligned_period({"inventories", "oper_rev"}, prior_year=True)
        if current:
            prior = f"{int(current[:4]) - 1}{current[4:]}"
            inv = (
                values["inventories"][current] / values["inventories"][prior] - 1
            ) * 100
            rev = (values["oper_rev"][current] / values["oper_rev"][prior] - 1) * 100
            shown = _extract_number(text, r"存货增速[（(]([+-]?\d+(?:\.\d+)?)%")
            if shown is not None:
                checks.append(("存货增速", inv, shown, 1))
            shown = _extract_number(text, r"营业收入增速[（(]([+-]?\d+(?:\.\d+)?)%")
            if shown is not None:
                checks.append(("营业收入增速", rev, shown, 1))
            shown = _extract_number(text, r"增速差(?:达|\s)([+-]?\d+(?:\.\d+)?)%")
            if shown is not None:
                checks.append(("增速差", inv - rev, shown, 1))
    elif rule_id == "R5":
        periods = sorted(values.get("oper_rev", {}))
        margins: dict[str, float] = {}
        expense_rates: dict[str, float] = {}
        for period in periods:
            rev = values["oper_rev"][period]
            cost = values.get("less_oper_cost", {}).get(period)
            if rev <= 0:
                continue
            if cost is not None:
                margins[period] = (rev - cost) / rev * 100
            expenses = [
                values.get(field, {}).get(period)
                for field in (
                    "less_selling_dist_exp",
                    "less_gerl_admin_exp",
                    "less_fin_exp",
                )
            ]
            if all(value is not None for value in expenses):
                expense_rates[period] = sum(expenses) / rev * 100
        current = (
            max(margins.keys() | expense_rates.keys())
            if margins or expense_rates
            else ""
        )
        if current in margins:
            history = [value for period, value in margins.items() if period != current]
            gm_deviation = margins[current] - sum(history) / len(history)
            shown = _extract_number(
                text,
                r"毛利率(?:较历史均值偏离\s*|[（(]\+?)([+-]?\d+(?:\.\d+)?)pp",
            )
            if shown is not None:
                checks.append(("毛利率偏离", gm_deviation, shown, 1))
        if current in expense_rates:
            history = [
                value for period, value in expense_rates.items() if period != current
            ]
            er_deviation = expense_rates[current] - sum(history) / len(history)
            shown = _extract_number(
                text, r"费用率(?:较历史均值)?下降\s*([+-]?\d+(?:\.\d+)?)pp"
            )
            if shown is not None:
                checks.append(("费用率下降", abs(er_deviation), shown, 1))
    elif rule_id == "R6":
        current = aligned_period({"oth_rcv", "tot_assets"})
        if current:
            ratio = values["oth_rcv"][current] / values["tot_assets"][current] * 100
            shown = _extract_number(text, r"占总资产\s*([+-]?\d+(?:\.\d+)?)%")
            if shown is not None:
                checks.append(("其他应收款占比", ratio, shown, 1))
            prior = f"{int(current[:4]) - 1}{current[4:]}"
            if prior in values["oth_rcv"]:
                yoy = (values["oth_rcv"][current] / values["oth_rcv"][prior] - 1) * 100
                shown = _extract_number(
                    text, r"(?:同比增速|增速较快[（(])\s*([+-]?\d+(?:\.\d+)?)%"
                )
                if shown is not None:
                    checks.append(("其他应收款同比", yoy, shown, 1))
                shown = _extract_number(text, r"同比下降\s*([+-]?\d+(?:\.\d+)?)%")
                if shown is not None:
                    checks.append(("其他应收款同比下降", abs(yoy), shown, 1))
            shown = _extract_number(text, r"金额\s*([+-]?\d+(?:\.\d+)?)\s*亿元")
            if shown is not None:
                checks.append(
                    ("其他应收款金额", values["oth_rcv"][current] / 1e8, shown, 1)
                )
    else:
        return False, f"{rule_id or 'unknown'} 尚未实现公式级复算"

    if not checks:
        return False, "Claim 中未识别到可与规则公式核对的数值"
    mismatches = [
        f"{label}: 重算={actual:.6g}, 展示={displayed}"
        for label, actual, displayed, decimals in checks
        if not _matches_rounded(actual, displayed, decimals)
    ]
    if mismatches:
        return False, "；".join(mismatches)
    return True, "；".join(f"{label}复算一致" for label, *_ in checks)


def assess_raw_traceability(
    claim: dict[str, Any], evidence_items: list[dict[str, Any]]
) -> dict[str, Any]:
    """区分“摘录复述”与“原始字段足以复算”。

    source_excerpt 只作为原始字段展示，不参与通过判定。严格口径要求
    evidence.value、字段及所需期间齐全，并按规则公式重算 Claim 数值一致。
    """
    text = str(claim.get("text") or "")
    mentions = extract_numeric_mentions(text)
    requested_ids = [str(v) for v in claim.get("evidence_ids") or []]
    by_id = {str(v.get("evidence_id") or ""): v for v in evidence_items}
    missing_ids = [eid for eid in requested_ids if eid not in by_id]
    linked = [by_id[eid] for eid in requested_ids if eid in by_id]
    excerpt_corpus = _compact(
        " ".join(str(v.get("source_excerpt") or "") for v in linked)
    )
    excerpt_replay = bool(mentions) and all(
        _compact(m) in excerpt_corpus for m in mentions
    )

    if missing_ids:
        return {
            "all_evidence_ids_resolved": False,
            "excerpt_replay": excerpt_replay,
            "arithmetic_verified": False,
            "raw_traceable": False,
            "reason": "evidence_id 无法解析：" + ", ".join(missing_ids),
        }
    if not linked:
        return {
            "all_evidence_ids_resolved": False,
            "excerpt_replay": False,
            "arithmetic_verified": False,
            "raw_traceable": False,
            "reason": "Claim 未绑定 evidence_id",
        }

    fields = {str(v.get("field_path") or "") for v in linked}
    periods = {str(v.get("period") or "") for v in linked if v.get("period")}
    nonempty_values = [v for v in linked if str(v.get("value") or "").strip()]
    rule_id = str(claim.get("rule_id") or "")

    def missing(required: set[str]) -> set[str]:
        return required - fields

    raw_ok = False
    reason = ""
    if rule_id == "R1":
        absent = missing({"acct_rcv", "oper_rev"})
        if absent:
            reason = "缺少字段：" + ", ".join(sorted(absent))
        elif len(periods) < 2:
            reason = "增速差需要当前期与同比基期，证据仅含单一期次"
        else:
            raw_ok = True
    elif rule_id == "R2":
        has_profit = bool(fields & {"net_profit", "net_profit_excl_min_int_inc"})
        has_cashflow = bool(fields & {"oper", "oper_cf", "net_cash_flows_oper_act"})
        absent = {
            label
            for label, present in (
                ("net_profit_excl_min_int_inc", has_profit),
                ("net_cash_flows_oper_act", has_cashflow),
            )
            if not present
        }
        if absent:
            reason = "缺少字段：" + ", ".join(sorted(absent))
        elif "季度" in text and len(periods) < 2:
            reason = "连续季度结论需要多期利润/现金流，证据仅含单一期次"
        else:
            raw_ok = True
    elif rule_id == "R3":
        has_debt = (
            "borrow" in fields
            or {
                "st_borrow",
                "lt_borrow",
            }
            <= fields
        )
        absent = missing({"monetary_cap", "tot_assets"})
        if not has_debt:
            absent.add("st_borrow+lt_borrow")
        if absent:
            reason = "占总资产比例无法复算，缺少字段：" + ", ".join(sorted(absent))
        else:
            raw_ok = True
    elif rule_id == "R4":
        absent = missing({"inventories", "oper_rev"})
        if absent:
            reason = "缺少字段：" + ", ".join(sorted(absent))
        elif len(periods) < 2:
            reason = "存货/营收增速差需要同比基期，证据仅含单一期次"
        else:
            raw_ok = True
    elif rule_id == "R5":
        absent = missing({"oper_rev"})
        if not fields & {"oper_cost", "less_oper_cost"}:
            absent.add("less_oper_cost")
        if absent:
            reason = "缺少字段：" + ", ".join(sorted(absent))
        elif len(periods) < 2:
            reason = "历史偏离需要历史序列，证据仅含单一期次"
        else:
            raw_ok = True
    elif rule_id == "R6":
        absent = missing({"oth_rcv", "tot_assets"})
        if absent:
            reason = "缺少字段：" + ", ".join(sorted(absent))
        elif ("同比" in text or "增速" in text) and len(periods) < 2:
            reason = "其他应收款增速需要基期值，证据仅含单一期次"
        else:
            raw_ok = True
    elif rule_id == "R7":
        if len(periods) < 2:
            reason = "增长背离需要多期序列，证据仅含单一期次"
        else:
            raw_ok = bool(nonempty_values)
    else:
        raw_ok = bool(nonempty_values) and excerpt_replay
        if not raw_ok:
            reason = "未知规则，无法证明原始字段足以复算"

    arithmetic_ok = False
    arithmetic_reason = "原始字段/期次不完整，未进入公式复算"
    if raw_ok and not nonempty_values:
        raw_ok = False
        reason = "证据未携带原始 value"
    if raw_ok:
        arithmetic_ok, arithmetic_reason = verify_claim_arithmetic(claim, linked)
        raw_ok = arithmetic_ok
        reason = arithmetic_reason
    return {
        "all_evidence_ids_resolved": True,
        "excerpt_replay": excerpt_replay,
        "arithmetic_verified": arithmetic_ok,
        "raw_traceable": raw_ok,
        "reason": reason,
    }


def compute_route_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    """计算 required-hit、exact-route 与模块级 Precision/Recall。"""
    by_category: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "required_hit": 0, "exact_match": 0}
    )
    per_module: dict[str, Counter] = {m: Counter() for m in CORE_MODULES}
    for record in records:
        expected = set(record["expected_modules"])
        actual = set(record["actual_modules"])
        category = str(record["category"])
        group = by_category[category]
        group["total"] += 1
        group["required_hit"] += int(expected <= actual)
        group["exact_match"] += int(expected == actual)
        for module in CORE_MODULES:
            exp = module in expected
            act = module in actual
            bucket = "tp" if exp and act else "fp" if act else "fn" if exp else "tn"
            per_module[module][bucket] += 1

    total = len(records)
    required_hits = sum(
        set(r["expected_modules"]) <= set(r["actual_modules"]) for r in records
    )
    exact_matches = sum(
        set(r["expected_modules"]) == set(r["actual_modules"]) for r in records
    )
    module_summary: dict[str, dict[str, Any]] = {}
    for module, counts in per_module.items():
        tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
        module_summary[module] = {
            **{key: counts[key] for key in ("tp", "fp", "fn", "tn")},
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
        }
    micro_tp = sum(v["tp"] for v in module_summary.values())
    micro_fp = sum(v["fp"] for v in module_summary.values())
    micro_fn = sum(v["fn"] for v in module_summary.values())
    return {
        "total": total,
        "required_hits": required_hits,
        "required_hit_rate": required_hits / total if total else 0.0,
        "exact_matches": exact_matches,
        "exact_match_rate": exact_matches / total if total else 0.0,
        "micro_precision": micro_tp / (micro_tp + micro_fp)
        if micro_tp + micro_fp
        else None,
        "micro_recall": micro_tp / (micro_tp + micro_fn)
        if micro_tp + micro_fn
        else None,
        "by_category": dict(by_category),
        "by_module": module_summary,
    }


def effective_route_modules(
    *,
    plan_intent: str,
    statuses: dict[str, dict[str, Any]],
    evidence_items: Iterable[Any] = (),
) -> tuple[list[str], str]:
    """统一工具族统计：指标快通道成功执行计入 finance 工具族。

    这里不伪称完整 finance_node 已运行；单独返回 execution_path，报告可区分
    full_module 与 indicator_query。
    """
    actual = [
        module
        for module in CORE_MODULES
        if statuses[module].get("state") not in ("skipped", "missing")
    ]
    execution_path = "full_module"
    evidence = [_model_dump(item) for item in evidence_items]
    indicator_succeeded = plan_intent == "indicator" and any(
        str(item.get("source_type") or "") == "financial_statement"
        and str(item.get("field_path") or "")
        and str(item.get("value") or "").strip()
        for item in evidence
    )
    if indicator_succeeded and "finance" not in actual:
        actual.append("finance")
        execution_path = "indicator_query"
    return actual, execution_path


def _pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value * 100:.1f}%"


def _escape_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def _git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return result.stdout.strip()
    except Exception:  # noqa: BLE001 - 报告降级，不阻断评估
        return "unknown"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _official_dataset_snapshot() -> dict[str, Any]:
    """校验本轮所用官方题集，阻止报告与题源版本错位。"""
    if not OFFICIAL_SIDECAR.exists():
        raise SystemExit(f"[dataset] 官方 sidecar 不存在: {OFFICIAL_SIDECAR}")
    if not OFFICIAL_CLEAN_XLSX.exists():
        raise SystemExit(f"[dataset] clean.xlsx 不存在: {OFFICIAL_CLEAN_XLSX}")

    from tests.evaluation.dataset_loader import load_clean_xlsx
    from tests.evaluation.official_runner import _validate_sidecar_against_excel

    items = [
        json.loads(line)
        for line in OFFICIAL_SIDECAR.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    dataset = load_clean_xlsx(OFFICIAL_CLEAN_XLSX)
    _validate_sidecar_against_excel(items, dataset.questions)
    sidecar_rows = {int(item["source_row"]) for item in items}
    deep_rows = {
        int(question["question_id"][1:])
        for question in dataset.questions
        if question.get("think_flag") == 1
    }
    if sidecar_rows != deep_rows:
        raise SystemExit(
            "[dataset] sidecar 与 clean.xlsx 的 think_flag=1 集合不一致："
            f"missing={sorted(deep_rows - sidecar_rows)} "
            f"extra={sorted(sidecar_rows - deep_rows)}"
        )
    return {
        "clean_xlsx": str(OFFICIAL_CLEAN_XLSX.relative_to(REPO_ROOT)).replace(
            "\\", "/"
        ),
        "clean_xlsx_sha256": _sha256(OFFICIAL_CLEAN_XLSX),
        "sidecar": str(OFFICIAL_SIDECAR.relative_to(REPO_ROOT)).replace("\\", "/"),
        "sidecar_sha256": _sha256(OFFICIAL_SIDECAR),
        "question_count": len(items),
        "deep_question_count": len(deep_rows),
        "source_validation": "passed",
    }


def _guard_and_snapshot() -> dict[str, Any]:
    from sqlalchemy import URL, create_engine, text

    from app.core.config import settings

    if settings.SQL_BACKEND != "mysql":
        raise SystemExit("[guard] 本评估只允许 SQL_BACKEND=mysql")
    demo_database = str(settings.MYSQL_DATABASE or "").strip()
    database = str(settings.MYSQL_TEST_DATABASE or "").strip()
    test_user = str(settings.MYSQL_TEST_USER or "").strip()
    test_password = str(settings.MYSQL_TEST_PASSWORD or "")
    if not database or not test_user or not test_password:
        raise SystemExit("[guard] 必须配置 MYSQL_TEST_DATABASE/USER/PASSWORD 三件套")
    if demo_database.lower() == database.lower():
        raise SystemExit(f"[guard] 测试库 {database!r} 与演示库 {demo_database!r} 相同")
    if not database.lower().endswith("_test"):
        raise SystemExit(f"[guard] 拒绝非测试库 MYSQL_TEST_DATABASE={database!r}")

    # 与官方 runner 保持一致：.env 默认保留演示库配置，脚本启动后才显式切换
    # 到独立测试凭据，并同步环境变量供后续 Settings()/子进程使用。
    settings.MYSQL_DATABASE = database
    settings.MYSQL_USER = test_user
    settings.MYSQL_PASSWORD = test_password
    os.environ["MYSQL_DATABASE"] = database
    os.environ["MYSQL_USER"] = test_user
    os.environ["MYSQL_PASSWORD"] = test_password

    url = URL.create(
        "mysql+pymysql",
        username=settings.MYSQL_USER,
        password=settings.MYSQL_PASSWORD,
        host=settings.MYSQL_HOST,
        port=settings.MYSQL_PORT,
        database=database,
    )
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            actual = str(conn.execute(text("SELECT DATABASE()")).scalar() or "")
            if actual.lower() != database.lower():
                raise SystemExit(
                    f"[guard] SELECT DATABASE()={actual!r}，期望 {database!r}"
                )
            version = str(conn.execute(text("SELECT VERSION()")).scalar() or "")
            dataset_rows = [
                dict(row)
                for row in conn.execute(
                    text(
                        "SELECT dataset_version, COUNT(*) AS row_count "
                        "FROM companies GROUP BY dataset_version ORDER BY dataset_version"
                    )
                ).mappings()
            ]
            counts = {}
            for table in (
                "companies",
                "balance_sheet",
                "income_statement",
                "cash_flow",
                "top_shareholders",
                "announcements",
                "research_reports",
            ):
                counts[table] = int(
                    conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
                )
    finally:
        engine.dispose()
    return {
        "database": database,
        "mysql_port": settings.MYSQL_PORT,
        "mysql_version": version,
        "dataset_versions": dataset_rows,
        "table_counts": counts,
        "graph_backend": settings.GRAPH_BACKEND,
        "llm_backend": settings.LLM_BACKEND,
        "web_search_backend": settings.WEB_SEARCH_BACKEND,
        "configured_dataset_version": settings.DATASET_VERSION,
    }


def _company_ref(code: str):
    from app.agents.state import CompanyRef
    from app.application.services.company_resolver import get_company_repository

    record = asyncio.run(get_company_repository().get_by_code(code))
    if record is None:
        raise RuntimeError(f"company_not_found: {code}")
    return CompanyRef(
        entity_id=record.entity_id,
        wind_code=record.wind_code,
        sec_name=record.sec_name,
        exchange=record.exchange_code or "",
        industry_l1=record.industry_l1 or "",
        listing_date=str(record.listing_date or ""),
        comp_type_code=str(record.comp_type_code or ""),
    )


def run_route_cases() -> list[dict[str, Any]]:
    from app.agents.graph import agent_graph
    from app.agents.state import RequestContext, RuntimeState
    from app.application.services.session_cleanup_service import SessionCleanupService

    compiled = agent_graph.compile()
    records: list[dict[str, Any]] = []
    session_ids: list[str] = []
    try:
        for case in ROUTE_CASES:
            token = f"phasee_route_{case.case_id.lower()}"
            session_ids.append(token)
            evaluated_question = case.question
            runtime = RuntimeState(
                trace_id=token,
                session_id=token,
                turn_id=token,
            )
            error = ""
            try:
                result = compiled.invoke(
                    {
                        "user_query": evaluated_question,
                        "request_context": RequestContext(
                            company_code=case.company_code
                        ),
                        "runtime": runtime,
                    }
                )
            except Exception as exc:  # noqa: BLE001 - 单题失败计为漏路由后继续
                result = {}
                error = f"{type(exc).__name__}: {exc}"
            plan = result.get("plan")
            raw_statuses = result.get("module_status") or {}
            statuses: dict[str, dict[str, Any]] = {}
            for module in CORE_MODULES:
                status = raw_statuses.get(module)
                statuses[module] = (
                    _model_dump(status)
                    if status is not None
                    else {"state": "missing", "error_code": "NO_MODULE_STATUS"}
                )
            plan_intent = getattr(plan, "intent", "error" if error else "")
            actual, execution_path = effective_route_modules(
                plan_intent=plan_intent,
                statuses=statuses,
                evidence_items=result.get("evidence") or [],
            )
            expected = list(case.expected_modules)
            records.append(
                {
                    "case_id": case.case_id,
                    "category": case.category,
                    "question": case.question,
                    "evaluated_question": evaluated_question,
                    "company_code": case.company_code,
                    "plan_intent": plan_intent,
                    "execution_path": execution_path,
                    "planned_modules": list(
                        getattr(plan, "requested_modules", []) or []
                    ),
                    "module_status": statuses,
                    "expected_modules": expected,
                    "actual_modules": actual,
                    "missing_modules": sorted(set(expected) - set(actual)),
                    "extra_modules": sorted(set(actual) - set(expected)),
                    "required_hit": set(expected) <= set(actual),
                    "exact_match": set(expected) == set(actual),
                    "error": error,
                }
            )
    finally:
        cleanup = SessionCleanupService()
        for session_id in session_ids:
            cleanup.cleanup_session(session_id)
    return records


def _stratified_sample(
    records: list[dict[str, Any]], limit: int
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[str(record["claim"].get("rule_id") or "unknown")].append(record)
    selected: list[dict[str, Any]] = []
    positions = Counter()
    order = [rule for rule in RULE_ORDER if groups.get(rule)]
    while len(selected) < limit:
        advanced = False
        for rule in order:
            pos = positions[rule]
            if pos >= len(groups[rule]):
                continue
            selected.append(groups[rule][pos])
            positions[rule] += 1
            advanced = True
            if len(selected) >= limit:
                break
        if not advanced:
            break
    return selected


def run_blind_review(limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from app.agents.graph import agent_graph
    from app.agents.state import RequestContext, RuntimeState
    from app.application.services.session_cleanup_service import SessionCleanupService

    compiled = agent_graph.compile()
    candidates: list[dict[str, Any]] = []
    company_errors: list[dict[str, str]] = []
    session_ids: list[str] = []
    try:
        for index, code in enumerate(BLIND_COMPANY_CODES, start=1):
            try:
                company = _company_ref(code)
                token = f"phasee_blind_{index:03d}"
                session_ids.append(token)
                question = f"{company.sec_name}财务风险如何？"
                result = compiled.invoke(
                    {
                        "user_query": question,
                        "request_context": RequestContext(company_code=code),
                        "runtime": RuntimeState(
                            trace_id=token,
                            session_id=token,
                            turn_id=token,
                        ),
                    }
                )
                all_evidence = [_model_dump(v) for v in result.get("evidence", [])]
                evidence_index = {v["evidence_id"]: v for v in all_evidence}
                for claim_obj in result.get("claims", []):
                    claim = _model_dump(claim_obj)
                    mentions = extract_numeric_mentions(str(claim.get("text") or ""))
                    if not mentions:
                        continue
                    linked = [
                        evidence_index[eid]
                        for eid in claim.get("evidence_ids") or []
                        if eid in evidence_index
                    ]
                    assessment = assess_raw_traceability(claim, all_evidence)
                    candidates.append(
                        {
                            "company_code": code,
                            "company_name": company.sec_name,
                            "industry_l1": company.industry_l1 or "",
                            "question": question,
                            "numeric_mentions": mentions,
                            "claim": claim,
                            "evidence": linked,
                            "assessment": assessment,
                            "plausibility_flags": detect_plausibility_flags(
                                str(claim.get("text") or "")
                            ),
                        }
                    )
            except Exception as exc:  # noqa: BLE001 - 单公司失败记录后继续
                company_errors.append(
                    {"company_code": code, "error": f"{type(exc).__name__}: {exc}"}
                )
    finally:
        cleanup = SessionCleanupService()
        for session_id in session_ids:
            cleanup.cleanup_session(session_id)

    selected = _stratified_sample(candidates, limit)
    if len(selected) < limit:
        raise RuntimeError(
            f"仅找到 {len(selected)} 条含业务数值的 Claim，少于 --blind-limit={limit}"
        )
    for index, record in enumerate(selected, start=1):
        record["sample_index"] = index
    diagnostics = {
        "candidate_count": len(candidates),
        "company_errors": company_errors,
        "candidate_rule_counts": dict(
            Counter(str(v["claim"].get("rule_id") or "unknown") for v in candidates)
        ),
        "selected_industry_counts": dict(
            Counter(v.get("industry_l1") or "<missing>" for v in selected)
        ),
        "selected_missing_industry_codes": sorted(
            {v["company_code"] for v in selected if not v.get("industry_l1")}
        ),
    }
    return selected, diagnostics


def render_route_report(
    records: list[dict[str, Any]],
    metrics: dict[str, Any],
    facts: dict[str, Any],
    generated_at: str,
) -> str:
    lines = [
        "# Phase E · 工具路由命中统计（成员 A）",
        "",
        f"> 生成时间：{generated_at}<br>",
        f"> 仓库提交：`{_git_sha()}`<br>",
        f"> 数据库：`{facts['database']}`（MySQL {facts['mysql_version']}，隔离测试库）<br>",
        f"> 官方题集：`{facts['official_dataset']['sidecar']}`，"
        f"{facts['official_dataset']['question_count']} 题，来源校验通过<br>",
        f"> clean.xlsx SHA-256：`{facts['official_dataset']['clean_xlsx_sha256']}`<br>",
        f"> sidecar SHA-256：`{facts['official_dataset']['sidecar_sha256']}`<br>",
        f"> 运行配置：`GRAPH_BACKEND={facts['graph_backend']}`、"
        f"`LLM_BACKEND={facts['llm_backend']}`、"
        f"`WEB_SEARCH_BACKEND={facts['web_search_backend']}`",
        "",
        "## 结论",
        "",
        f"- 必需模块命中：**{metrics['required_hits']}/{metrics['total']} "
        f"({_pct(metrics['required_hit_rate'])})**。该口径只要求期望模块均被调用。",
        f"- 精确路由：**{metrics['exact_matches']}/{metrics['total']} "
        f"({_pct(metrics['exact_match_rate'])})**。该口径同时惩罚漏路由和多路由。",
        f"- 模块级 micro Precision：**{_pct(metrics['micro_precision'])}**。",
        f"- 模块级 micro Recall：**{_pct(metrics['micro_recall'])}**。",
        "- 本轮不设 92% 硬门槛；未命中项按真实结果保留。",
        "",
        "## 方法与边界",
        "",
        "1. 当前 `main` 已有 `tests/evaluation/api_client.py`，但 REST 客户端返回结构不暴露 "
        "`module_status`。本报告因此在同一生产代码上直接运行完整 Agent 图，覆盖结构化代码解析、"
        "计划、模块执行与回答生成，再读取最终 `ModuleStatus`；`state != skipped` 计为实际调用。",
        "2. 为隔离工具路由本身，每题通过正式 `RequestContext.company_code` 预绑定同一公司；"
        "因此本统计不评价自然语言公司名召回。成功返回原始财务 Evidence 的指标快通道计入"
        "财务工具族，并以 `execution_path=indicator_query` 单列，不伪称完整 `finance_node` 已运行。",
        "3. 每题使用独立评测 session，并在 `finally` 中调用 `SessionCleanupService` 清理。",
        "4. `risk` 是汇总节点，不属于手册定义的财务/股权/舆情三类工具，未进入 Precision 分母。",
        "5. 官方 77 题在启动时用于题源版本和来源行门禁；本路由统计采用 20 条人工标注的"
        "单模块/综合诊断用例，不把两者冒充为同一评测集。",
        "",
        "## 分组统计",
        "",
        "| 意图类别 | 样本数 | 必需模块命中 | 精确路由 |",
        "|---|---:|---:|---:|",
    ]
    for category, values in metrics["by_category"].items():
        lines.append(
            f"| {_escape_cell(category)} | {values['total']} | "
            f"{values['required_hit']}/{values['total']} | "
            f"{values['exact_match']}/{values['total']} |"
        )
    lines += [
        "",
        "## 模块级混淆统计",
        "",
        "| 模块 | TP | FP | FN | TN | Precision | Recall |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for module, values in metrics["by_module"].items():
        lines.append(
            f"| `{module}` | {values['tp']} | {values['fp']} | {values['fn']} | "
            f"{values['tn']} | {_pct(values['precision'])} | {_pct(values['recall'])} |"
        )
    lines += [
        "",
        "## 逐题明细",
        "",
        "| ID | 类别 | 问题 | 期望 | 实际 | 执行路径 | 模块状态 | 必需命中 | 精确匹配 | 误判说明 |",
        "|---|---|---|---|---|---|---|:---:|:---:|---|",
    ]
    for record in records:
        status_text = ", ".join(
            f"{module}={value.get('state')}"
            + (f"/{value.get('error_code')}" if value.get("error_code") else "")
            for module, value in record["module_status"].items()
        )
        issues = []
        if record["missing_modules"]:
            issues.append("漏：" + ",".join(record["missing_modules"]))
        if record["extra_modules"]:
            issues.append("多：" + ",".join(record["extra_modules"]))
        if record.get("error"):
            issues.append("错误：" + record["error"])
        lines.append(
            "| {case_id} | {category} | {question} | {expected} | {actual} | {path} | {status} | "
            "{required} | {exact} | {issues} |".format(
                case_id=record["case_id"],
                category=_escape_cell(record["category"]),
                question=_escape_cell(record["question"]),
                expected="+".join(record["expected_modules"]),
                actual="+".join(record["actual_modules"]) or "无",
                path=record.get("execution_path", "full_module"),
                status=_escape_cell(status_text),
                required="✅" if record["required_hit"] else "❌",
                exact="✅" if record["exact_match"] else "❌",
                issues=_escape_cell("；".join(issues) or "—"),
            )
        )
    misses = [r for r in records if not r["exact_match"]]
    lines += [
        "",
        "## 未达标原因与改进项",
        "",
        f"- 本轮共有 **{len(misses)}** 条非精确路由。具体缺失/多调模块已在上表逐条列出。",
        "- `indicator_query` 与完整财务规则分析是两条不同执行路径；本报告只在成功取得"
        "原始财务 Evidence 时把前者计入财务工具族。",
        "- 含“风险”的问题先按明确领域词收窄；仅无领域限定的宽泛诊断或明确综合/全面"
        "请求才展开三模块。",
        "- 模块 `partial` 表示已经调用但数据不完整；路由命中统计不把它改记为漏路由，"
        "但逐题状态保留，供数据覆盖质量另行审计。",
        "",
    ]
    return "\n".join(lines)


def render_blind_report(
    records: list[dict[str, Any]],
    diagnostics: dict[str, Any],
    facts: dict[str, Any],
    generated_at: str,
) -> str:
    total = len(records)
    ids_ok = sum(v["assessment"]["all_evidence_ids_resolved"] for v in records)
    excerpt_ok = sum(v["assessment"]["excerpt_replay"] for v in records)
    arithmetic_ok = sum(
        v["assessment"].get("arithmetic_verified", False) for v in records
    )
    raw_ok = sum(v["assessment"]["raw_traceable"] for v in records)
    rule_counts = Counter(str(v["claim"].get("rule_id") or "unknown") for v in records)
    industry_counts = Counter(v.get("industry_l1") or "<missing>" for v in records)
    industry_known = total - industry_counts["<missing>"]
    missing_industry_codes = sorted(
        {v["company_code"] for v in records if not v.get("industry_l1")}
    )
    reason_counts = Counter(
        str(v["assessment"]["reason"])
        for v in records
        if not v["assessment"]["raw_traceable"]
    )
    plausibility_records = [v for v in records if v.get("plausibility_flags")]
    lines = [
        "# Phase E · 无幻觉数值 Claim 盲评报告（成员 A）",
        "",
        f"> 生成时间：{generated_at}<br>",
        f"> 仓库提交：`{_git_sha()}`<br>",
        f"> 数据库：`{facts['database']}`（MySQL {facts['mysql_version']}，隔离测试库）<br>",
        f"> 官方题集：`{facts['official_dataset']['sidecar']}`，"
        f"{facts['official_dataset']['question_count']} 题，来源校验通过<br>",
        f"> clean.xlsx SHA-256：`{facts['official_dataset']['clean_xlsx_sha256']}`<br>",
        f"> sidecar SHA-256：`{facts['official_dataset']['sidecar_sha256']}`<br>",
        f"> 数据版本（companies 实测）：`{json.dumps(facts['dataset_versions'], ensure_ascii=False)}`<br>",
        f"> Evidence 配置版本：`{facts['configured_dataset_version']}`",
        "",
        "## 结论",
        "",
        f"- 抽样：**{total} 条**含业务数值的财务 Claim，覆盖 "
        + "、".join(f"{rule}={count}" for rule, count in sorted(rule_counts.items()))
        + "。",
        f"- evidence_id 可解析率：**{ids_ok}/{total} ({_pct(ids_ok / total if total else 0)})**。",
        f"- source_excerpt 数值复述率：**{excerpt_ok}/{total} "
        f"({_pct(excerpt_ok / total if total else 0)})**。",
        f"- 公式级重算一致率：**{arithmetic_ok}/{total} "
        f"({_pct(arithmetic_ok / total if total else 0)})**。",
        f"- 严格原始字段可复算率：**{raw_ok}/{total} "
        f"({_pct(raw_ok / total if total else 0)})**。这是本报告采用的整体可溯源率。",
        f"- 行业字段覆盖：**{industry_known}/{total} "
        f"({_pct(industry_known / total if total else 0)})**；空值对应 "
        f"{len(missing_industry_codes)} 个证券代码，单列旁查，不据此伪造行业。",
        "",
        "`source_excerpt` 只用于展示原始字段和值，不再复制规则 explanation。摘录复述率因此"
        "不是通过条件；严格口径要求绑定 evidence 的 "
        "`field_path + value + period` 足够重算百分比、同比或历史偏离。",
        "",
        "## 抽样方法",
        "",
        f"- 从 {len(BLIND_COMPANY_CODES)} 家候选公司运行完整生产 Agent 图，读取最终 "
        f"Claim/Evidence，共得到 {diagnostics['candidate_count']} 条含业务数值候选 Claim。",
        f"- 按 R1-R7 轮询分层抽取 {total} 条，避免只挑单一公司/规则；未人工挑选通过项。",
        "- 仅评估带 `%`、`pp`、金额、倍数或期间单位的业务数值；股票代码、规则编号、"
        "无单位日期不进入抽样。",
        "- 本脚本按 wind_code 预绑定公司以隔离实体识别误差；完整 Agent 图可能调用 "
        "PersistTurn，所有独立评测 session 均在 finally 中清理。",
        "- 官方 77 题用于题源版本门禁；因其中只有 2 条被标注为财务相关，无法提供 20-30 条"
        "数值 Claim，本盲评另用真实 Agent 对话生成分层样本，二者不混称。",
        "",
        "## 行业覆盖旁查",
        "",
        "该统计只描述本次盲评样本覆盖，不把行业当作抽样或通过条件。行业空值必须再与"
        "当前 A 股证券快照核对；历史/退市证券按行业审计规则豁免，不能强填。",
        "",
        "| 行业一级 | 样本条数 |",
        "|---|---:|",
    ]
    for industry, count in sorted(industry_counts.items()):
        label = "空值（需按当前证券快照核对）" if industry == "<missing>" else industry
        lines.append(f"| {_escape_cell(label)} | {count} |")
    lines += [
        "",
        "行业空值代码："
        + ("、".join(f"`{code}`" for code in missing_industry_codes) or "无")
        + "。",
        "",
        "## 逐条明细",
        "",
        "| # | 公司 | 行业一级 | 规则 | 数值陈述 | claim_id | evidence_id | ID可查 | 摘录复述 | 原始可复算 | 结论/缺口 |",
        "|---:|---|---|---|---|---|---|:---:|:---:|:---:|---|",
    ]
    for record in records:
        claim = record["claim"]
        assessment = record["assessment"]
        lines.append(
            "| {idx} | {company} (`{code}`) | {industry} | {rule} | {text} | `{claim_id}` | "
            "{evidence_ids} | {ids_ok} | {excerpt} | {raw} | {reason} |".format(
                idx=record["sample_index"],
                company=_escape_cell(record["company_name"]),
                code=record["company_code"],
                industry=_escape_cell(record.get("industry_l1") or "空值"),
                rule=claim.get("rule_id") or "—",
                text=_escape_cell(claim.get("text") or ""),
                claim_id=claim.get("claim_id") or "",
                evidence_ids="<br>".join(
                    f"`{eid}`" for eid in claim.get("evidence_ids") or []
                ),
                ids_ok="✅" if assessment["all_evidence_ids_resolved"] else "❌",
                excerpt="✅" if assessment["excerpt_replay"] else "❌",
                raw="✅" if assessment["raw_traceable"] else "❌",
                reason=_escape_cell(assessment["reason"]),
            )
        )
    if reason_counts:
        lines += [
            "",
            "## 典型问题",
            "",
        ]
        for reason, count in reason_counts.most_common():
            lines.append(f"- {count} 条：{reason}。")
    lines += [
        "",
        "## 数值合理性旁查（不计入可溯源率）",
        "",
        "以下仅标记需人工复核的极端或模板矛盾，不在没有更多业务口径时直接判为错误：",
        "",
    ]
    if plausibility_records:
        for record in plausibility_records:
            lines.append(
                f"- 样本 {record['sample_index']} / `{record['claim']['claim_id']}`："
                + "；".join(record["plausibility_flags"])
                + "。"
            )
    else:
        lines.append("- 本次抽样未命中预设的极端值/模板矛盾规则。")
    lines += [
        "",
        "## 改进建议",
        "",
        "1. 派生指标 Claim 应绑定完整计算输入：当前期、同比基期、分母与历史窗口；"
        "不能只绑定当前期两个字段。",
        "2. `source_excerpt` 仅保存原始字段事实；规则 explanation 只放在 Claim/规则详情中，"
        "避免形成“Claim 证明 Claim”的循环。",
        "3. `RuleResult.calculation_trace` 保存 `formula_id/formula/calculation_version/inputs`，"
        "前端可展示“原始值 → 公式 → 派生值”的可复算链。",
        "4. Evidence 的 `dataset_version` 必须与库内 `companies.dataset_version` 对齐；"
        "本报告已分别展示二者，若不一致不得宣称版本链完整。",
        "5. R6 文案必须按实际触发条件和增速符号分支；占比触发不能被误写为增速触发，"
        "负增长不得描述为“增速较快”。",
        "",
        "逐条 evidence 的 `field_path/value/period/source_excerpt` 已保存在 "
        "`data/reports/phasee_member_a_evaluation.json`，可供复核。",
        "",
    ]
    return "\n".join(lines)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8", newline="\n")


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blind-limit", type=int, default=25)
    parser.add_argument(
        "--raw-output",
        type=Path,
        default=REPO_ROOT / "data/reports/phasee_member_a_evaluation.json",
    )
    parser.add_argument(
        "--route-report",
        type=Path,
        default=REPO_ROOT / "docs/reports/路由命中统计.md",
    )
    parser.add_argument(
        "--blind-report",
        type=Path,
        default=REPO_ROOT / "docs/reports/盲评报告.md",
    )
    args = parser.parse_args(argv)
    if not 20 <= args.blind_limit <= 30:
        parser.error("--blind-limit 必须在 20-30 之间")
    return args


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    generated_at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    official_dataset = _official_dataset_snapshot()
    print(
        "[dataset] sidecar={count} clean/source validation={validation} ✓".format(
            count=official_dataset["question_count"],
            validation=official_dataset["source_validation"],
        )
    )
    facts = _guard_and_snapshot()
    facts["official_dataset"] = official_dataset
    print(f"[guard] SELECT DATABASE() = {facts['database']} ✓")
    print(f"[route] running {len(ROUTE_CASES)} cases ...")
    route_records = run_route_cases()
    route_metrics = compute_route_metrics(route_records)
    print(f"[blind] collecting {args.blind_limit} numeric claims ...")
    blind_records, blind_diagnostics = run_blind_review(args.blind_limit)

    payload = {
        "schema_version": "phasee-member-a-v1",
        "generated_at": generated_at,
        "git_sha": _git_sha(),
        "facts": facts,
        "route": {"metrics": route_metrics, "records": route_records},
        "blind_review": {
            "diagnostics": blind_diagnostics,
            "records": blind_records,
        },
    }
    args.raw_output.parent.mkdir(parents=True, exist_ok=True)
    args.raw_output.write_text(
        # 仓库编码审计对单个文本文件设有 500 KiB 门槛；一空格缩进既保留
        # 人工可读性，也避免完整 Evidence 明细因纯空白超过门槛。
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _write_text(
        args.route_report,
        render_route_report(route_records, route_metrics, facts, generated_at),
    )
    _write_text(
        args.blind_report,
        render_blind_report(blind_records, blind_diagnostics, facts, generated_at),
    )
    print(
        "[done] required_hit={required} exact={exact} blind_raw={raw}/{total}".format(
            required=_pct(route_metrics["required_hit_rate"]),
            exact=_pct(route_metrics["exact_match_rate"]),
            raw=sum(v["assessment"]["raw_traceable"] for v in blind_records),
            total=len(blind_records),
        )
    )
    print(f"[report] {args.route_report}")
    print(f"[report] {args.blind_report}")
    print(f"[raw] {args.raw_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
