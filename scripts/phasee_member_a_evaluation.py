#!/usr/bin/env python3
"""Phase E 数据组成员 A：工具路由统计与数值 Claim 独立盲评。

本脚本只允许连接隔离的 MySQL 测试库。它不走实体解析与 PersistTurn：
当前 main 的公司候选查询会让空 sec_name 命中任意 mention，导致精确代码也可能
被判为 too_many_candidates；本任务已知主体，因此按 wind_code 从仓库读取公司，
再调用生产 PlanModules / Finance / Equity / Events / BuildClaims 节点。

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
import json
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

CORE_MODULES = ("finance", "equity", "events")
RULE_ORDER = ("R1", "R2", "R3", "R4", "R5", "R6", "R7")

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
    RouteCase("F01", "财务", "康美药业营业收入如何？", ("finance",)),
    RouteCase("F02", "财务", "康美药业资产负债情况如何？", ("finance",)),
    RouteCase("F03", "财务", "康美药业经营现金流如何？", ("finance",)),
    RouteCase("F04", "财务", "康美药业应收账款情况如何？", ("finance",)),
    RouteCase(
        "D01",
        "综合诊断",
        "康美药业有造假风险吗？",
        ("finance", "equity", "events"),
    ),
    RouteCase(
        "D02",
        "综合诊断",
        "综合分析康美药业的财务、股权和舆情风险",
        ("finance", "equity", "events"),
    ),
    RouteCase(
        "D03",
        "综合诊断",
        "康美药业是否存在财务、股权和公告综合风险？",
        ("finance", "equity", "events"),
    ),
    RouteCase("E01", "股权", "康美药业的前十大股东是谁？", ("equity",)),
    RouteCase("E02", "股权", "查询康美药业的股权结构", ("equity",)),
    RouteCase("E03", "股权", "查一下康美药业主要股东持股比例", ("equity",)),
    RouteCase("V01", "舆情", "康美药业最近有哪些公告？", ("events",)),
    RouteCase("V02", "舆情", "康美药业是否有负面舆情？", ("events",)),
    RouteCase("V03", "舆情", "查看康美药业近期事件", ("events",)),
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
    for raw in re.findall(r"([+-]?\d+(?:\.\d+)?)\s*pp", text or "", re.I):
        if abs(float(raw)) > 100:
            flags.append(f"百分点绝对值 {raw}pp 超过 100，需核对单位/缩放")
    if "现金流/利润比" in (text or ""):
        for raw in re.findall(r"现金流/利润比[^\d+-]*([+-]?\d+(?:\.\d+)?)", text):
            if abs(float(raw)) > 100:
                flags.append(f"现金流/利润比 {raw} 为极端值，需核对分母与单位")
    return flags


def assess_raw_traceability(
    claim: dict[str, Any], evidence_items: list[dict[str, Any]]
) -> dict[str, Any]:
    """区分“摘录复述”与“原始字段足以复算”。

    source_excerpt 当前可能直接保存规则 explanation。它能证明 ID 可回查，
    但不是对 derived metric 的独立复算。严格口径要求 evidence.value、字段及
    所需期间足够重算 Claim 中的全部业务数值。
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
            "raw_traceable": False,
            "reason": "evidence_id 无法解析：" + ", ".join(missing_ids),
        }
    if not linked:
        return {
            "all_evidence_ids_resolved": False,
            "excerpt_replay": False,
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
        absent = missing({"net_profit", "oper"})
        if absent:
            reason = "缺少字段：" + ", ".join(sorted(absent))
        elif "季度" in text and len(periods) < 2:
            reason = "连续季度结论需要多期利润/现金流，证据仅含单一期次"
        else:
            raw_ok = True
    elif rule_id == "R3":
        absent = missing({"monetary_cap", "borrow", "tot_assets"})
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
        absent = missing({"oper_rev", "oper_cost"})
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

    if raw_ok and not nonempty_values:
        raw_ok = False
        reason = "证据未携带原始 value"
    if raw_ok:
        reason = "evidence.value、字段与期次足以复算数值陈述"
    return {
        "all_evidence_ids_resolved": True,
        "excerpt_replay": excerpt_replay,
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
    return {
        "total": total,
        "required_hits": required_hits,
        "required_hit_rate": required_hits / total if total else 0.0,
        "exact_matches": exact_matches,
        "exact_match_rate": exact_matches / total if total else 0.0,
        "micro_precision": micro_tp / (micro_tp + micro_fp)
        if micro_tp + micro_fp
        else None,
        "by_category": dict(by_category),
        "by_module": module_summary,
    }


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


def _guard_and_snapshot() -> dict[str, Any]:
    from sqlalchemy import URL, create_engine, text

    from app.core.config import settings

    database = str(settings.MYSQL_DATABASE or "")
    configured_test = str(settings.MYSQL_TEST_DATABASE or "")
    if settings.SQL_BACKEND != "mysql":
        raise SystemExit("[guard] 本评估只允许 SQL_BACKEND=mysql")
    if database.lower() == "truthnet" or not database.lower().endswith("_test"):
        raise SystemExit(f"[guard] 拒绝非测试库 MYSQL_DATABASE={database!r}")
    if configured_test and configured_test.lower() != database.lower():
        raise SystemExit(
            f"[guard] MYSQL_DATABASE={database!r} 与 MYSQL_TEST_DATABASE="
            f"{configured_test!r} 不一致"
        )

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
    from app.agents.nodes.equity import equity_node
    from app.agents.nodes.events import events_node
    from app.agents.nodes.finance import finance_node
    from app.agents.nodes.plan_modules import plan_modules_node
    from app.agents.state import RuntimeState

    module_nodes = {
        "finance": finance_node,
        "equity": equity_node,
        "events": events_node,
    }
    companies = {
        case.company_code: _company_ref(case.company_code) for case in ROUTE_CASES
    }
    records: list[dict[str, Any]] = []
    for case in ROUTE_CASES:
        runtime = RuntimeState(
            trace_id=f"phasee_route_{case.case_id}",
            session_id=f"phasee_route_{case.case_id}",
            turn_id=f"phasee_route_{case.case_id}",
        )
        base_state = {
            "user_query": case.question,
            "company": companies[case.company_code],
            "runtime": runtime,
        }
        plan = plan_modules_node(base_state)["plan"]
        statuses: dict[str, dict[str, Any]] = {}
        for module, node in module_nodes.items():
            output = node({**base_state, "plan": plan})
            status = output.get("module_status", {}).get(module)
            statuses[module] = (
                _model_dump(status)
                if status is not None
                else {
                    "state": "missing",
                    "error_code": "NO_MODULE_STATUS",
                }
            )
        actual = [
            module
            for module in CORE_MODULES
            if statuses[module].get("state") not in ("skipped", "missing")
        ]
        expected = list(case.expected_modules)
        records.append(
            {
                "case_id": case.case_id,
                "category": case.category,
                "question": case.question,
                "company_code": case.company_code,
                "plan_intent": plan.intent,
                "planned_modules": list(plan.requested_modules),
                "module_status": statuses,
                "expected_modules": expected,
                "actual_modules": actual,
                "missing_modules": sorted(set(expected) - set(actual)),
                "extra_modules": sorted(set(actual) - set(expected)),
                "required_hit": set(expected) <= set(actual),
                "exact_match": set(expected) == set(actual),
            }
        )
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
    from app.agents.nodes.build_claims import build_claims_node
    from app.agents.nodes.finance import finance_node
    from app.agents.state import ExecutionPlan, RuntimeState

    candidates: list[dict[str, Any]] = []
    company_errors: list[dict[str, str]] = []
    for index, code in enumerate(BLIND_COMPANY_CODES, start=1):
        try:
            company = _company_ref(code)
            runtime = RuntimeState(
                trace_id=f"phasee_blind_trace_{index:03d}",
                session_id=f"phasee_blind_session_{index:03d}",
                turn_id=f"phasee_blind_turn_{index:03d}",
            )
            state: dict[str, Any] = {
                "user_query": f"{company.sec_name}财务风险如何？",
                "company": company,
                "plan": ExecutionPlan(intent="diagnose", requested_modules=["finance"]),
                "runtime": runtime,
            }
            finance_output = finance_node(state)
            state.update(finance_output)
            claims_output = build_claims_node(state)
            all_evidence = [_model_dump(v) for v in claims_output.get("evidence", [])]
            evidence_index = {v["evidence_id"]: v for v in all_evidence}
            for claim_obj in claims_output.get("claims", []):
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
                        "question": state["user_query"],
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
        "- 本轮不设 92% 硬门槛；未命中项按真实结果保留。",
        "",
        "## 方法与边界",
        "",
        "1. 当前 `main` 不存在手册所写的 `tests/evaluation/api_client.py`。本报告调用当前生产 "
        "`plan_modules_node`，随后实际执行 Finance/Equity/Events 节点并读取各自 "
        "`ModuleStatus`；`state != skipped` 计为实际调用。",
        "2. 当前公司候选 SQL 会让空 `sec_name` 命中任意 mention，精确代码也可能被判 "
        "`too_many_candidates`。本任务已知主体，故使用 `600518.SH` 从公司仓库精确读取后"
        "再评路由；实体识别质量不混入工具路由指标。",
        "3. `risk` 是汇总节点，不属于手册定义的财务/股权/舆情三类工具，未进入 Precision 分母。",
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
        "| ID | 类别 | 问题 | 期望 | 实际 | 模块状态 | 必需命中 | 精确匹配 | 误判说明 |",
        "|---|---|---|---|---|---|:---:|:---:|---|",
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
        lines.append(
            "| {case_id} | {category} | {question} | {expected} | {actual} | {status} | "
            "{required} | {exact} | {issues} |".format(
                case_id=record["case_id"],
                category=_escape_cell(record["category"]),
                question=_escape_cell(record["question"]),
                expected="+".join(record["expected_modules"]),
                actual="+".join(record["actual_modules"]) or "无",
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
        "- 优先检查 `indicator` 意图：若营业收入、经营现金流等问题的 "
        "`requested_modules=[]`，应明确这是直达指标服务的设计，还是漏掉 `finance`。"
        "在口径澄清前，本报告按手册要求将其记为漏路由。",
        "- 对含“风险”的股权/舆情问题，建议补充路由标注规范：是要求单模块，还是按综合诊断"
        "调用三模块。否则 Precision 会混入标注歧义。",
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
    raw_ok = sum(v["assessment"]["raw_traceable"] for v in records)
    rule_counts = Counter(str(v["claim"].get("rule_id") or "unknown") for v in records)
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
        f"- 严格原始字段可复算率：**{raw_ok}/{total} "
        f"({_pct(raw_ok / total if total else 0)})**。这是本报告采用的整体可溯源率。",
        "",
        "`source_excerpt` 当前直接保存规则 explanation，通常与 Claim 数值相同；因此 100% 的"
        "摘录复述率并不能独立证明数值来自原始财报。严格口径要求绑定 evidence 的 "
        "`field_path + value + period` 足够重算百分比、同比或历史偏离。",
        "",
        "## 抽样方法",
        "",
        f"- 从 {len(BLIND_COMPANY_CODES)} 家候选公司运行生产 `finance_node` + "
        f"`build_claims_node`，共得到 {diagnostics['candidate_count']} 条含业务数值候选 Claim。",
        f"- 按 R1-R7 轮询分层抽取 {total} 条，避免只挑单一公司/规则；未人工挑选通过项。",
        "- 仅评估带 `%`、`pp`、金额、倍数或期间单位的业务数值；股票代码、规则编号、"
        "无单位日期不进入抽样。",
        "- 本脚本按 wind_code 预绑定公司，绕过当前空 `sec_name` 导致的实体候选污染；"
        "不调用 PersistTurn，不遗留评测会话。",
        "",
        "## 逐条明细",
        "",
        "| # | 公司 | 规则 | 数值陈述 | claim_id | evidence_id | ID可查 | 摘录复述 | 原始可复算 | 结论/缺口 |",
        "|---:|---|---|---|---|---|:---:|:---:|:---:|---|",
    ]
    for record in records:
        claim = record["claim"]
        assessment = record["assessment"]
        lines.append(
            "| {idx} | {company} (`{code}`) | {rule} | {text} | `{claim_id}` | "
            "{evidence_ids} | {ids_ok} | {excerpt} | {raw} | {reason} |".format(
                idx=record["sample_index"],
                company=_escape_cell(record["company_name"]),
                code=record["company_code"],
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
        "2. `source_excerpt` 应保存来源原文或明确标成 `derived_explanation`；不要把规则 explanation"
        "放进看似原始证据的字段，否则会形成“Claim 证明 Claim”的循环。",
        "3. Evidence 增加 `formula`、`input_evidence_ids` 与 `calculation_version`，前端可展示"
        "“原始值 → 公式 → 派生值”的可复算链。",
        "4. Evidence 的 `dataset_version` 必须与库内 `companies.dataset_version` 对齐；"
        "本报告已分别展示二者，若不一致不得宣称版本链完整。",
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
    facts = _guard_and_snapshot()
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
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
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
