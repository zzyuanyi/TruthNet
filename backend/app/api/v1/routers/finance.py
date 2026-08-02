"""财务分析路由 — V12 §11.10.

GET /api/v1/companies/{code}/finance?periods=8&statement_scope=parent_company

返回 risk_level、rules、industry_benchmark、data_quality、claim_ids、evidence_ids。
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Path, Query

from app.api.v1.schemas.common import ApiMeta, V12Response, WarningItem
from app.api.v1.schemas.finance import (
    DataQuality,
    FinanceResponseData,
    FinanceRuleItem,
    IndustryBenchmark,
)
from app.core.config import settings

router = APIRouter(tags=["finance"])


def _trace() -> str:
    return str(uuid.uuid4())


def _resolve_company(code: str) -> tuple[str, str, str] | None:
    """解析公司代码 → (entity_id, wind_code, sec_name)。"""
    from app.api.v1.routers.companies import _MOCK_COMPANIES

    for c in _MOCK_COMPANIES:
        wc = c["wind_code"]
        # 支持 600518、600518.SH、600518_SH 多种格式
        if code in (wc, wc.replace(".", "_"), wc.split(".")[0]):
            return (c["entity_id"], wc, c["sec_name"])
    return None


@router.get("/companies/{code}/finance")
async def get_company_finance(
    code: str = Path(..., description="公司代码，如 600518.SH"),
    periods: int = Query(default=8, ge=4, le=20, description="历史期数"),
    statement_scope: str = Query(
        default="parent_company",
        pattern=r"^(parent_company|consolidated|auto)$",
        description="报表口径",
    ),
    as_of: str | None = Query(default=None, description="数据截止日期 (YYYYMMDD)"),
):
    """财务分析 — 运行 7 条规则并返回结果。

    返回 R1-R7 状态、当前值、历史序列、行业分位、数据质量。
    """
    trace_id = _trace()
    warnings: list[WarningItem] = []
    data_warnings: list[str] = []

    # 1. 解析公司
    resolved = _resolve_company(code)
    if resolved is None:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "https://truthnet.dev/errors/company-not-found",
                "title": "Company Not Found",
                "status": 404,
                "detail": f"未找到公司: {code}",
                "error_code": "COMPANY_NOT_FOUND",
                "trace_id": trace_id,
                "recoverable": True,
            },
        )

    entity_id, wind_code, sec_name = resolved
    as_of_str = as_of or settings.DEFAULT_AS_OF or "20260331"

    # 2. 运行规则引擎（full profile 真实查询，lite profile mock）
    rules: list[FinanceRuleItem] = []
    try:
        from app.domain.finance.rule_engine import evaluate_all_rules

        results = evaluate_all_rules(wind_code, as_of_str)
        for rid in [f"R{i}" for i in range(1, 8)]:
            r = results.get(rid)
            if r is None:
                rules.append(
                    FinanceRuleItem(
                        rule_id=rid,
                        rule_name="",
                        status="insufficient_data",
                        explanation="规则未执行",
                    )
                )
                continue
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
                    quality=r.quality,
                    explanation=r.explanation,
                    evidence_ids=r.evidence_ids,
                    claim_ids=r.claim_ids,
                    warnings=r.warnings,
                )
            )
    except Exception as exc:
        # 规则引擎不可用时降级为 mock
        warnings.append(
            WarningItem(
                code="RULE_ENGINE_DEGRADED",
                message=f"规则引擎不可用，返回空规则列表: {exc}",
                module="finance",
                recoverable=True,
            )
        )

    # 3. 行业对标（Phase C 依赖数据组任务3）
    industry_benchmark = IndustryBenchmark(
        industry_l1=(
            next(
                (
                    c["industry_l1"]
                    for c in _MOCK_COMPANIES
                    if c["wind_code"] == wind_code
                ),
                "",
            )
            if "_MOCK_COMPANIES" in dir()
            else ""
        ),
        peer_count=0,
        warnings=["行业分位数据尚未就绪（Phase C 数据组任务3）"],
    )
    if industry_benchmark.warnings:
        data_warnings.extend(industry_benchmark.warnings)

    # 4. 数据质量
    data_quality = DataQuality(
        periods_available=0,  # 由规则引擎实际查询后填充
        periods_requested=periods,
        statement_scope=statement_scope,
    )

    # 5. 汇总 evidence_ids 和 claim_ids
    all_evidence_ids: list[str] = []
    all_claim_ids: list[str] = []
    for rule in rules:
        all_evidence_ids.extend(rule.evidence_ids)
        all_claim_ids.extend(rule.claim_ids)

    return V12Response(
        data=FinanceResponseData(
            wind_code=wind_code,
            sec_name=sec_name,
            risk_level=_derive_risk_level(rules),
            rules=rules,
            industry_benchmark=industry_benchmark,
            data_quality=data_quality,
            claim_ids=list(dict.fromkeys(all_claim_ids)),
            evidence_ids=list(dict.fromkeys(all_evidence_ids)),
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


def _derive_risk_level(rules: list[FinanceRuleItem]) -> str:
    """从规则结果推导风险等级。"""
    triggered = sum(1 for r in rules if r.status == "triggered")
    red = sum(1 for r in rules if r.severity == "red")
    orange = sum(1 for r in rules if r.severity == "orange")
    if red >= 2 or triggered >= 4:
        return "red"
    if red >= 1 or orange >= 2 or triggered >= 2:
        return "orange"
    if orange >= 1 or triggered >= 1:
        return "yellow"
    return "green"
