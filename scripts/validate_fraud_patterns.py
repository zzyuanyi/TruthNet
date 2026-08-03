#!/usr/bin/env python
"""造假手法真实验证 — Phase C 数据任务 6.

对真实公司运行 7 条规则 → 匹配造假模式（fraud_patterns.yaml）→ 收集真实案例。
每个案例的 Claim/Evidence 以统一 ID 幂等持久化（可经 /api/v1/claims|evidence 查询）。

输出:
  - docs/reports/FRAUD_PATTERN_REAL_CASES.md
  - data/processed/fraud_pattern_real_cases.json

验收: >=3 个真实公司案例、>=2 种模式；文案只写"风险信号/疑似模式"，不写"确认造假"。

用法:
    python scripts/validate_fraud_patterns.py --dry-run
    python scripts/validate_fraud_patterns.py --limit 300
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(1, str(_ROOT / "backend"))

from sqlalchemy import create_engine, text  # noqa: E402

from backend.app.core.config import settings  # noqa: E402
from backend.app.domain.finance.rule_engine import evaluate_all_rules  # noqa: E402
from backend.app.domain.provenance.id_factory import (  # noqa: E402
    NS_FINANCE,
    make_claim_id,
    make_evidence_id,
)
from backend.app.domain.risk.fraud_patterns import match_patterns  # noqa: E402

MIN_REAL_CASES = 3
MIN_PATTERNS = 2


def _engine():
    if settings.SQL_BACKEND == "mysql":
        url = (
            f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
            f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
            "?charset=utf8mb4"
        )
    else:
        url = f"sqlite:///{settings.SQLITE_PATH}"
    return create_engine(url, pool_pre_ping=True)


def _latest_period(engine) -> str:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT MAX(report_period) FROM income_statement "
                "WHERE statement_type = '408006000'"
            )
        ).scalar()
    return row or "20260331"


def _candidates(engine, as_of: str, limit: int) -> list[tuple[str, str]]:
    """候选公司：非金融、有母公司当期营收、行业已知（确定性顺序）。"""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT DISTINCT c.wind_code, c.sec_name "
                "FROM income_statement t JOIN companies c ON t.wind_code = c.wind_code "
                "WHERE t.statement_type = '408006000' AND t.report_period = :p "
                "AND t.oper_rev IS NOT NULL AND c.comp_type_code = 1 "
                "AND c.industry_l1 IS NOT NULL "
                "ORDER BY c.wind_code ASC LIMIT :lim"
            ),
            {"p": as_of, "lim": limit},
        ).fetchall()
    return [(r[0], r[1]) for r in rows]


def _coverage_score(results: dict) -> float:
    """规则 quality data_completeness 均值。"""
    completions = [
        r.quality.get("data_completeness", 0.0)
        for r in results.values()
        if r.quality and r.quality.get("data_completeness") is not None
    ]
    if not completions:
        return 0.0
    return round(sum(completions) / len(completions), 3)


def _evidence_ids_for(wind_code: str, as_of: str, triggered: list[str]) -> list[str]:
    ids = []
    for rid in triggered:
        ids.append(
            make_evidence_id(
                source_namespace=NS_FINANCE,
                source_type="financial_statement",
                source_record_id=f"{wind_code}|{as_of}",
                field_path=f"rule_{rid}",
                period=as_of,
                dataset_version=settings.DATASET_VERSION,
                company_code=wind_code,
            )
        )
    return ids


def _persist_run(engine, trace_id: str, company_codes: list[str], as_of: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO analysis_runs (run_id, trace_id, endpoint, company_codes, "
                "period, statement_scope, status, created_at) "
                "VALUES (:rid, :trace, 'validate_fraud_patterns', :codes, :per, "
                "'parent_company', 'completed', CURRENT_TIMESTAMP)"
            ),
            {
                "rid": f"run_{uuid.uuid4().hex[:12]}",
                "trace": trace_id,
                "codes": json.dumps(company_codes, ensure_ascii=False),
                "per": as_of,
            },
        )


def _persist_claims_evidence(engine, trace_id: str, cases: list[dict]) -> None:
    """幂等持久化案例的 Claim/Evidence/links（可经 Lookup 查询）。"""
    ignore = "IGNORE" if settings.SQL_BACKEND == "mysql" else "OR IGNORE"
    now = datetime.now(timezone.utc)
    for case in cases:
        claim_id = case["claim_ids"][0] if case["claim_ids"] else ""
        with engine.begin() as conn:
            for eid in case["evidence_ids"]:
                conn.execute(
                    text(
                        f"INSERT {ignore} INTO evidence_refs "
                        "(evidence_id, source_type, source_record_id, company_code, "
                        " field_path, period, dataset_version, retrieved_at, "
                        " trace_id, module, source_table) "
                        "VALUES (:eid, 'financial_statement', :srid, :cc, :fp, :per, "
                        " :dv, :ret, :trace, 'finance', 'financial_statement')"
                    ),
                    {
                        "eid": eid,
                        "srid": f"{case['wind_code']}|{case['data_scope']['as_of']}",
                        "cc": case["wind_code"],
                        "fp": f"fraud_pattern_{case['pattern_id']}",
                        "per": case["data_scope"]["as_of"],
                        "dv": case["data_scope"]["dataset_version"],
                        "ret": now,
                        "trace": trace_id,
                    },
                )
            if claim_id:
                conn.execute(
                    text(
                        f"INSERT {ignore} INTO claims "
                        "(claim_id, turn_id, text, claim_type, severity, confidence, "
                        " rule_id, rule_version, verification_status, generated_at, "
                        " trace_id, company_code, module) "
                        "VALUES (:cid, NULL, :text, 'risk_signal', :sev, :conf, "
                        " :rid, :rver, 'verified', :gen, :trace, :cc, 'risk')"
                    ),
                    {
                        "cid": claim_id,
                        "text": case["conclusion"],
                        "sev": case["severity"],
                        "conf": case["confidence_score"],
                        "rid": f"pattern_{case['pattern_id']}",
                        "rver": "1.0.0",
                        "gen": now,
                        "trace": trace_id,
                        "cc": case["wind_code"],
                    },
                )
                for seq, eid in enumerate(case["evidence_ids"]):
                    conn.execute(
                        text(
                            f"INSERT {ignore} INTO claim_evidence_links "
                            "(claim_id, evidence_id, relation_type, sequence_no, created_at) "
                            "VALUES (:cid, :eid, 'supports', :seq, CURRENT_TIMESTAMP)"
                        ),
                        {"cid": claim_id, "eid": eid, "seq": seq},
                    )


def run(limit: int, as_of: str | None, dry_run: bool) -> dict:
    engine = _engine()
    as_of = as_of or _latest_period(engine)
    dataset_version = settings.DATASET_VERSION or "competition-2026"

    candidates = _candidates(engine, as_of, limit)
    print(f"候选公司: {len(candidates)} 家 (as_of={as_of})")

    cases: list[dict] = []
    seen_company = 0
    for wc, name in candidates:
        results = evaluate_all_rules(wc, as_of)
        # 规则结果 → match_patterns 需要的 dict
        rule_dict = {
            rid: {"status": r.status, "severity": r.severity}
            for rid, r in results.items()
        }
        matches = match_patterns(rule_dict)
        if not matches:
            continue
        # 优先保留置信度最高的匹配（每公司最多记录 2 个模式）
        matches_sorted = sorted(
            matches,
            key=lambda m: (m.confidence == "high", len(m.triggered_rules)),
            reverse=True,
        )
        coverage = _coverage_score(results)
        triggered = [rid for rid, r in results.items() if r.status == "triggered"]
        for m in matches_sorted[:2]:
            conf_score = {"high": 0.85, "medium": 0.6, "low": 0.4}.get(
                m.confidence, 0.5
            )
            # 低 coverage 不得给高置信度
            if coverage < 0.5 and conf_score > 0.6:
                conf_score = 0.5
            evidence_ids = _evidence_ids_for(wc, as_of, triggered or [m.pattern_id])
            claim_id = make_claim_id(
                turn_id="fraud_validate",
                company_code=wc,
                claim_type="risk_signal",
                claim_text=f"疑似{_pattern_label(m.pattern_id)}风险信号（{m.pattern_name}）",
            )
            cases.append(
                {
                    "pattern_id": m.pattern_id,
                    "pattern_name": m.pattern_name,
                    "wind_code": wc,
                    "sec_name": name,
                    "triggered_rules": triggered,
                    "supporting_signals": m.triggered_rules,
                    "contradicting_signals": [
                        f"{rid} 数据不足/不适用" for rid in m.unavailable_rules
                    ]
                    if m.partial_coverage
                    else [],
                    "claim_ids": [claim_id],
                    "evidence_ids": evidence_ids,
                    "data_scope": {
                        "as_of": as_of,
                        "statement_scope": "parent_company",
                        "dataset_version": dataset_version,
                    },
                    "coverage": coverage,
                    "confidence": m.confidence,
                    "confidence_score": round(conf_score, 3),
                    "severity": "orange" if m.confidence == "high" else "yellow",
                    "conclusion": (
                        f"风险信号/疑似模式: {name}（{wc}）呈现{m.pattern_name}特征"
                        f"（{'/'.join(m.triggered_rules)} 触发），"
                        f"属风险信号而非造假认定，需结合事件/股权综合判断"
                    ),
                }
            )
        seen_company += 1

    # 去重（同公司同模式只保留一条）
    seen: set[tuple[str, str]] = set()
    unique_cases = []
    for c in cases:
        key = (c["wind_code"], c["pattern_id"])
        if key in seen:
            continue
        seen.add(key)
        unique_cases.append(c)
    cases = unique_cases

    patterns_covered = {c["pattern_id"] for c in cases}
    print(
        f"真实案例: {len(cases)} 个 | 模式覆盖: {sorted(patterns_covered)} "
        f"| 触发公司: {seen_company} 家"
    )

    if not dry_run and cases:
        trace_id = f"trace_fraud_validate_{uuid.uuid4().hex[:8]}"
        _persist_run(engine, trace_id, [c["wind_code"] for c in cases], as_of)
        _persist_claims_evidence(engine, trace_id, cases)
        print(f"已持久化 Claim/Evidence (trace={trace_id})")

    return {
        "as_of": as_of,
        "cases": cases,
        "patterns_covered": sorted(patterns_covered),
    }


def _pattern_label(pid: str) -> str:
    return {
        "P1": "收入虚增",
        "P2": "资金占用",
        "P3": "利润调节",
        "P4": "资产虚增",
        "P5": "综合粉饰",
    }.get(pid, pid)


def _md(result: dict) -> str:
    lines = [
        "# TruthNet · 造假模式真实验证报告 — Phase C",
        "",
        f"> 生成时间: {datetime.now(timezone.utc).isoformat()} | as_of: {result['as_of']}",
        f"> 覆盖模式: {result['patterns_covered']}",
        "> 说明: 以下为真实财务数据规则触发的**风险信号/疑似模式**，不代表造假认定。",
        "",
        "## 案例列表",
        "",
    ]
    for i, c in enumerate(result["cases"], 1):
        lines += [
            f"### 案例 {i}: {c['sec_name']}（{c['wind_code']}）— {c['pattern_name']}",
            "",
            f"- pattern_id: `{c['pattern_id']}`",
            f"- 触发规则: {', '.join(c['triggered_rules']) or '无'}",
            f"- 支撑信号: {', '.join(c['supporting_signals'])}",
            f"- 相反信号: {', '.join(c['contradicting_signals']) or '无'}",
            f"- 数据覆盖: {c['coverage']} | 置信度: {c['confidence']} ({c['confidence_score']})",
            f"- claim_id: `{c['claim_ids'][0] if c['claim_ids'] else ''}`",
            f"- evidence_ids: `{c['evidence_ids'][0]}` ... 共 {len(c['evidence_ids'])} 条",
            f"- 结论: {c['conclusion']}",
            "",
        ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="造假手法真实验证")
    parser.add_argument("--limit", type=int, default=300, help="候选公司上限")
    parser.add_argument("--as-of", default=None, help="报告期 YYYYMMDD")
    parser.add_argument("--dry-run", action="store_true", help="不写库不落盘")
    args = parser.parse_args()

    result = run(args.limit, args.as_of, args.dry_run)
    cases = result["cases"]
    if len(cases) < MIN_REAL_CASES:
        print(
            f"警告: 真实案例 {len(cases)} < {MIN_REAL_CASES}，"
            f"未达验收（至少 {MIN_REAL_CASES} 个真实公司案例、{MIN_PATTERNS} 种模式）",
            file=sys.stderr,
        )
        if not args.dry_run:
            return 2
    if len(result["patterns_covered"]) < MIN_PATTERNS:
        print(
            f"警告: 模式覆盖 {result['patterns_covered']} < {MIN_PATTERNS}",
            file=sys.stderr,
        )

    if args.dry_run:
        for c in cases[:5]:
            print(
                f"  {c['sec_name']} {c['wind_code']} -> {c['pattern_id']} {c['confidence']}"
            )
        print("dry-run 完成，未写库未落盘。")
        return 0

    out_dir = Path("docs/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "FRAUD_PATTERN_REAL_CASES.md").write_text(
        _md(result), encoding="utf-8", newline="\n"
    )
    proc_dir = Path("data/processed")
    proc_dir.mkdir(parents=True, exist_ok=True)
    (proc_dir / "fraud_pattern_real_cases.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    print("已写入 docs/reports/FRAUD_PATTERN_REAL_CASES.md")
    print("已写入 data/processed/fraud_pattern_real_cases.json")
    return 0 if len(cases) >= MIN_REAL_CASES else 2


if __name__ == "__main__":
    sys.exit(main())
