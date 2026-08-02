"""跨公司对比路由 — V12 §11.14.

POST /api/v1/comparisons

请求体: {company_codes, period, indicators, statement_scope}
返回: 多公司指标值对比 + 风险摘要。
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


def _trace() -> str:
    return str(uuid.uuid4())


def _resolve_company(code: str) -> tuple[str, str, str] | None:
    """解析公司代码 → (wind_code, sec_name, industry_l1)。"""
    from app.api.v1.routers.companies import _MOCK_COMPANIES

    for c in _MOCK_COMPANIES:
        wc = c["wind_code"]
        if code in (wc, wc.replace(".", "_"), wc.split(".")[0]):
            return (wc, c["sec_name"], c.get("industry_l1", ""))
    return None


@router.post("/comparisons")
async def create_comparison(body: ComparisonRequest):
    """跨公司对比 — 对 2-5 家公司按指标对比，含风险摘要。

    未覆盖的公司跳过并返回 warning。
    """
    trace_id = _trace()
    warnings: list[WarningItem] = []
    data_warnings: list[str] = []

    # 1. 解析所有公司
    company_summaries: list[CompanyRiskSummary] = []
    resolved_map: dict[str, tuple[str, str, str]] = {}

    for code in body.company_codes:
        resolved = _resolve_company(code)
        if resolved is None:
            warnings.append(
                WarningItem(
                    code="COMPANY_NOT_COVERED",
                    message=f"{code} 不在数据覆盖范围，已跳过",
                    module="comparisons",
                    recoverable=True,
                )
            )
            continue
        resolved_map[code] = resolved

    if len(resolved_map) < 2:
        raise HTTPException(
            status_code=400,
            detail={
                "type": "https://truthnet.dev/errors/insufficient-companies",
                "title": "Insufficient Companies",
                "status": 400,
                "detail": (
                    f"需要至少 2 家可对比公司，"
                    f"当前仅 {len(resolved_map)} 家在覆盖范围内"
                ),
                "error_code": "INSUFFICIENT_COMPANIES",
                "trace_id": trace_id,
                "recoverable": True,
            },
        )

    # 2. 收集每家公司风险摘要
    for code, (wind_code, sec_name, industry_l1) in resolved_map.items():
        triggered_rules: list[str] = []
        risk_level = "unknown"
        overall_score = 0.0
        pattern_names: list[str] = []

        try:
            from app.domain.finance.rule_engine import evaluate_all_rules

            as_of = (
                body.period + "01"  # 2026Q2 → 2026Q201 (简化)
                if body.period
                else "20260331"
            )
            results = evaluate_all_rules(wind_code, as_of)
            triggered_rules = [
                rid
                for rid, r in results.items()
                if r.status == "triggered"
            ]
            red_count = sum(
                1 for r in results.values() if r.severity == "red"
            )

            overall_score = min(1.0, red_count * 0.25)
            risk_level = (
                "red"
                if overall_score >= 0.6
                else ("orange" if overall_score >= 0.35 else ("yellow" if overall_score >= 0.15 else "green"))
            )

            # 模式匹配
            if "R1" in triggered_rules and "R2" in triggered_rules:
                pattern_names.append("收入虚增型(P1)")
            if "R3" in triggered_rules and "R6" in triggered_rules:
                pattern_names.append("资金占用型(P2)")
            if "R5" in triggered_rules and "R7" in triggered_rules:
                pattern_names.append("利润调节型(P3)")
        except Exception:
            pass

        company_summaries.append(
            CompanyRiskSummary(
                wind_code=wind_code,
                sec_name=sec_name,
                industry_l1=industry_l1,
                risk_level=risk_level,
                overall_score=round(overall_score, 3),
                triggered_rules=triggered_rules,
                pattern_matches=pattern_names,
            )
        )

    # 3. 构建指标对比
    indicator_compares: list[IndicatorCompare] = []
    indicator_labels = {
        "R1": "应收–营收背离",
        "R2": "现金流–利润背离",
        "R3": "存贷双高",
        "R4": "存货–营收背离",
        "R5": "毛利率/费用率异常",
        "R6": "其他应收款/关联占用",
        "R7": "盈利质量/非经常性依赖",
    }

    for ind in body.indicators:
        companies: list[CompanyIndicator] = []

        for code, (wind_code, sec_name, _) in resolved_map.items():
            try:
                from app.domain.finance.rule_engine import evaluate_all_rules

                results = evaluate_all_rules(wind_code, "20260331")
                r = results.get(ind)
                if r is None:
                    companies.append(
                        CompanyIndicator(
                            wind_code=wind_code,
                            sec_name=sec_name,
                            status="not_applicable",
                        )
                    )
                    continue

                # 提取第一个 current 指标值
                value = None
                unit = ""
                if r.current:
                    first_key = next(iter(r.current))
                    metric = r.current[first_key]
                    value = metric.get("value") if isinstance(metric, dict) else None
                    unit = metric.get("unit", "") if isinstance(metric, dict) else ""

                companies.append(
                    CompanyIndicator(
                        wind_code=wind_code,
                        sec_name=sec_name,
                        value=value,
                        unit=unit,
                        severity=r.severity,
                        status=r.status,
                    )
                )
            except Exception:
                companies.append(
                    CompanyIndicator(
                        wind_code=wind_code,
                        sec_name=sec_name,
                        status="insufficient_data",
                    )
                )

        indicator_compares.append(
            IndicatorCompare(
                indicator=ind,
                label=indicator_labels.get(ind, ind),
                companies=companies,
            )
        )

    return V12Response(
        data=ComparisonsResponseData(
            period=body.period,
            statement_scope=body.statement_scope,
            companies=company_summaries,
            indicators=indicator_compares,
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
