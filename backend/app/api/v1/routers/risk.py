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
    DerivationChain,
    MitigatingFactor,
    PatternMatch,
    RiskEvidence,
    RiskResponseData,
    RiskTag,
    SubScore,
)
from app.core.config import settings

router = APIRouter(tags=["risk"])

# 8.11：证据摘要回查批量窗口（禁止逐条 N+1）
_EVIDENCE_QUERY_BATCH = 500


def _build_risk_evidence(out) -> list[RiskEvidence]:
    """真实证据映射：优先服务层结构化证据；旧输出回查 evidence_refs。

    找不到记录 → source_type="unknown"，禁止伪造 "risk"。
    """
    structured = getattr(out, "evidence", []) or []
    if structured:
        return [
            RiskEvidence(
                evidence_id=e.evidence_id,
                source_type=(e.source_type or "").strip() or "unknown",
                # 8.11 P1（审查）：不得把全部 claim 关联到每条无直接映射的
                # Evidence——无映射时保持空列表（关系过度断言）
                claim_ids=e.claim_ids or [],
                summary=(e.summary or "").strip() or "未知来源",
            )
            for e in structured
        ]
    meta = _fetch_evidence_meta(out.evidence_ids or [])
    return [
        RiskEvidence(
            evidence_id=eid,
            source_type=(str(meta[eid].get("source_type") or "").strip() or "unknown")
            if eid in meta
            else "unknown",
            # 8.11 P1（审查）：旧输出兼容分支同样不得把全部 Claim 挂到
            # 每条 Evidence——无法确定精确映射时保持空列表
            claim_ids=[],
            summary=_summary_from_meta(meta.get(eid)),
        )
        for eid in (out.evidence_ids or [])
    ]


def _trace() -> str:
    return str(uuid.uuid4())


_engine = None


def _get_engine():
    """惰性缓存 MySQL engine（与 sessions.py 同模式）。"""
    global _engine
    if _engine is None:
        from sqlalchemy import create_engine

        url = (
            f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
            f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
        )
        _engine = create_engine(url, echo=False)
    return _engine


def _summary_from_meta(meta: dict | None) -> str:
    """从 evidence_refs 行构造摘要：title → excerpt → 字段 期次: 值。"""
    if not meta:
        return "未知来源"
    title = str(meta.get("source_title") or "").strip()
    if title:
        return title
    excerpt = str(meta.get("source_excerpt") or "").strip()
    if excerpt:
        return excerpt
    field_path = str(meta.get("field_path") or "").strip()
    period = str(meta.get("period") or "").strip()
    value = meta.get("value")
    value_str = "" if value is None else str(value).strip()
    if field_path or period or value_str:
        return f"{field_path} {period}: {value_str}".strip(" :")
    return "未知来源"


def _fetch_evidence_meta(eids: list[str]) -> dict[str, dict]:
    """批量回查 evidence_refs 真实类型与摘要（500 分批，禁止 N+1）。"""
    if not eids:
        return {}
    from sqlalchemy import text

    meta: dict[str, dict] = {}
    unique = list(dict.fromkeys(eids))
    # 8.11 P1（审查）：连接用 with 关闭，避免兼容回查泄漏连接
    with _get_engine().connect() as conn:
        for i in range(0, len(unique), _EVIDENCE_QUERY_BATCH):
            chunk = unique[i : i + _EVIDENCE_QUERY_BATCH]
            placeholders = ", ".join(f":e{i}" for i in range(len(chunk)))
            rows = (
                conn.execute(
                    text(
                        "SELECT evidence_id, source_type, field_path, period, value, "
                        "source_title, source_excerpt "
                        f"FROM evidence_refs WHERE evidence_id IN ({placeholders})"
                    ),
                    {f"e{i}": c for i, c in enumerate(chunk)},
                )
                .mappings()
                .all()
            )
            for r in rows:
                meta[str(r["evidence_id"])] = dict(r)
    return meta


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
                    phase=m.phase,
                    alternative_explanation=m.alternative_explanation,
                    regulatory_hint=m.regulatory_hint,
                )
                for m in out.pattern_matches
            ],
            derivation_chains=[
                DerivationChain.model_validate(chain.model_dump())
                for chain in out.derivation_chains
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
            evidence=_build_risk_evidence(out),
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
