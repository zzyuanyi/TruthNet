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

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Path, Query

from app.api.v1.schemas.common import ApiMeta, V12Response, WarningItem
from app.core.errors import ErrorCode
from app.api.v1.schemas.risk import (
    DataCoverage,
    DerivationChain,
    FraudConclusionData,
    ImpactAdviceData,
    ImpactAdviceSegmentData,
    MitigatingFactor,
    PatternMatch,
    RiskEvidence,
    RiskResponseData,
    RiskTag,
    SubScore,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

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


def _get_engine():
    """8/19 全面审查：改用完整 profile key + 切 profile 即 dispose 旧 Engine。

    原实现以模块级单例缓存且只支持 mysql，进程内切库后复用旧库 Engine。"""
    from app.domain.finance._engine_utils import get_engine

    return get_engine()


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
    # 未传时传空串，由 assemble_and_score 在公司解析后从库内推导真实截止期
    from app.domain.finance.period import normalize_period

    as_of_ymd = normalize_period(as_of) or ""

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


def _build_fraud_conclusion_input(out) -> tuple[str, str, list[str], int]:
    """把 RiskOutput 组装成「锁定输入」+ 确定性模板结论。

    返回 (locked_text, template_conclusion, pattern_names, evidence_count)。
    """
    patterns: list[str] = []
    for m in out.pattern_matches or []:
        name = getattr(m, "pattern_name", "") or ""
        conf = getattr(m, "confidence", "") or ""
        rules = getattr(m, "triggered_rules", []) or []
        patterns.append(f"{name}（{conf}，规则 {','.join(rules)}）")

    rule_lines: list[str] = []
    evidence_ids: set[str] = set()
    for chain in out.derivation_chains or []:
        if getattr(chain, "conclusion_type", "") != "rule_trigger":
            continue
        conclusion = getattr(chain, "conclusion", "") or ""
        expl = ""
        for sig in getattr(chain, "signals", []) or []:
            expl = getattr(sig, "explanation", "") or ""
            if expl:
                break
        evidence_ids.update(getattr(chain, "evidence_ids", []) or [])
        rule_lines.append(f"- {conclusion}：{expl}")

    locked = (
        f"公司：{out.sec_name}\n"
        f"综合风险等级：{out.risk_level}（{out.overall_score:.3f} 分）\n"
        f"命中造假模式：{'; '.join(patterns) if patterns else '无'}\n"
        f"触发规则证据：\n" + "\n".join(rule_lines)
    )

    # 确定性模板结论（LLM 失败/关闭时的兜底）
    risk_cn = {
        "red": "高危",
        "orange": "中高危",
        "yellow": "中等",
        "green": "正常",
        "blue": "低风险",
        "unknown": "数据不足",
    }.get(out.risk_level, out.risk_level)
    if patterns:
        template = (
            f"该公司综合风险等级为{risk_cn}（{out.overall_score:.3f} 分），"
            f"疑似命中造假模式：{'、'.join(patterns)}；"
            f"上述结论由规则引擎评分、触发规则与造假模式匹配结果汇总，数字均可追溯至对应证据。"
        )
    else:
        template = (
            f"该公司综合风险等级为{risk_cn}（{out.overall_score:.3f} 分），"
            f"当前数据未命中既有造假模式；结论仅反映既有规则覆盖范围，不构成对未覆盖风险的排除。"
        )
    return locked, template, patterns, len(evidence_ids)


@router.get(
    "/companies/{code}/fraud-conclusion",
    response_model=V12Response[FraudConclusionData],
)
async def get_fraud_conclusion(
    code: str = Path(..., description="公司代码，如 600518.SH"),
    as_of: str | None = Query(default=None, description="数据截止日期"),
):
    """反欺诈结论（结论层 + 叙事层）——按需调用。

    - 数字/规则名/公司名/模式名/置信度全部由后端确定性计算并锁定，
      LLM 仅做措辞归纳，禁止改动任何数值；
    - LLM 失败/关闭时回退确定性模板结论（method=template）。
    """
    trace_id = str(uuid.uuid4())
    from app.domain.finance.period import normalize_period

    as_of_ymd = normalize_period(as_of) or ""
    try:
        from app.application.services.risk_scoring_service import assemble_and_score

        out = await assemble_and_score(code, as_of_ymd or "")
    except ValueError as exc:
        raise HTTPException(
            status_code=404, detail=f"Company not found: {code}"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"风险评分失败: {exc}") from exc

    locked, template, patterns, ev_count = _build_fraud_conclusion_input(out)

    conclusion, method = template, "template"
    try:
        from app.agents.llm_sync import run_llm_chat

        messages = [
            {
                "role": "system",
                "content": (
                    "你是上市公司财报反欺诈分析助手。只能依据下面给定的结构化数据归纳，"
                    "严禁改动、新增或猜测任何数字、规则编号、公司名、模式名、置信度；"
                    "每个数字必须原样引用。输出 2-4 句中文：先说疑似造假模式，"
                    "再给关键证据数字，最后一句风险提示。数据不足就如实说，不得虚构。"
                ),
            },
            {"role": "user", "content": locked},
        ]
        llm_out = await asyncio.to_thread(run_llm_chat, messages)
        if llm_out and str(llm_out).strip():
            conclusion, method = str(llm_out).strip(), "llm"
    except Exception:  # noqa: BLE001 — LLM 失败回退模板
        pass

    return V12Response(
        data=FraudConclusionData(
            wind_code=out.wind_code,
            sec_name=out.sec_name,
            risk_level=out.risk_level,
            overall_score=out.overall_score,
            as_of=getattr(out, "as_of", "") or as_of_ymd or None,
            conclusion=conclusion,
            method=method,
            patterns=patterns,
            evidence_count=ev_count,
        ),
        meta=ApiMeta(
            request_id=trace_id,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            data_as_of=as_of_ymd,
        ),
    )


@router.get(
    "/companies/{code}/impact-advice",
    response_model=V12Response[ImpactAdviceData],
)
async def get_impact_advice(
    code: str = Path(..., description="公司代码，如 600518.SH"),
    as_of: str | None = Query(default=None, description="数据截止日期"),
):
    """Phase E 会3：影响与建议聚合端点（画像页影响建议模块数据源）。

    综合财务规则信号 / 股权链路与隐含关系 / 舆情影响 / 综合风险评分
    四路生成整体建议；每句建议可溯源（segments 携带 evidence_ids）；
    LLM 只读锁定事实（不覆盖/不篡改结构化数据），失败回退模板兜底。
    """
    trace_id = str(uuid.uuid4())
    from app.domain.finance.period import normalize_period

    as_of_ymd = normalize_period(as_of) or ""
    try:
        from app.application.services.impact_advice_service import (
            assemble_impact_advice,
        )

        result = await assemble_impact_advice(code, as_of_ymd or "")
    except ValueError as exc:
        raise HTTPException(
            status_code=404, detail=f"Company not found: {code}"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("impact-advice 聚合失败")
        raise HTTPException(
            status_code=500, detail=f"影响与建议聚合失败: {exc}"
        ) from exc

    return V12Response(
        data=ImpactAdviceData(
            wind_code=result.wind_code,
            sec_name=result.sec_name,
            risk_level=result.risk_level,
            overall_score=result.overall_score,
            as_of=result.as_of,
            overall_advice=result.overall_advice,
            method=result.method,
            segments=[
                ImpactAdviceSegmentData(
                    source_module=s.source_module,
                    title=s.title,
                    detail=s.detail,
                    evidence_ids=s.evidence_ids,
                )
                for s in result.segments
            ],
            evidence_count=result.evidence_count,
            warnings=result.warnings,
        ),
        meta=ApiMeta(
            request_id=trace_id,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            data_as_of=as_of_ymd,
        ),
    )
