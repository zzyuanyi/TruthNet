"""_answer_comparison — generate_answer 拆分模块（重构生成，函数体与原文件逐字节一致）。"""

from __future__ import annotations

import logging
from ._answer_common import _emit_segment
from ._answer_fact_lookup import (
    _evidence_for_observations,
    _web_search_fill_company_fact,
)
from app.agents.state import (
    AgentState,
    Claim,
    EvidenceRef,
    FinalResponse,
    MAX_MULTI_COMPARISON_PARTICIPANTS,
)
from app.core.config import settings
from app.domain.provenance.id_factory import (
    NS_COMPANY_REGISTRY,
    make_claim_id,
    make_evidence_id,
)

logger = logging.getLogger(__name__)


def _answer_light_comparison(state: AgentState) -> dict:
    """v3.3.3 批次 C/D（方案 §5.6）：消费 ComparisonSpec 的轻量比较回答。

    查询与算术在 light_comparison_service，本函数只渲染结构化结果并
    组装 claim/evidence；missing_dimension/full 不得启动数值查询。
    """
    plan = state.get("plan")
    spec = getattr(plan, "comparison", None) if plan is not None else None
    company = state.get("company")
    if spec is None:
        return {}
    if spec.scope == "same_company_cross_indicator" and spec.mode == "indicator":
        if company is None:
            return {}
        return _answer_same_company_comparison(state, company, spec)
    if spec.scope == "cross_company":
        return _answer_cross_company_comparison(state, spec)
    return {}


def _answer_same_company_comparison(state: AgentState, company, spec) -> dict:
    """同主体两指标轻量比较：共同期间 + 单位校验 + 程序差值（批次 C）。"""
    from app.application.services.light_comparison_service import (
        compare_same_company_indicators,
    )

    plan = state.get("plan")
    as_of = plan.as_of.strftime("%Y%m%d") if plan and plan.as_of else ""
    result = compare_same_company_indicators(
        company.wind_code, company.sec_name, spec, as_of=as_of
    )
    name_code = f"{company.sec_name}（{company.wind_code}）"

    def _finish(answer: str, claims: list, evidence: list, executed: list) -> dict:
        _emit_segment(state, answer)
        return {
            "claims": claims,
            "evidence": evidence,
            "executed_metrics": executed,
            "final_response": FinalResponse(
                answer=answer,
                risk_level="unknown",
                claims=claims,
                evidence=evidence,
            ),
        }

    if result.status == "ok":
        runtime = state.get("runtime")
        turn_id = getattr(runtime, "turn_id", "") if runtime else ""
        trace_id = getattr(runtime, "trace_id", "") if runtime else ""
        evidence: list[EvidenceRef] = []
        for participant in result.participants:
            evidence.extend(
                _evidence_for_observations(state, company, participant.observations)
            )
        evidence_ids = [item.evidence_id for item in evidence]
        claim = Claim(
            claim_id=make_claim_id(
                turn_id=turn_id,
                company_code=company.wind_code,
                claim_type="indicator_comparison",
                claim_text=result.conclusion,
            ),
            text=result.conclusion,
            claim_type="indicator_comparison",
            severity="unknown",
            evidence_ids=evidence_ids,
            verification_status="verified",
            limitations=["母公司报表口径", "共同期间"],
            turn_id=turn_id,
            trace_id=trace_id,
            company_code=company.wind_code,
            module="finance",
        )
        executed = [
            {
                "metric_id": p.metric_id,
                "period": p.period,
                "unit": p.unit,
                "status": "ok",
                "company_code": p.company_code,
            }
            for p in result.participants
        ]
        return _finish(result.conclusion, [claim], evidence, executed)

    if result.status == "partial":
        parts = []
        for p in result.participants:
            parts.append(f"{p.metric_label}为 {p.value:.2f}（期间 {p.period}）")
        answer = (
            f"{name_code}仅有一侧指标可用：{'；'.join(parts)}。"
            "另一侧指标数据不可用，无法比较高低（母公司口径）。"
        )
        return _finish(answer, [], [], [])

    if result.status == "unsupported":
        answer = (
            f"{name_code}的两项指标单位不兼容，无法直接相减"
            f"（{'；'.join(result.warnings)}）。请指定同一量纲的指标对比。"
        )
        return _finish(answer, [], [], [])

    # insufficient_data：无共同期间/两侧无数据，不得输出高低结论
    answer = (
        f"{name_code}：{'；'.join(result.warnings) or '数据不足'}，"
        "无法完成两项指标的比较（母公司口径）。"
    )
    return _finish(answer, [], [], [])


def _light_comparison_payload(
    spec,
    targets,
    *,
    comparison_mode: str,
    overview_rows: list | None = None,
    llm_analysis: str = "",
) -> dict:
    """v3.3.4 方案 §3.3/§6.1：已执行比较的 light_comparison 载荷。

    next_steps 由程序按 requested_scope 生成（只提供导航动作，不改变任何
    数值、主体、证据或结论）；主体代码直接取已校验的 finalized targets
    （去重保序），禁止掺入未经校验的主体。
    Phase E 会6：llm_analysis 为跨公司对比大模型整体分析段落（空串表示
    未生成/降级，前端不渲染）。
    """
    from app.application.services.light_comparison_service import (
        build_preview_next_steps,
    )

    codes: list[str] = []
    for t in targets or []:
        code = str(getattr(t, "wind_code", "") or "")
        if code and code not in codes:
            codes.append(code)
    scope = getattr(spec, "requested_scope", "indicator") or "indicator"
    return {
        "comparison_mode": comparison_mode,
        "overview_rows": list(overview_rows or []),
        "requested_scope": scope,
        "next_steps": [s.model_dump() for s in build_preview_next_steps(scope, codes)],
        "llm_analysis": llm_analysis,
    }


def _answer_cross_company_comparison(state: AgentState, spec) -> dict:
    """v3.3.3 批次 D：双公司轻量比较渲染（方案 §2.4/§5.6）。"""
    targets = state.get("comparison_targets") or []

    def _plain(answer: str) -> dict:
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(
                answer=answer, risk_level="unknown", claims=[], evidence=[]
            ),
        }

    if spec.mode == "missing_dimension":
        return _plain(
            "请指定要比较的维度（例如毛利率、存货周转天数或风险等级），"
            "我会给出双方数值与差异。"
        )
    if spec.mode == "risk":
        return _answer_cross_company_risk(state, targets, spec)
    if spec.mode == "indicator":
        return _answer_cross_company_indicator(state, targets, spec)
    if spec.mode == "overview":
        return _answer_cross_company_overview(state, targets, spec)
    if spec.mode == "company_fact":
        return _answer_cross_company_fact(state, targets, spec)
    return {}


def _answer_cross_company_overview(state, targets, spec) -> dict:
    """双公司轻量整体概览（v3.3.4 方案 §3/§5/§6）。

    服务端固定维度 profile 逐指标比较；claims/evidence 只引用成功行
    （缺失行不伪造事实）；不生成综合评分与整体优劣结论；
    requested_scope=full/industry 时明确声明有限预览，结构化 next_steps
    按请求范围由程序生成。
    """
    from app.application.services.light_comparison_service import (
        compare_cross_company_overview,
    )

    plan = state.get("plan")
    as_of = plan.as_of.strftime("%Y%m%d") if plan and plan.as_of else ""
    result = compare_cross_company_overview(targets, spec, as_of=as_of)
    runtime = state.get("runtime")
    turn_id = getattr(runtime, "turn_id", "") if runtime else ""
    trace_id = getattr(runtime, "trace_id", "") if runtime else ""
    company_by_code = {str(t.wind_code): t for t in targets}

    def _fmt(value, unit: str) -> str:
        if unit in ("percent", "ratio", "pp"):
            return f"{value:.2f}%"
        if unit == "days":
            return f"{value:.2f}天"
        return f"{value:,.2f}元"

    ok_rows = [r for r in result.overview_rows if r.status == "ok"]
    claims: list[Claim] = []
    evidence: list[EvidenceRef] = []
    executed: list[dict] = []
    for row in ok_rows:
        if len(row.values) != 2:
            continue  # 防御：ok 行必须携带双方值，否则不为其生成事实 claim
        row_evidence: list[EvidenceRef] = []
        for participant in row.values:
            ref = company_by_code.get(participant.company_code)
            if ref is None:
                continue
            row_evidence.extend(
                _evidence_for_observations(state, ref, participant.observations)
            )
        evidence.extend(row_evidence)
        first, second = row.values
        text = (
            f"{row.metric_label}：{first.sec_name}"
            f"{_fmt(first.value, row.unit)}；{second.sec_name}"
            f"{_fmt(second.value, row.unit)}；{row.conclusion}"
            f"（共同期间 {row.period}，母公司口径）"
        )
        primary_code = str(targets[0].wind_code) if targets else ""
        claims.append(
            Claim(
                claim_id=make_claim_id(
                    turn_id=turn_id,
                    company_code=primary_code,
                    claim_type="overview_comparison",
                    claim_text=text,
                ),
                text=text,
                claim_type="overview_comparison",
                severity="unknown",
                evidence_ids=[ev.evidence_id for ev in row_evidence],
                verification_status="verified",
                limitations=["母公司报表口径", "共同期间", "轻量概览"],
                turn_id=turn_id,
                trace_id=trace_id,
                company_code=primary_code,
                module="finance",
            )
        )
        executed.extend(
            {
                "metric_id": v.metric_id,
                "period": v.period,
                "unit": v.unit,
                "status": "ok",
                "company_code": v.company_code,
            }
            for v in row.values
        )

    names = "、".join(str(getattr(t, "sec_name", "") or "") for t in targets[:2])
    if ok_rows:
        first_name = str(getattr(targets[0], "sec_name", "公司A"))
        second_name = str(getattr(targets[1], "sec_name", "公司B"))
        table = [
            f"{names}概览",
            "",
            f"| 指标 | {first_name} | {second_name} | 共同期间 | 对比结论 |",
            "|---|---:|---:|---|---|",
        ]
        for row in ok_rows:
            first, second = row.values
            conclusion = str(row.conclusion or "").replace("|", "｜")
            table.append(
                f"| {row.metric_label} | {_fmt(first.value, row.unit)} | "
                f"{_fmt(second.value, row.unit)} | {row.period} | {conclusion} |"
            )
        missing = [r.metric_label for r in result.overview_rows if r.status != "ok"]
        answer = "\n".join(table)
        if missing:
            answer += "\n\n暂无共同可比数据：" + "、".join(missing) + "。"
        if result.conclusion:
            answer += "\n\n" + result.conclusion
    else:
        answer = (
            f"{names}概览：{'；'.join(result.warnings) or '数据不足'}，"
            "无法完成概览比较（母公司口径）。"
        )
    # v3.3.4 方案 §6.1：requested_scope 感知的预览声明——
    # 全面/行业请求必须明确当前结果是有限预览而非完整结论/行业分位。
    if spec.requested_scope == "industry":
        answer += (
            "\n\n当前对话仅展示基础财务预览，未执行行业分位或行业基准计算；"
            "行业对比请点击「查看行业对比」。"
        )
    elif spec.requested_scope == "full":
        answer += (
            "\n\n以上为有限预览，不代表完整画像；风险、股权、行业等更多维度"
            "请点击「查看完整对比」。"
        )
    else:
        answer += (
            "\n\n这是基础指标预览，不代表完整画像；可继续指定「毛利率」"
            "「存货周转」或「风险等级」进行单项比较，完整对比请点击"
            "「查看完整对比」。"
        )

    # ── Phase E 会6：跨公司对比大模型整体分析段落 ──
    # 只读结构化数据做整体解读（不覆盖/不篡改）；失败/降级时模板兜底，
    # 空串则前端不渲染该段。
    llm_analysis = ""
    try:
        from app.application.services.comparison_analysis_service import (
            build_comparison_analysis,
        )

        names_list = [str(getattr(t, "sec_name", "") or "") for t in targets[:2]]
        llm_analysis, _analysis_warnings = build_comparison_analysis(
            result=result,
            company_names=names_list,
        )
        if llm_analysis:
            answer += "\n\n大模型整体分析：" + llm_analysis
    except Exception:  # noqa: BLE001 — 分析失败不影响结构化比较
        logger.warning("comparison_analysis 失败，跳过 LLM 段落", exc_info=True)

    _emit_segment(state, answer)
    return {
        "claims": claims,
        "evidence": evidence,
        "executed_metrics": executed,
        "final_response": FinalResponse(
            answer=answer,
            risk_level="unknown",
            claims=claims,
            evidence=evidence,
        ),
        # v3.3.4 方案 §3.3/§6.1：结构化概览载荷（REST/WS 只读追加，向后兼容）。
        # overview_rows 用 mode="json" 序列化（Decimal → float/str），
        # WS _ws_sender 的 json.dumps 不接受 Decimal。
        "light_comparison": _light_comparison_payload(
            spec,
            targets,
            comparison_mode=result.comparison_mode,
            overview_rows=[r.model_dump(mode="json") for r in result.overview_rows],
            llm_analysis=llm_analysis,
        ),
    }


def _answer_cross_company_risk(state, targets, spec) -> dict:
    """两家公司窄风险比较（收口批次 D，方案 §3.7）。

    按既有评估等级排序回答；任一侧无记录/口径不一致 → partial 诚实
    说明；显式历史截止期（as_of）→ unsupported（方案 §5 D2：当前仅
    支持最新风险评估，不静默取未来记录）。触发信号详情继续页面
    （不在此伪造）。等级比较不生成数值 claim（避免无证据数值结论），
    页面承载详情。
    """
    from app.application.services.light_comparison_service import (
        compare_cross_company_risk,
    )

    plan = state.get("plan")
    as_of = plan.as_of.strftime("%Y%m%d") if plan and plan.as_of else ""
    result = compare_cross_company_risk(targets, spec, as_of=as_of)
    if result.status == "ok":
        answer = result.conclusion
    elif result.status == "partial":
        answer = (
            f"风险比较：{'；'.join(result.warnings)}。"
            "全面风险画像请使用页面跨公司对比。"
        )
    else:
        answer = f"风险比较：{'；'.join(result.warnings) or '数据不足'}。"
    _emit_segment(state, answer)
    return {
        "claims": [],
        "evidence": [],
        "final_response": FinalResponse(
            answer=answer, risk_level="unknown", claims=[], evidence=[]
        ),
        # v3.3.4 方案 §2.1/§6.1：风险比较附带完整对比页下一步
        "light_comparison": _light_comparison_payload(
            spec, targets, comparison_mode="risk"
        ),
    }


def _answer_cross_company_indicator(state, targets, spec) -> dict:
    """双公司单指标：共同期间 + 程序差值 + 双方原始值（批次 D）。"""
    from app.application.services.light_comparison_service import (
        compare_cross_company_indicators,
    )

    plan = state.get("plan")
    as_of = plan.as_of.strftime("%Y%m%d") if plan and plan.as_of else ""
    result = compare_cross_company_indicators(targets, spec, as_of=as_of)
    runtime = state.get("runtime")
    turn_id = getattr(runtime, "turn_id", "") if runtime else ""
    trace_id = getattr(runtime, "trace_id", "") if runtime else ""

    def _finish(answer: str, claims: list, evidence: list, executed: list) -> dict:
        _emit_segment(state, answer)
        return {
            "claims": claims,
            "evidence": evidence,
            "executed_metrics": executed,
            "final_response": FinalResponse(
                answer=answer,
                risk_level="unknown",
                claims=claims,
                evidence=evidence,
            ),
            # v3.3.4 方案 §2.1/§6.1：单指标比较附带完整对比页下一步
            "light_comparison": _light_comparison_payload(
                spec, targets, comparison_mode="indicator"
            ),
        }

    if result.status == "ok":
        company_by_code = {str(t.wind_code): t for t in targets}
        evidence: list[EvidenceRef] = []
        for participant in result.participants:
            ref = company_by_code.get(participant.company_code)
            if ref is None:
                continue
            evidence.extend(
                _evidence_for_observations(state, ref, participant.observations)
            )
        evidence_ids = [item.evidence_id for item in evidence]
        primary_code = str(targets[0].wind_code) if targets else ""
        claim = Claim(
            claim_id=make_claim_id(
                turn_id=turn_id,
                company_code=primary_code,
                claim_type="indicator_comparison",
                claim_text=result.conclusion,
            ),
            text=result.conclusion,
            claim_type="indicator_comparison",
            severity="unknown",
            evidence_ids=evidence_ids,
            verification_status="verified",
            limitations=["母公司报表口径", "共同期间"],
            turn_id=turn_id,
            trace_id=trace_id,
            company_code=primary_code,
            module="finance",
        )
        executed = [
            {
                "metric_id": p.metric_id,
                "period": p.period,
                "unit": p.unit,
                "status": "ok",
                "company_code": p.company_code,
            }
            for p in result.participants
        ]
        return _finish(
            result.conclusion
            + "\n\n更多维度的对比请点击「查看完整对比」进入跨公司对比页面。",
            [claim],
            evidence,
            executed,
        )

    if result.status == "partial":
        names = "、".join(p.sec_name for p in result.participants)
        return _finish(
            f"仅{names}的该指标数据可用，另一侧不可用，无法比较高低（母公司口径）。",
            [],
            [],
            [],
        )

    if result.status == "unsupported":
        return _finish(f"该比较暂不支持：{'；'.join(result.warnings)}。", [], [], [])

    return _finish(
        f"双方数据不足或无共同期间：{'；'.join(result.warnings)}，"
        "无法比较（母公司口径）。",
        [],
        [],
        [],
    )


def _answer_cross_company_fact(state, targets, spec) -> dict:
    """双公司公司事实比较（批次 D 仅 listing_date）。"""
    from app.application.services.light_comparison_service import (
        compare_cross_company_facts,
    )

    runtime = state.get("runtime")
    turn_id = getattr(runtime, "turn_id", "") if runtime else ""
    trace_id = getattr(runtime, "trace_id", "") if runtime else ""

    comparison_targets = list(targets)
    web_evidence_by_code: dict[str, EvidenceRef] = {}
    if getattr(spec, "fact_key", "") == "listing_date":
        for index, target in enumerate(comparison_targets):
            if str(getattr(target, "listing_date", "") or "").strip():
                continue
            value, web_evidence = _web_search_fill_company_fact(
                sec_name=str(target.sec_name),
                wind_code=str(target.wind_code),
                fact_key="listing_date",
                label="上市日期",
                turn_id=turn_id,
                trace_id=trace_id,
            )
            if value:
                comparison_targets[index] = target.model_copy(
                    update={"listing_date": value}
                )
            if web_evidence is not None:
                web_evidence_by_code[str(target.wind_code)] = web_evidence

    result = compare_cross_company_facts(comparison_targets, spec)

    def _finish(answer: str, claims: list, evidence: list) -> dict:
        _emit_segment(state, answer)
        return {
            "claims": claims,
            "evidence": evidence,
            "final_response": FinalResponse(
                answer=answer,
                risk_level="unknown",
                claims=claims,
                evidence=evidence,
            ),
            # v3.3.4 方案 §2.1/§6.1：公司事实比较附带完整对比页下一步
            "light_comparison": _light_comparison_payload(
                spec, targets, comparison_mode="company_fact"
            ),
        }

    if result.status != "ok":
        return _finish(
            f"上市日期比较：{'；'.join(result.warnings) or '数据不足'}。",
            [],
            [],
        )

    evidence: list[EvidenceRef] = []
    for target in comparison_targets:
        date_value = str(getattr(target, "listing_date", "") or "")
        if not date_value:
            continue
        web_evidence = web_evidence_by_code.get(str(target.wind_code))
        if web_evidence is not None:
            evidence.append(web_evidence)
            continue
        evidence.append(
            EvidenceRef(
                evidence_id=make_evidence_id(
                    source_namespace=NS_COMPANY_REGISTRY,
                    source_type="company_registry",
                    source_record_id=str(target.wind_code),
                    field_path="listing_date",
                    company_code=str(target.wind_code),
                ),
                source_type="company_registry",
                source_record_id=str(target.wind_code),
                field_path="listing_date",
                value=date_value,
                source_title=f"{target.sec_name} · 公司注册信息",
                turn_id=turn_id,
                trace_id=trace_id,
                company_code=str(target.wind_code),
                module="company_fact",
            )
        )
    evidence_ids = [item.evidence_id for item in evidence]
    primary_code = str(targets[0].wind_code) if targets else ""
    claim = Claim(
        claim_id=make_claim_id(
            turn_id=turn_id,
            company_code=primary_code,
            claim_type="company_fact_comparison",
            claim_text=result.conclusion,
        ),
        text=result.conclusion,
        claim_type="company_fact_comparison",
        severity="unknown",
        evidence_ids=evidence_ids,
        verification_status="verified",
        limitations=["公司注册信息（证券主表）"],
        turn_id=turn_id,
        trace_id=trace_id,
        company_code=primary_code,
        module="company_fact",
    )
    return _finish(result.conclusion, [claim], evidence)


def _answer_comparison_guide(state: AgentState) -> dict:
    """比较意图页面引导（P2-2 + v3.3.3 批次 D + v3.3.4 §2.4/§6.1）。

    按 0/1/≥2 家候选区分文案，绝不静默退化为单公司分析；
    批次 D 起聊天内已支持双公司单指标/公司事实轻量比较。
    三家及以上（v3.3.4）：不查询指标、不静默截断——
    - 3..MAX 家 → 结构化保底 next_steps（多主体页面可用 →
      open_multi_company_comparison 全代码；否则 choose_comparison_pair）；
    - 超过 MAX → 纯文案要求缩小范围，next_steps 为空、不携带任何代码。
    """
    from app.agents.nodes.plan_modules import _FULL_COMPARISON_CUES
    from app.application.services.light_comparison_service import (
        build_multi_company_next_steps,
    )

    user_query = state.get("user_query", "")
    targets = state.get("comparison_targets", [])
    company = state.get("company")

    def _finish(answer: str, payload: dict | None = None) -> dict:
        _emit_segment(state, answer)
        out: dict = {
            "final_response": FinalResponse(
                answer=answer, risk_level="unknown", claims=[], evidence=[]
            )
        }
        if payload is not None:
            out["light_comparison"] = payload
        return out

    def _requested_scope_from_query() -> str:
        if any(cue in user_query for cue in _FULL_COMPARISON_CUES):
            return "full"
        if "行业" in user_query:
            return "industry"
        return "overview"

    # v3.3.3 批次 D + v3.3.4：单主体行业/全面对比（company 已识别、targets 为空）
    if not targets and company is not None:
        if any(cue in user_query for cue in _FULL_COMPARISON_CUES):
            return _finish(
                f"{company.sec_name}（{company.wind_code}）目前只有一家公司，"
                "无法进行跨公司对比。请补充另一家公司的名称或代码；"
                "完整对比请使用页面「跨公司对比」功能。"
            )
        return _finish(
            f"{company.sec_name}（{company.wind_code}）的行业分位对比请使用"
            "页面「行业对标」功能（企业画像页/跨公司对比页提供行业基准与"
            "分位），对话内暂不执行行业分位计算。"
        )

    if len(targets) >= 2:
        names = "、".join(f"{item.sec_name}（{item.wind_code}）" for item in targets)
        codes: list[str] = []
        for item in targets:
            code = str(getattr(item, "wind_code", "") or "")
            if code and code not in codes:
                codes.append(code)

        # v3.3.4 §2.4：三家及以上保底——不查询、不截断、不默认取前两家
        if len(codes) >= 3:
            next_steps = build_multi_company_next_steps(
                codes,
                multi_page_enabled=settings.COMPARISON_MULTI_PAGE_ENABLED,
            )
            if len(codes) > MAX_MULTI_COMPARISON_PARTICIPANTS:
                answer = (
                    f"你提到了 {names} 共 {len(codes)} 家公司，超过一次对比的"
                    f"上限 {MAX_MULTI_COMPARISON_PARTICIPANTS} 家。请缩小到"
                    f" {MAX_MULTI_COMPARISON_PARTICIPANTS} 家以内再发起对比；"
                    "本次未执行任何指标查询，也没有默认选择其中几家。"
                )
            elif settings.COMPARISON_MULTI_PAGE_ENABLED:
                answer = (
                    f"已识别 {names} 共 {len(codes)} 家公司，尚未执行数值比较。"
                    "多主体对比页已支持一次对比全部公司，请点击「多公司对比」"
                    "；或指定其中两家与具体指标（如毛利率）在对话内比较。"
                )
            else:
                answer = (
                    f"已识别 {names} 共 {len(codes)} 家公司，尚未执行数值比较。"
                    "一期对话预览仅支持两家，请点击「选择两家对比」或直接"
                    "指定其中两家与具体指标（如毛利率）在对话内比较。"
                )
            return _finish(
                answer,
                {
                    "comparison_mode": "",
                    "overview_rows": [],
                    "requested_scope": _requested_scope_from_query(),
                    "next_steps": [s.model_dump() for s in next_steps],
                },
            )

        # 恰好两家（防御性兜底：正常路径已在 plan 层进入 overview/轻量比较）
        if "行业" in user_query:
            return _finish(
                f"行业分位对比请使用页面「行业对标/跨公司对比」功能"
                f"（{names} 的指标行业分位在页面展示）。"
                "对话内可回答两家公司同一指标或同一公司事实的数值比较。"
            )
        return _finish(
            f"你提到了 {names}。全面/多维度对比请使用"
            "页面上方的「跨公司对比」功能；单个指标（如毛利率、"
            "存货周转天数）或公司事实（如上市日期）的两两比较"
            "可直接在对话中提问。"
        )
    if len(targets) == 1:
        t0 = targets[0]
        if "行业" in user_query:
            return _finish(
                f"{t0.sec_name}（{t0.wind_code}）的行业分位对比请使用"
                "页面「行业对标」功能（企业画像页/跨公司对比页提供"
                "行业基准与分位），对话内暂不执行行业分位计算。"
            )
        return _finish(
            f"已识别 {t0.sec_name}（{t0.wind_code}），另一家公司未匹配到"
            "数据。请补充另一家公司的名称或代码；跨公司对比请使用页面"
            "上方的「跨公司对比」功能。"
        )
    return _finish(
        "请提供两家公司的名称或代码（例如「康美药业和金牌家居的"
        "差距」），以便进行跨公司对比。"
    )
