"""综合风险路由 — V12 §11.12.

GET /api/v1/companies/{code}/risk?as_of=2026-06-30

返回综合分、等级、分项贡献、风险标签、模式匹配、置信度、
数据覆盖、缓解因素和证据。
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Path, Query

from app.api.v1.schemas.common import ApiMeta, V12Response, WarningItem
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


def _resolve_company(code: str) -> tuple[str, str] | None:
    from app.api.v1.routers.companies import _MOCK_COMPANIES

    for c in _MOCK_COMPANIES:
        wc = c["wind_code"]
        if code in (wc, wc.replace(".", "_"), wc.split(".")[0]):
            return (wc, c["sec_name"])
    return None


@router.get("/companies/{code}/risk")
async def get_company_risk(
    code: str = Path(..., description="公司代码，如 600518.SH"),
    as_of: str | None = Query(default=None, description="数据截止日期 (YYYY-MM-DD)"),
):
    """综合风险评分 — 融合财务+股权+事件+外部数据四维度。

    返回综合分、分项分、等级、策略版本、数据覆盖、置信度、
    关键贡献因素、缓解因素、证据。
    """
    trace_id = _trace()
    warnings: list[WarningItem] = []

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

    wind_code, sec_name = resolved
    as_of_str = as_of or f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"

    # 2. 收集各模块数据
    sub_scores: list[SubScore] = []
    risk_tags: list[RiskTag] = []
    pattern_matches: list[PatternMatch] = []
    coverage = DataCoverage()
    mitigating_factors: list[MitigatingFactor] = []
    evidence: list[RiskEvidence] = []

    # 2a. 财务维度
    finance_available = False
    try:
        from app.domain.finance.rule_engine import evaluate_all_rules

        results = evaluate_all_rules(wind_code, as_of_str.replace("-", ""))
        triggered = [rid for rid, r in results.items() if r.status == "triggered"]
        red_count = sum(1 for r in results.values() if r.severity == "red")
        orange_count = sum(1 for r in results.values() if r.severity == "orange")

        finance_score = min(1.0, (red_count * 0.25 + orange_count * 0.15))
        finance_available = True

        sub_scores.append(
            SubScore(
                dimension="finance",
                label="财务勾稽",
                score=round(finance_score, 3),
                weight=0.40,
                contribution=round(finance_score * 0.40, 3),
                status="success",
            )
        )
        coverage.finance = True

        if triggered:
            risk_tags.append(
                RiskTag(
                    tag=f"财务异常: {', '.join(triggered)}",
                    category="finance",
                    confidence=min(0.9, 0.5 + len(triggered) * 0.1),
                )
            )

        # 造假模式匹配（Phase C 会议决议：集成手法库）
        pattern_map = {
            "P1": (["R1", "R2"], "收入虚增型"),
            "P2": (["R3", "R6"], "资金占用型"),
            "P3": (["R5", "R7"], "利润调节型"),
            "P4": (["R1", "R4", "R2"], "资产虚增型"),
            "P5": (["R1", "R2", "R3", "R4"], "综合粉饰型"),
        }
        for pid, (rule_ids, name) in pattern_map.items():
            matched = [r for r in rule_ids if r in triggered]
            if len(matched) >= 2:
                pattern_matches.append(
                    PatternMatch(
                        pattern_id=pid,
                        pattern_name=name,
                        triggered_rules=matched,
                        confidence=(
                            "high"
                            if len(matched) >= len(rule_ids)
                            else "medium"
                        ),
                        reasoning=f"{len(matched)}/{len(rule_ids)} 条规则触发: {', '.join(rule_ids)}",
                    )
                )
    except Exception as exc:
        sub_scores.append(
            SubScore(
                dimension="finance",
                label="财务勾稽",
                score=0.0,
                weight=0.40,
                contribution=0.0,
                status="failed",
                warning=str(exc),
            )
        )
        warnings.append(
            WarningItem(
                code="FINANCE_MODULE_FAILED",
                message=f"财务模块执行失败: {exc}",
                module="finance",
                recoverable=True,
            )
        )

    # 2b. 股权维度
    equity_available = False
    try:
        from app.infrastructure.graph.networkx.equity_graph import NetworkXEquityGraph

        g = NetworkXEquityGraph()
        graph = await g.get_graph(wind_code.split(".")[0], depth=5)

        chain_count = len(graph.control_chains) if graph else 0
        # 多层控制链 + 自然人节点 → 风险信号
        equity_score = (
            0.3 if chain_count > 2 else (0.1 if chain_count > 0 else 0.0)
        )
        equity_available = True

        sub_scores.append(
            SubScore(
                dimension="equity",
                label="股权穿透",
                score=round(equity_score, 3),
                weight=0.30,
                contribution=round(equity_score * 0.30, 3),
                status="success" if graph else "partial",
            )
        )
        coverage.equity = True

        if chain_count > 2:
            risk_tags.append(
                RiskTag(
                    tag=f"多层控制链: {chain_count} 条路径",
                    category="equity",
                    confidence=0.7,
                )
            )
    except Exception as exc:
        sub_scores.append(
            SubScore(
                dimension="equity",
                label="股权穿透",
                score=0.0,
                weight=0.30,
                contribution=0.0,
                status="failed",
                warning=str(exc),
            )
        )
        warnings.append(
            WarningItem(
                code="EQUITY_MODULE_FAILED",
                message=f"股权模块执行失败: {exc}",
                module="equity",
                recoverable=True,
            )
        )

    # 2c. 事件维度
    try:
        from app.domain.finance._fetch import _get_engine

        engine = _get_engine()
        with engine.connect() as conn:
            from sqlalchemy import text

            row = conn.execute(
                text(
                    "SELECT COUNT(*) as cnt FROM announcements "
                    "WHERE wind_code = :code"
                ),
                {"code": wind_code},
            ).fetchone()
            ann_count = row[0] if row else 0

        if ann_count > 0:
            # 有公告 → 查询负面占比
            from app.domain.events.fcode_taxonomy import classify_sentiment

            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        "SELECT fcode FROM announcements "
                        "WHERE wind_code = :code"
                    ),
                    {"code": wind_code},
                ).fetchall()

            negative_count = 0
            for (fcode_raw,) in rows:
                sentiment, _, _ = classify_sentiment(
                    str(fcode_raw) if fcode_raw else ""
                )
                if sentiment == "negative":
                    negative_count += 1
            neg_ratio = negative_count / len(rows) if rows else 0.0

            events_score = min(1.0, neg_ratio * 3)
            sub_scores.append(
                SubScore(
                    dimension="events",
                    label="舆情事件",
                    score=round(events_score, 3),
                    weight=0.20,
                    contribution=round(events_score * 0.20, 3),
                    status="success",
                )
            )
            coverage.events = True
        else:
            sub_scores.append(
                SubScore(
                    dimension="events",
                    label="舆情事件",
                    score=0.0,
                    weight=0.20,
                    contribution=0.0,
                    status="skipped",
                    warning="无公告数据覆盖",
                )
            )
    except Exception as exc:
        sub_scores.append(
            SubScore(
                dimension="events",
                label="舆情事件",
                score=0.0,
                weight=0.20,
                contribution=0.0,
                status="failed",
                warning=str(exc),
            )
        )

    # 2d. 外部/基准维度
    sub_scores.append(
        SubScore(
            dimension="external",
            label="行业基准",
            score=0.0,
            weight=0.10,
            contribution=0.0,
            status="skipped",
            warning="行业分位数据尚未就绪",
        )
    )

    # 3. 计算综合分
    overall_score = sum(s.contribution for s in sub_scores)

    # 4. 数据覆盖
    coverage.benchmarks = False
    coverage.missing_modules = [
        s.dimension
        for s in sub_scores
        if s.status in ("failed", "skipped") and s.dimension != "external"
    ]
    covered = sum(
        [coverage.finance, coverage.equity, coverage.events, coverage.benchmarks]
    )
    coverage.coverage_ratio = covered / 4.0

    # 5. 置信度（基于数据覆盖 + 模块状态）
    success_count = sum(1 for s in sub_scores if s.status == "success")
    partial_count = sum(1 for s in sub_scores if s.status == "partial")
    confidence = min(0.95, (success_count * 0.25 + partial_count * 0.12))

    # 6. 缓解因素
    if not coverage.events:
        mitigating_factors.append(
            MitigatingFactor(
                factor="无公告数据 → 舆情维度降权，不影响财务勾稽判定",
                category="data_coverage",
                weight=0.3,
            )
        )
    if not coverage.benchmarks:
        mitigating_factors.append(
            MitigatingFactor(
                factor="行业分位未就绪 → 使用通用阈值替代",
                category="data_coverage",
                weight=0.2,
            )
        )

    # 7. 证据
    if finance_available:
        evidence.append(
            RiskEvidence(
                evidence_id=f"evidence_{wind_code}_finance",
                source_type="rule_engine",
                summary="7 条财务反欺诈规则计算",
            )
        )
    if equity_available:
        evidence.append(
            RiskEvidence(
                evidence_id=f"evidence_{wind_code}_equity",
                source_type="equity_graph",
                summary="股权穿透分析",
            )
        )

    return V12Response(
        data=RiskResponseData(
            wind_code=wind_code,
            sec_name=sec_name,
            as_of=as_of_str,
            overall_score=round(overall_score, 3),
            risk_level=_derive_risk_level(overall_score),
            sub_scores=sub_scores,
            risk_tags=risk_tags,
            pattern_matches=pattern_matches,
            confidence=round(confidence, 3),
            data_coverage=coverage,
            mitigating_factors=mitigating_factors,
            strategy_version="1.0.0",
            rule_set_version=settings.RULE_SET_VERSION,
            evidence=evidence,
            warnings=[w.message for w in warnings],
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


def _derive_risk_level(score: float) -> str:
    """综合分 → 风险等级。"""
    if score >= 0.60:
        return "red"
    if score >= 0.35:
        return "orange"
    if score >= 0.15:
        return "yellow"
    return "green"
