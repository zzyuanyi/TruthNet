"""综合风险路由 — V12 §11.12 + Phase C 任务 11.

GET /api/v1/companies/{code}/risk?as_of=2026-06-30

Router 职责（任务 11 验收）:
  - 参数校验
  - CompanyResolver
  - 调用 RiskScoringService（assemble_and_score）
  - DTO 映射
  - 错误信封

Router 禁止: 查四张表 / 重算规则 / new NetworkX / 硬编码 pattern / 临时 evidence ID。
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Path, Query

from app.api.v1.schemas.common import ApiMeta, V12Response, WarningItem
from app.core.errors import ErrorCode
from app.api.v1.schemas.risk import (
    DataCoverage,
    MitigatingFactor,
    PatternMatch,
    RiskEvidence,
    RiskResponseData,
    RiskTag,
    SubScore,
)
from app.core.config import settings

router = APIRouter(tags=["risk"])


def _trace() -> str:
    return str(uuid.uuid4())


@router.get(
    "/companies/{code}/risk",
    response_model=V12Response[RiskResponseData],
)
async def get_company_risk(
    code: str = Path(..., description="公司代码，如 600518.SH"),
    as_of: str | None = Query(default=None, description="数据截止日期 (YYYY-MM-DD)"),
):
    """综合风险评分 — 融合财务+股权+事件+行业基准四维度。"""
    trace_id = _trace()
    warnings: list[WarningItem] = []

    # as_of 规范化（支持 YYYYMMDD / YYYY-MM-DD / YYYYQn）
    from app.domain.finance.period import normalize_period

    as_of_ymd = normalize_period(as_of) or settings.DEFAULT_AS_OF or "20260331"

    # ── CompanyResolver + RiskScoringService（Router 不收集模块数据）──
    try:
        from app.application.services.risk_scoring_service import assemble_and_score

        out = await assemble_and_score(
            code,
            as_of_ymd,
            rule_set_version=settings.RULE_SET_VERSION,
            dataset_version=settings.DATASET_VERSION,
        )
    except ValueError as exc:
        # 公司不存在
        raise HTTPException(
            status_code=404,
            detail={
                "type": "https://truthnet.dev/errors/company-not-found",
                "title": "Company Not Found",
                "status": 404,
                "detail": str(exc),
                "error_code": ErrorCode.COMPANY_NOT_COVERED,
                "trace_id": trace_id,
                "recoverable": True,
            },
        )
    except Exception as exc:  # noqa: BLE001 — 明确错误信封
        raise HTTPException(
            status_code=500,
            detail={
                "type": "https://truthnet.dev/errors/risk-scoring-failed",
                "title": "Risk Scoring Failed",
                "status": 500,
                "detail": f"风险评分执行失败: {exc}",
                "error_code": "RISK_SCORING_FAILED",
                "trace_id": trace_id,
                "recoverable": True,
            },
        )

    # ── DTO 映射 ──
    data_warnings = list(out.warnings)
    coverage = DataCoverage(
        finance=out.data_coverage.finance,
        equity=out.data_coverage.equity,
        events=out.data_coverage.events,
        benchmarks=out.data_coverage.benchmarks,
        coverage_ratio=out.data_coverage.coverage_ratio,
        missing_modules=out.data_coverage.missing_modules,
    )
    return V12Response(
        data=RiskResponseData(
            wind_code=out.wind_code,
            sec_name=out.sec_name,
            as_of=out.as_of,
            overall_score=out.overall_score,
            risk_level=out.risk_level,
            sub_scores=[
                SubScore(
                    dimension=s.dimension,
                    label=s.label,
                    score=s.score,
                    weight=s.weight,
                    contribution=s.contribution,
                    status=s.status,
                )
                for s in out.sub_scores
            ],
            risk_tags=[
                RiskTag(
                    tag=f"综合风险 {out.risk_level}",
                    category="overall",
                    confidence=out.confidence,
                )
            ],
            pattern_matches=[
                PatternMatch(
                    pattern_id=m.pattern_id,
                    pattern_name=m.pattern_name,
                    triggered_rules=m.triggered_rules,
                    confidence=m.confidence,
                    reasoning=m.reasoning,
                )
                for m in out.pattern_matches
            ],
            confidence=out.confidence,
            data_coverage=coverage,
            mitigating_factors=[
                MitigatingFactor(
                    factor=f,
                    category="data_coverage",
                    weight=0.0,
                )
                for f in out.mitigating_factors
            ],
            strategy_version=out.strategy_version,
            rule_set_version=out.rule_set_version,
            evidence=[
                RiskEvidence(
                    evidence_id=eid,
                    source_type="risk",
                    claim_ids=out.claim_ids,
                    summary="综合风险评分引用证据",
                )
                for eid in out.evidence_ids
            ],
            warnings=data_warnings,
        ),
        meta=ApiMeta(
            request_id=trace_id,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            data_as_of=as_of_ymd,
            dataset_version=settings.DATASET_VERSION,
            rule_set_version=settings.RULE_SET_VERSION,
        ),
        warnings=warnings,
    )
