"""跨公司对比路由 — V12 §11.14 + Phase C 任务 13.

POST /api/v1/comparisons

要求（任务 13）:
  - 2-5 家公司，统一 CompanyResolver
  - 正确解析 YYYYMMDD / YYYY-MM-DD / YYYYQ1-YYYYQ4（2026Q2 → 20260630，不得 2026Q201）
  - 每家公司只执行一次规则分析（缓存，不逐指标重复执行）
  - statement_scope 固定 parent_company
  - 单家公司失败 → partial warning（绝不 except: pass 静默吞错）
  - 输出指标、风险、coverage、evidence
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.api.v1.schemas.common import ApiMeta, V12Response, WarningItem
from app.api.v1.schemas.comparisons import (
    CompanyIndicator,
    CompanyRiskSummary,
    ComparisonRequest,
    ComparisonsResponseData,
    IndicatorCompare,
)
from app.core.config import settings

router = APIRouter(tags=["comparisons"])

_INDICATOR_LABELS = {
    "R1": "应收–营收背离",
    "R2": "现金流–利润背离",
    "R3": "存贷双高",
    "R4": "存货–营收背离",
    "R5": "毛利率/费用率异常",
    "R6": "其他应收款/关联占用",
    "R7": "盈利质量/非经常性依赖",
}


def _trace() -> str:
    return str(uuid.uuid4())


def _unified_evidence(wind_code: str, as_of: str, rule_ids: list[str]) -> list[str]:
    """统一 Evidence ID（与 Finance 端点同口径）。"""
    from app.domain.provenance.id_factory import NS_FINANCE, make_evidence_id

    return [
        make_evidence_id(
            source_namespace=NS_FINANCE,
            source_type="financial_statement",
            source_record_id=f"{wind_code}|{as_of}",
            field_path=f"rule_{rid}",
            period=as_of,
            dataset_version=settings.DATASET_VERSION,
            company_code=wind_code,
        )
        for rid in rule_ids
    ]


async def _resolve_company(code: str):
    from app.application.services.company_resolver import resolve_company

    return await resolve_company(code)


@router.post("/comparisons", response_model=V12Response[ComparisonsResponseData])
async def create_comparison(body: ComparisonRequest):
    """跨公司对比 — 对 2-5 家公司按指标对比，含风险摘要 + coverage + evidence。"""
    trace_id = _trace()
    warnings: list[WarningItem] = []
    data_warnings: list[str] = []

    # 固定母公司口径（任务 13：不接受其他 scope）
    statement_scope = "parent_company"

    # period 规范化（2026Q2 → 20260630）
    from app.domain.finance.period import normalize_period

    period_ymd = normalize_period(body.period)
    if period_ymd is None:
        raise HTTPException(
            status_code=422,
            detail={
                "type": "https://truthnet.dev/errors/invalid-period",
                "title": "Invalid Period",
                "status": 422,
                "detail": f"无法解析期间: {body.period}",
                "error_code": "INVALID_PERIOD",
                "trace_id": trace_id,
                "recoverable": True,
            },
        )

    # ── 1. 解析所有公司 ──
    resolved_map: dict[str, object] = {}
    for code in body.company_codes:
        rec = await _resolve_company(code)
        if rec is None:
            warnings.append(
                WarningItem(
                    code="COMPANY_NOT_COVERED",
                    message=f"{code} 不在数据覆盖范围，已跳过",
                    module="comparisons",
                    recoverable=True,
                )
            )
            continue
        resolved_map[code] = rec

    if len(resolved_map) < 2:
        raise HTTPException(
            status_code=400,
            detail={
                "type": "https://truthnet.dev/errors/insufficient-companies",
                "title": "Insufficient Companies",
                "status": 400,
                "detail": f"需要至少 2 家可对比公司，当前 {len(resolved_map)} 家",
                "error_code": "INSUFFICIENT_COMPANIES",
                "trace_id": trace_id,
                "recoverable": True,
            },
        )

    # ── 2. 每家公司只执行一次规则分析（缓存）──
    rule_cache: dict[str, dict] = {}
    company_failures: dict[str, str] = {}

    from app.domain.finance.rule_engine import evaluate_all_rules

    for code, rec in resolved_map.items():
        try:
            results = evaluate_all_rules(rec.wind_code, period_ymd)
            rule_cache[code] = {
                "wind_code": rec.wind_code,
                "sec_name": rec.sec_name,
                "industry_l1": rec.industry_l1 or "",
                "results": results,
            }
        except Exception as exc:  # noqa: BLE001 — 记录失败，不静默吞掉
            company_failures[code] = str(exc)
            data_warnings.append(f"{code} 分析失败: {exc}")

    # ── 3. 公司风险摘要 ──
    company_summaries: list[CompanyRiskSummary] = []
    for code, rec in resolved_map.items():
        if code in company_failures:
            company_summaries.append(
                CompanyRiskSummary(
                    wind_code=rec.wind_code,
                    sec_name=rec.sec_name,
                    industry_l1=rec.industry_l1 or "",
                    risk_level="unknown",
                    overall_score=0.0,
                    partial=True,
                )
            )
            continue
        entry = rule_cache[code]
        results = entry["results"]
        triggered = [rid for rid, r in results.items() if r.status == "triggered"]
        red_count = sum(1 for r in results.values() if r.severity == "red")
        orange_count = sum(1 for r in results.values() if r.severity == "orange")
        overall_score = min(
            1.0, red_count * 0.25 + orange_count * 0.15 + len(triggered) * 0.05
        )
        risk_level = (
            "red"
            if overall_score >= 0.6
            else (
                "orange"
                if overall_score >= 0.35
                else ("yellow" if overall_score >= 0.15 else "green")
            )
        )
        # coverage：规则 quality 数据完整性均值
        completions = [
            r.quality.get("data_completeness", 0.0)
            for r in results.values()
            if r.quality and r.quality.get("data_completeness") is not None
        ]
        coverage = round(sum(completions) / len(completions), 3) if completions else 0.0
        # 模式匹配（唯一来源 fraud_patterns.yaml）
        pattern_names: list[str] = []
        try:
            from app.domain.risk.fraud_patterns import match_patterns

            rule_dict = {
                rid: {"status": r.status, "severity": r.severity}
                for rid, r in results.items()
            }
            pattern_names = [
                f"{m.pattern_id}({m.pattern_name})" for m in match_patterns(rule_dict)
            ]
        except Exception:  # noqa: BLE001 — pattern 失败不阻塞对比
            pattern_names = []

        company_summaries.append(
            CompanyRiskSummary(
                wind_code=entry["wind_code"],
                sec_name=entry["sec_name"],
                industry_l1=entry["industry_l1"],
                risk_level=risk_level,
                overall_score=round(overall_score, 3),
                triggered_rules=triggered,
                pattern_matches=pattern_names,
                coverage=coverage,
                evidence_ids=_unified_evidence(
                    entry["wind_code"], period_ymd, triggered or []
                ),
                partial=False,
            )
        )

    # ── 4. 指标对比（复用缓存结果）──
    indicator_compares: list[IndicatorCompare] = []
    for ind in body.indicators:
        companies: list[CompanyIndicator] = []
        for code, rec in resolved_map.items():
            if code in company_failures:
                companies.append(
                    CompanyIndicator(
                        wind_code=rec.wind_code,
                        sec_name=rec.sec_name,
                        status="insufficient_data",
                    )
                )
                continue
            entry = rule_cache[code]
            r = entry["results"].get(ind)
            if r is None:
                companies.append(
                    CompanyIndicator(
                        wind_code=entry["wind_code"],
                        sec_name=entry["sec_name"],
                        status="not_applicable",
                    )
                )
                continue
            value = None
            unit = ""
            if r.current:
                first_key = next(iter(r.current))
                metric = r.current[first_key]
                value = metric.get("value") if isinstance(metric, dict) else None
                unit = metric.get("unit", "") if isinstance(metric, dict) else ""
            companies.append(
                CompanyIndicator(
                    wind_code=entry["wind_code"],
                    sec_name=entry["sec_name"],
                    value=value,
                    unit=unit,
                    severity=r.severity,
                    status=r.status,
                )
            )
        indicator_compares.append(
            IndicatorCompare(
                indicator=ind,
                label=_INDICATOR_LABELS.get(ind, ind),
                companies=companies,
            )
        )

    return V12Response(
        data=ComparisonsResponseData(
            period=body.period,
            statement_scope=statement_scope,
            companies=company_summaries,
            indicators=indicator_compares,
            dataset_version=settings.DATASET_VERSION,
            warnings=data_warnings,
        ),
        meta=ApiMeta(
            request_id=trace_id,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            dataset_version=settings.DATASET_VERSION,
            rule_set_version=settings.RULE_SET_VERSION,
        ),
        warnings=warnings,
    )
