"""财务分析路由 — V12 §11.10 + Phase C 任务 9/16.

GET /api/v1/companies/{code}/finance?as_of=20260331

要求:
  - 只接受 statement_scope=parent_company（consolidated/auto → 422）
  - data_quality.periods_available 来自真实查询
  - 返回真实 industry benchmark（industry_benchmarks 表 / 实时计算）
  - 全部 evidence_id 使用统一 make_evidence_id 并可查询（持久化到 evidence_refs）
  - 规则引擎失败 → risk_level=unknown，绝不返回伪造的空正常结果
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Path, Query

from app.api.v1.schemas.common import ApiMeta, V12Response, WarningItem
from app.core.errors import ErrorCode
from app.api.v1.schemas.finance import (
    DataQuality,
    FinanceResponseData,
    FinanceRuleItem,
    IndustryBenchmark,
)
from app.application.services.similar_case_provider import (
    SimilarCaseProvider,
    compute_similar_cases,
)
from app.core.config import settings
from app.domain.finance._fetch import fetch_company_field

router = APIRouter(tags=["finance"])

# 相似指标案例 Provider（模块级可注入，供测试替换 FakeProvider）
_similar_case_provider: SimilarCaseProvider | None = None


def set_similar_case_provider(provider: SimilarCaseProvider | None) -> None:
    """注入/重置相似案例 Provider（测试替换 FakeProvider）。"""
    global _similar_case_provider
    _similar_case_provider = provider


def _get_similar_case_provider() -> SimilarCaseProvider:
    """返回当前相似案例 Provider（默认惰性建真实实现）。"""
    global _similar_case_provider
    if _similar_case_provider is None:
        from app.application.services.similar_case_provider import (
            RealSimilarCaseProvider,
        )

        _similar_case_provider = RealSimilarCaseProvider()
    return _similar_case_provider


_TABLE_CODE_MAP = {
    "bs": "balance_sheet",
    "is": "income_statement",
    "cf": "cash_flow",
}


def _trace() -> str:
    return str(uuid.uuid4())


def _normalize_evidence_id(legacy: str, wind_code: str, as_of: str) -> str:
    """legacy evidence_id → 统一 ID（⑥ 起委托共享模块，与 /comparisons 同源）。"""
    from app.application.services.finance_evidence import normalize_rule_evidence_id

    return normalize_rule_evidence_id(legacy, wind_code, as_of)


async def _resolve_company(code: str) -> tuple[str, str, str, str] | None:
    """解析公司代码 → (entity_id, wind_code, sec_name, industry_l1)。"""
    from app.application.services.company_resolver import resolve_company

    rec = await resolve_company(code)
    if rec is None:
        return None
    return (rec.entity_id, rec.wind_code, rec.sec_name, rec.industry_l1 or "")


@router.get(
    "/companies/{code}/finance",
    response_model=V12Response[FinanceResponseData],
)
async def get_company_finance(
    code: str = Path(..., description="公司代码，如 600518.SH"),
    periods: int = Query(default=8, ge=4, le=20, description="历史期数"),
    statement_scope: str = Query(
        default="parent_company",
        pattern=r"^parent_company$",
        description="报表口径（固定母公司报表，仅支持 parent_company）",
    ),
    as_of: str | None = Query(default=None, description="数据截止日期 YYYYMMDD"),
):
    """财务分析 — 运行 7 条规则并返回真实结果。"""
    trace_id = _trace()
    warnings: list[WarningItem] = []
    data_warnings: list[str] = []

    # 1. 解析公司
    resolved = await _resolve_company(code)
    if resolved is None:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "https://truthnet.dev/errors/company-not-found",
                "title": "Company Not Found",
                "status": 404,
                "detail": f"未找到公司: {code}",
                "error_code": ErrorCode.COMPANY_NOT_COVERED,
                "trace_id": trace_id,
                "recoverable": True,
            },
        )
    entity_id, wind_code, sec_name, industry_l1 = resolved

    # 2. as_of 规范化（YYYYQn → 季末日期）
    from app.domain.finance.period import normalize_period

    as_of_str = normalize_period(as_of) or settings.DEFAULT_AS_OF or "20260331"

    # 3. 运行规则引擎（异常 → unknown，不伪造）
    rules: list[FinanceRuleItem] = []
    # 行业分位（共享服务，与 /benchmarks 同口径）——按 rule_id 分组供规则明细填充
    industry_result = None
    industry_by_rule: dict[str, list] = {}
    if industry_l1:
        try:
            from app.application.services.industry_benchmark_service import (
                compute_industry_percentiles,
            )

            industry_result = compute_industry_percentiles(
                wind_code, industry_l1, as_of_str
            )
            for _p in industry_result["percentiles"]:
                industry_by_rule.setdefault(_p.rule_id or "", []).append(_p)
        except Exception:  # noqa: BLE001 — 行业分位失败不阻塞财务分析
            industry_result = None

    rule_engine_ok = True
    engine_error = ""
    try:
        from app.domain.finance.rule_engine import evaluate_all_rules

        results = evaluate_all_rules(wind_code, as_of_str)
    except Exception as exc:  # noqa: BLE001 — 明确降级，不伪造结果
        rule_engine_ok = False
        engine_error = str(exc)
        results = {}

    # 4. 规则结果 + 统一 Evidence ID（v3.4 方向 A：共享 builder，真实财务字段）
    rule_evidence_map: dict[str, str] = {}
    claim_for_persist: list[dict] = []
    trigger_claim_texts: dict[str, str] = {}
    evidence_for_persist: list[dict] = []
    built_evidence = None
    if rule_engine_ok:
        from app.application.services.finance_evidence import (
            build_finance_rule_evidence_drafts,
            normalize_rule_evidence_id,
        )

        built_evidence = build_finance_rule_evidence_drafts(
            rules=results, wind_code=wind_code, as_of=as_of_str
        )
        # 唯一 drafts（同 ID 只落库一次）+ 规则→证据映射（含共享）
        evidence_for_persist = list(built_evidence["unique_drafts"].values())
        rule_evidence_by_rule = built_evidence["rule_evidence_map"]
        for rid in [f"R{i}" for i in range(1, 8)]:
            r = results.get(rid)
            if r is None:
                continue
            for legacy_ev in r.evidence_ids:
                rule_evidence_map.setdefault(
                    legacy_ev,
                    normalize_rule_evidence_id(legacy_ev, wind_code, as_of_str),
                )
        # 相似指标案例（任务①）：comp_type_code 仅取一次，仅对触发规则透出
        try:
            comp_type_code = fetch_company_field(wind_code, "comp_type_code")
        except Exception:  # noqa: BLE001 — 公司字段读取失败不阻塞财务分析
            comp_type_code = None
        sc_provider = _get_similar_case_provider()
        for rid in [f"R{i}" for i in range(1, 8)]:
            r = results.get(rid)
            if r is None:
                continue
            unified_evidence: list[str] = list(rule_evidence_by_rule.get(rid, []))
            similar_cases = None
            if r.status == "triggered":
                trigger_claim_texts[rid] = (
                    f"{r.rule_name}触发（{r.severity}）：{r.explanation or '财务异常信号'}"
                )
                similar_cases = compute_similar_cases(
                    sc_provider,
                    rule_id=r.rule_id,
                    company_code=wind_code,
                    current=dict(getattr(r, "current", None) or {}),
                    industry=industry_l1,
                    as_of=as_of_str,
                    comp_type_code=comp_type_code,
                )
            rules.append(
                FinanceRuleItem(
                    rule_id=r.rule_id,
                    rule_version=r.rule_version,
                    rule_name=r.rule_name,
                    status=r.status,
                    severity=r.severity,
                    current=r.current,
                    history=r.history,
                    industry=r.industry,
                    industry_metrics=industry_by_rule.get(r.rule_id, []),
                    quality=r.quality,
                    explanation=r.explanation,
                    evidence_ids=unified_evidence,
                    claim_ids=r.claim_ids,
                    warnings=r.warnings,
                    similar_cases=similar_cases,
                )
            )

    # 5. 生成 Claim（触发规则 → 风险信号 Claim）+ 持久化
    claim_ids: list[str] = []
    from app.domain.provenance.id_factory import make_claim_id

    for rid, text in trigger_claim_texts.items():
        cid = make_claim_id(
            turn_id=trace_id,
            company_code=wind_code,
            claim_type="risk_signal",
            rule_id=rid,
            claim_text=text,
            rule_version=settings.RULE_SET_VERSION,
        )
        claim_ids.append(cid)
        evidence_ids = [
            ev for rule in rules if rule.rule_id == rid for ev in rule.evidence_ids
        ]
        claim_for_persist.append(
            {
                "claim_id": cid,
                "text": text,
                "claim_type": "risk_signal",
                "severity": "medium",
                "confidence": 0.7,
                "rule_id": rid,
                "rule_version": settings.RULE_SET_VERSION,
                "verification_status": "verified",
                "company_code": wind_code,
                "module": "finance",
                "evidence_ids": evidence_ids,
            }
        )

    if not rule_engine_ok:
        warnings.append(
            WarningItem(
                code="RULE_ENGINE_ERROR",
                message=f"财务规则引擎执行失败，返回空规则并标记 unknown: {engine_error}",
                module="finance",
                recoverable=True,
            )
        )
        data_warnings.append("RULE_ENGINE_ERROR: 规则引擎失败，未产生规则结果")
        risk_level = "unknown"
    else:
        # 持久化（直接 REST provenance：analysis_runs 载体）
        try:
            from app.application.services.provenance_service import ProvenanceService

            svc = ProvenanceService()
            svc.create_analysis_run(
                trace_id=trace_id,
                endpoint="companies/{code}/finance",
                company_codes=[wind_code],
                period=as_of_str,
            )
            svc.persist_evidence(
                evidence_for_persist, trace_id=trace_id, turn_id=trace_id
            )
            svc.persist_claims(claim_for_persist, trace_id=trace_id, turn_id=trace_id)
        except Exception as exc:  # noqa: BLE001 — 持久化失败不阻塞主流程
            data_warnings.append(f"PROVENANCE_PERSIST_FAILED: {exc}")

        risk_level = _derive_risk_level(rules)

    # 6. 行业对标（真实 industry_benchmarks）
    if industry_result is not None:
        industry_benchmark = IndustryBenchmark(
            industry_l1=industry_l1,
            peer_count=industry_result["peer_count"],
            percentile={
                _p.metric_id: _p.company_percentile
                for _p in industry_result["percentiles"]
                if _p.company_percentile is not None
            },
            warnings=industry_result["warnings"],
        )
    else:
        industry_benchmark = _build_industry_benchmark(
            wind_code, industry_l1, as_of_str
        )

    # 7. periods_available（真实）
    periods_available = _query_periods_available(wind_code, as_of_str)

    # 8. 汇总
    all_evidence_ids = list(
        dict.fromkeys(eid for rule in rules for eid in rule.evidence_ids)
    )
    data_quality = DataQuality(
        periods_available=periods_available,
        periods_requested=periods,
        statement_scope="parent_company",
        warnings=[],
    )

    return V12Response(
        data=FinanceResponseData(
            wind_code=wind_code,
            sec_name=sec_name,
            risk_level=risk_level,
            rules=rules,
            industry_benchmark=industry_benchmark,
            data_quality=data_quality,
            claim_ids=list(dict.fromkeys(claim_ids)),
            evidence_ids=all_evidence_ids,
            warnings=data_warnings,
        ),
        meta=ApiMeta(
            request_id=trace_id,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            data_as_of=as_of_str,
            dataset_version=settings.DATASET_VERSION,
            rule_set_version=settings.RULE_SET_VERSION,
        ),
        warnings=warnings,
    )


def _build_industry_benchmark(
    wind_code: str, industry_l1: str, as_of: str
) -> IndustryBenchmark:
    """从 industry_benchmarks 表读取真实分位 + 计算公司值百分位。"""
    from app.domain.benchmarks.calculator import (
        MIN_PEER_SAMPLE,
        aggregate_stats,
        percentile_rank,
    )
    from app.domain.benchmarks.metric_registry import get_metric
    from app.domain.finance._fetch import _get_engine

    if not industry_l1:
        return IndustryBenchmark(
            industry_l1="",
            peer_count=0,
            percentile={},
            warnings=["INDUSTRY_UNKNOWN: 公司行业未知，无法计算行业分位"],
        )

    engine = _get_engine()
    # 从表读预计算基准（若存在）
    try:
        with engine.connect() as conn:
            rows = (
                conn.execute(
                    (
                        "SELECT metric_id, sample_count, p05, p25, p50, p75, p95 "
                        "FROM industry_benchmarks "
                        "WHERE industry_l1 = :ind AND period = :per "
                        "AND statement_scope = 'parent_company' "
                        "AND dataset_version = :dv"
                    ),
                    {"ind": industry_l1, "per": as_of, "dv": settings.DATASET_VERSION},
                )
                .mappings()
                .fetchall()
            )
    except Exception:  # noqa: BLE001 — 表未就绪时实时计算兜底
        rows = []

    percentile: dict[str, float | None] = {}
    warnings: list[str] = []
    peer_count = 0
    if not rows:
        # 表数据未就绪 → 实时计算（不伪造）
        from app.domain.benchmarks.calculator import compute_metric_values

        for metric_id in (
            "r1_gap",
            "r2_cf_ratio",
            "r3_cash_to_assets",
            "r4_growth_gap",
            "r6_oth_rcv_to_assets",
        ):
            try:
                metric = get_metric(metric_id)
                pairs = compute_metric_values(engine, metric, industry_l1, as_of)
                values = [v for _, v in pairs]
                company_value = next((v for c, v in pairs if c == wind_code), None)
                stats = aggregate_stats(values)
                if (
                    stats["sample_count"] >= MIN_PEER_SAMPLE
                    and company_value is not None
                ):
                    percentile[f"{metric_id}_percentile"] = percentile_rank(
                        company_value, values
                    )
                peer_count = max(peer_count, stats["sample_count"])
            except Exception:  # noqa: BLE001
                continue
        if not percentile:
            warnings.append("行业分位数据尚未就绪（表无记录且实时计算无有效样本）")
    else:
        for row in rows:
            peer_count = max(peer_count, row["sample_count"] or 0)
            if row["sample_count"] and row["sample_count"] >= MIN_PEER_SAMPLE:
                percentile[f"{row['metric_id']}_p50"] = row["p50"]
            else:
                percentile[f"{row['metric_id']}_sample_count"] = row["sample_count"]
        if not percentile:
            warnings.append("行业分位样本不足，未伪造分位值")

    return IndustryBenchmark(
        industry_l1=industry_l1,
        peer_count=peer_count,
        percentile=percentile,
        warnings=warnings,
    )


def _query_periods_available(wind_code: str, as_of: str) -> int:
    """真实可用母公司财务期数。"""
    try:
        from app.domain.finance._fetch import _get_engine
        from sqlalchemy import text

        engine = _get_engine()
        with engine.connect() as conn:
            n = conn.execute(
                text(
                    "SELECT COUNT(DISTINCT report_period) FROM balance_sheet "
                    "WHERE wind_code = :c AND statement_type = '408006000' "
                    "AND report_period <= :asof"
                ),
                {"c": wind_code, "asof": as_of},
            ).scalar()
        return int(n or 0)
    except Exception:  # noqa: BLE001
        return 0


def _derive_risk_level(rules: list[FinanceRuleItem]) -> str:
    """从规则结果推导风险等级（失败/无数据 → unknown）。"""
    if not rules:
        return "unknown"
    triggered = sum(1 for r in rules if r.status == "triggered")
    red = sum(1 for r in rules if r.severity == "red")
    orange = sum(1 for r in rules if r.severity == "orange")
    if red >= 2 or triggered >= 4:
        return "red"
    if red >= 1 or orange >= 2 or triggered >= 2:
        return "orange"
    if orange >= 1 or triggered >= 1:
        return "yellow"
    # 全部 not_triggered 但数据覆盖可能不足 → 不输出绿色
    insufficient = sum(
        1 for r in rules if r.status in ("insufficient_data", "not_applicable")
    )
    if insufficient == len(rules):
        return "unknown"
    return "green"
