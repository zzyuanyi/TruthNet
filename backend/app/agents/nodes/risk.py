"""Risk — Phase C 后端任务 6. 风险评分 Agent 节点.

读取已完成的 finance/equity/events 模块结果 + 交叉验证 + 行业基准 + 评级拐点，
调用 RiskScoringService 计算综合风险，产出风险 Claim。
不重复计算规则；不实例化任何图实现（股权结果由 equity 节点提供）。
"""

from __future__ import annotations

from app.agents.state import AgentState, Claim, ModuleStatus
from app.domain.provenance.id_factory import make_claim_id
from app.domain.risk.severity import risk_level_label


def _fetch_rating_inflections(company_code: str, as_of: str = "") -> list:
    """从 rating_changes 表读取该公司评级变更并检测拐点。"""
    try:
        from app.domain.events.rating_inflection import (
            RatingChangeRecord,
            detect_inflections,
        )
        from app.domain.finance._fetch import _get_engine
        from sqlalchemy import text

        engine = _get_engine()
        with engine.connect() as conn:
            sql = (
                "SELECT wind_code, quarter, institution, direction "
                "FROM rating_changes WHERE wind_code = :c "
            )
            params = {"c": company_code}
            if as_of:
                sql += (
                    "AND (published_at IS NULL "
                    "OR REPLACE(published_at, '-', '') <= :asof) "
                )
                params["asof"] = as_of
            rows = conn.execute(text(sql), params).mappings().fetchall()
        records = [
            RatingChangeRecord(
                wind_code=r["wind_code"],
                quarter=r["quarter"],
                institution=r["institution"],
                direction=r["direction"],
            )
            for r in rows
        ]
        return detect_inflections(records)
    except Exception:  # noqa: BLE001 — 评级拐点缺失不阻塞风险
        return []


def _fetch_benchmarks(company_code: str, as_of: str, industry_l1: str) -> dict:
    """行业基准公司分位（行业已知时）。"""
    if not industry_l1:
        return {}
    try:
        from app.domain.benchmarks.calculator import (
            MIN_PEER_SAMPLE,
            compute_metric_values,
            percentile_rank,
        )
        from app.domain.benchmarks.metric_registry import all_metrics
        from app.domain.finance._fetch import _get_engine

        engine = _get_engine()
        benchmarks: dict[str, dict] = {}
        for metric in all_metrics():
            try:
                pairs = compute_metric_values(engine, metric, industry_l1, as_of)
                values = [v for _, v in pairs]
                company_value = next((v for c, v in pairs if c == company_code), None)
                if len(values) >= MIN_PEER_SAMPLE and company_value is not None:
                    benchmarks[metric.metric_id] = {
                        "company_percentile": percentile_rank(company_value, values),
                        "sample_count": len(values),
                    }
            except Exception:  # noqa: BLE001
                continue
        return benchmarks
    except Exception:  # noqa: BLE001
        return {}


def risk_node(state: AgentState) -> dict:
    """风险评分节点：复用模块结果 → RiskScoringService → 风险 Claim。"""
    company = state.get("company")
    results = state.get("results")
    cross_validation = state.get("cross_validation")

    if company is None:
        return {
            "module_status": {
                "risk": ModuleStatus(state="skipped", error_code="NO_COMPANY")
            },
            "messages": [],
        }

    as_of = ""
    plan = state.get("plan")
    if plan is not None and plan.as_of:
        as_of = plan.as_of.strftime("%Y%m%d")
    # 2026-08-16 口径整改：未传期次时从库内真实期次推导，禁止硬编码默认
    if not as_of:
        try:
            from app.domain.finance.data_as_of import resolve_company_data_as_of

            as_of = resolve_company_data_as_of(company.wind_code)
        except Exception:  # noqa: BLE001
            as_of = ""

    # 评级拐点 + 行业基准
    rating_inflections = _fetch_rating_inflections(company.wind_code, as_of=as_of)
    benchmarks = _fetch_benchmarks(company.wind_code, as_of, company.industry_l1 or "")

    try:
        from app.application.services.risk_scoring_service import RiskScoringService

        svc = RiskScoringService()
        out = svc.score(
            wind_code=company.wind_code,
            as_of=as_of,
            sec_name=company.sec_name,
            finance_result=results.finance if results else None,
            equity_result=results.equity if results else None,
            events_result=results.events if results else None,
            benchmarks=benchmarks,
            rating_inflections=rating_inflections,
            cross_validation=cross_validation,
        )
    except Exception:  # noqa: BLE001 — 明确降级，不伪造风险结果
        # 必须 dict 包装（与其他节点一致）：module_status reducer 是 {**a, **b}，
        # 裸 ModuleStatus 对象会让合并抛 TypeError，导致整个 graph 中断
        return {
            "module_status": {
                "risk": ModuleStatus(
                    state="failed",
                    error_code="RISK_SCORING_ERROR",
                    recoverable=True,
                )
            },
            "messages": [],
            "risk_output": None,
        }

    # 风险 Claim（非 green/unknown 时生成）
    claims: list[Claim] = []
    if out.risk_level not in ("green", "unknown"):
        runtime_obj = state.get("runtime")
        turn_id = getattr(runtime_obj, "turn_id", "") if runtime_obj else ""
        trace_id = getattr(runtime_obj, "trace_id", "") if runtime_obj else ""
        text = (
            f"{company.sec_name}综合风险等级为{risk_level_label(out.risk_level)}"
            f"（综合分 {out.overall_score:.2f}）"
            f"{'；' + '；'.join(out.key_contributors[:3]) if out.key_contributors else ''}"
        )
        claim_id = make_claim_id(
            turn_id=turn_id,
            company_code=company.wind_code,
            claim_type="risk",
            claim_text=text,
            rule_version=out.rule_set_version,
        )
        claims.append(
            Claim(
                claim_id=claim_id,
                text=text,
                claim_type="risk",
                severity=out.risk_level,
                confidence=out.confidence,
                evidence_ids=out.evidence_ids[:50],
                turn_id=turn_id,
                trace_id=trace_id,
                company_code=company.wind_code,
                module="risk",
            )
        )

    return {
        "module_status": {"risk": ModuleStatus(state="success")},
        "claims": claims,
        "risk_output": out,
        "messages": [],
    }
