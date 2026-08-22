"""GenerateAnswer — V12 §7.2. 生成最终回答（入口 + 意图分发）。

重构说明（2026-08-21）：本文件原为 3600+ 行单体，已按职责拆分：
- _answer_common：常量 + 叶子工具（流式/格式化/状态）
- _answer_headline：综合分析/润色/风险等级
- _answer_fact_lookup：公司事实/行情/指标/行业
- _answer_research：研报族
- _answer_comparison：对比族
本文件保留 generate_answer_node 入口与全部名字 re-export（兼容外部 import）。
"""

from __future__ import annotations

import logging
from app.agents.delta_sink import get_sink
from app.agents.state import AgentState, FinalResponse
from app.core.config import settings
from app.domain.finance.parent_scope import NO_SIGNAL_IN_SCOPE, RISK_SIGNAL_IN_SCOPE
import re

from ._answer_common import (
    CHAT_RISK_DISCLAIMER,
    _CAPABILITY_KW,
    _CONSOLIDATED_SCOPE_KW,
    _CONTEXT_REQUEST_KW,
    _EXCHANGE_LABELS,
    _FACT_KEYS,
    _FAREWELL_KW,
    _FRAUD_KEYWORDS,
    _IMPACT_DIRECTION_LABELS,
    _IMPACT_SEVERITY_LABELS,
    _IMPACT_TYPE_LABELS,
    _METRIC_LABELS,
    _METRIC_UNITS,
    _MODULE_LABELS,
    _MODULE_STATE_LABELS,
    _R7_FOLLOW_UP_FULL,
    _R7_FOLLOW_UP_SIMPLIFIED,
    _RISK_SEVERITIES,
    _RULE_FOLLOW_UP,
    _SEVERITY_LABELS,
    _SEVERITY_ORDER,
    _THANKS_KW,
    _UNSUPPORTED_MARKET_CUES,
    _WEB_SEARCHABLE_FACTS,
    _clip_evidence_value,
    _dedup,
    _emit_segment,
    _extract_key_facts,
    _extract_markers,
    _finance_all_blocked,
    _finance_executed,
    _format_growth,
    _format_indicator_value,
    _format_metrics,
    _format_number_value,
    _highest_severity,
    _is_unsupported_market_query,
    _leaf_risk_claims,
    _merge_unique,
    _module_state,
    _stream_turn_id,
)
from ._answer_headline import (
    _answer_risk_level,
    _answer_rule_detail,
    _build_company_brief_analysis,
    _build_cross_module_observation,
    _build_equity_overview,
    _build_follow_ups,
    _build_impact_conclusions_segment,
    _build_interpretation_segments,
    _build_rule_details,
    _build_signal_summary,
    _degraded_module_summary,
    _polish_answer,
    _select_answer_mode,
)
from ._answer_fact_lookup import (
    _answer_company_fact,
    _answer_directional_events,
    _answer_indicator,
    _answer_indicator_assessment,
    _answer_industry_benchmark,
    _answer_market_quote,
    _answer_multi_metric,
    _company_fact_search_queries,
    _evidence_for_observations,
    _indicator_impact_text,
    _web_search_fill_company_fact,
)
from ._answer_research import (
    _answer_company_research,
    _format_research_insights,
    _research_evidence_and_claims,
    _research_relevant_excerpt,
)
from ._answer_comparison import (
    _answer_comparison_guide,
    _answer_cross_company_comparison,
    _answer_cross_company_fact,
    _answer_cross_company_indicator,
    _answer_cross_company_overview,
    _answer_cross_company_risk,
    _answer_light_comparison,
    _answer_same_company_comparison,
    _light_comparison_payload,
)

__all__ = [
    "CHAT_RISK_DISCLAIMER",
    "_CAPABILITY_KW",
    "_CONSOLIDATED_SCOPE_KW",
    "_CONTEXT_REQUEST_KW",
    "_EXCHANGE_LABELS",
    "_FACT_KEYS",
    "_FAREWELL_KW",
    "_FRAUD_KEYWORDS",
    "_IMPACT_DIRECTION_LABELS",
    "_IMPACT_SEVERITY_LABELS",
    "_IMPACT_TYPE_LABELS",
    "_METRIC_LABELS",
    "_METRIC_UNITS",
    "_MODULE_LABELS",
    "_MODULE_STATE_LABELS",
    "_R7_FOLLOW_UP_FULL",
    "_R7_FOLLOW_UP_SIMPLIFIED",
    "_RISK_SEVERITIES",
    "_RULE_FOLLOW_UP",
    "_SEVERITY_LABELS",
    "_SEVERITY_ORDER",
    "_THANKS_KW",
    "_UNSUPPORTED_MARKET_CUES",
    "_WEB_SEARCHABLE_FACTS",
    "_answer_company_fact",
    "_answer_company_research",
    "_answer_comparison_guide",
    "_answer_cross_company_comparison",
    "_answer_cross_company_fact",
    "_answer_cross_company_indicator",
    "_answer_cross_company_overview",
    "_answer_cross_company_risk",
    "_answer_directional_events",
    "_answer_indicator",
    "_answer_indicator_assessment",
    "_answer_industry_benchmark",
    "_answer_light_comparison",
    "_answer_market_quote",
    "_answer_multi_metric",
    "_answer_risk_level",
    "_answer_same_company_comparison",
    "_build_company_brief_analysis",
    "_build_cross_module_observation",
    "_build_equity_overview",
    "_build_follow_ups",
    "_build_impact_conclusions_segment",
    "_build_interpretation_segments",
    "_build_rule_details",
    "_build_signal_summary",
    "_clip_evidence_value",
    "_company_fact_search_queries",
    "_dedup",
    "_degraded_module_summary",
    "_emit_segment",
    "_evidence_for_observations",
    "_extract_key_facts",
    "_extract_markers",
    "_finance_all_blocked",
    "_finance_executed",
    "_format_growth",
    "_format_indicator_value",
    "_format_metrics",
    "_format_number_value",
    "_format_research_insights",
    "_highest_severity",
    "_indicator_impact_text",
    "_is_unsupported_market_query",
    "_leaf_risk_claims",
    "_light_comparison_payload",
    "_merge_unique",
    "_module_state",
    "_polish_answer",
    "_research_evidence_and_claims",
    "_research_relevant_excerpt",
    "_select_answer_mode",
    "_stream_turn_id",
    "_web_search_fill_company_fact",
]

logger = logging.getLogger(__name__)


def generate_answer_node(state: AgentState) -> dict:
    company = state.get("company")
    claims = state.get("claims", [])
    evidence = state.get("evidence", [])
    finance_ran, finance = _finance_executed(state)
    finance_blocked = _finance_all_blocked(finance)
    finance_unknown_type = finance_blocked and any(
        "公司类型缺失" in (w or "") for w in (finance.warnings or [])
    )
    # 流式模式：存在 DeltaSink（由 WsTurnRunner 注册）。
    # 流式下跳过整段 LLM 润色——润色会整体重写回答，导致
    # "delta 拼接 == 最终答案" 无法成立；润色仅作为 REST 增强保留。
    streaming = get_sink(_stream_turn_id(state) or "") is not None

    if company is None:
        user_query = state.get("user_query", "")
        plan = state.get("plan")
        intent = getattr(plan, "intent", "") if plan else ""

        if intent == "industry_benchmark":
            return _answer_industry_benchmark(state)
        if intent == "unsupported_indicator":
            answer = (
                f"当前数据覆盖范围暂不支持查询「{user_query}」，无法可靠返回该指标。"
            )
            _emit_segment(state, answer)
            return {
                "claims": [],
                "evidence": [],
                "final_response": FinalResponse(answer=answer, risk_level="unknown"),
            }
        if intent in ("investment_advice", "trade_execution"):
            answer = (
                "系统不能代为买卖证券或提交交易指令。"
                if intent == "trade_execution"
                else "系统不提供是否买入或卖出的投资建议。"
            )
            answer += "可以查询客观行情，或核查财务、股权与公告风险后自行判断。"
            _emit_segment(state, answer)
            return {
                "claims": [],
                "evidence": [],
                "final_response": FinalResponse(answer=answer, risk_level="unknown"),
            }
        if intent in ("causal_query", "unsupported_scope"):
            answer = (
                "当前系统不接入行情价格因果归因，无法仅凭财报、股权和公告模块确认这次涨跌原因。"
                if intent == "causal_query"
                else "当前系统固定使用母公司报表口径，不能切换为合并口径；本轮不返回替代口径数值。"
            )
            _emit_segment(state, answer)
            return {
                "claims": [],
                "evidence": [],
                "final_response": FinalResponse(answer=answer, risk_level="unknown"),
            }

        if getattr(plan, "event_list_requested", False):
            answer = (
                "当前公告/事件列表查询需要先指定上市公司或股票代码；"
                "系统暂不提供全市场公告的完整索引，不能据此确认所有上市公司的股权质押公告。"
            )
            _emit_segment(state, answer)
            return {
                "claims": [],
                "evidence": [],
                "final_response": FinalResponse(answer=answer, risk_level="unknown"),
            }

        # 2026-08-12 批 1.5 补做：实体解析失败/候选截断明确告知，
        # 替代通用引导（"请提供公司名称或股票代码"）——用户能知道
        # 系统"看到了"疑似公司但库内无匹配。
        if state.get("candidates_truncated"):
            answer = "候选公司过多（已截断展示）。请补充更完整的公司名称或代码后重试。"
            _emit_segment(state, answer)
            return {
                "final_response": FinalResponse(
                    answer=answer,
                    risk_level="unknown",
                    claims=[],
                    evidence=[],
                )
            }
        if state.get("entity_resolution_error") == "company_not_found":
            if _is_unsupported_market_query(user_query):
                answer = (
                    "当前只支持可识别的单只 A 股行情快照，未覆盖板块、指数、"
                    "期货、基金的行情，也不提供交易建议或市场资金流数据。"
                )
                _emit_segment(state, answer)
                return {
                    "final_response": FinalResponse(answer=answer, risk_level="unknown")
                }
            frags = state.get("unresolved_fragments") or []
            frag_text = "「" + "」「".join(frags[:3]) + "」" if frags else ""
            answer = (
                f"检测到疑似公司{frag_text}但未能识别，请提供完整名称或股票代码。"
                if frags
                else "未能识别到公司，请提供完整名称或股票代码。"
            )
            _emit_segment(state, answer)
            return {
                "final_response": FinalResponse(
                    answer=answer,
                    risk_level="unknown",
                    claims=[],
                    evidence=[],
                )
            }

        if intent == "relation_clarify":
            # v3.1 P0-3：身份已确认但关系不可执行（reference/sequence/
            # ambiguous）→ 澄清主次/先后，不启动模块执行、不进比较引导
            resolution = state.get("entity_resolution_result")
            names = ""
            if resolution is not None and getattr(
                resolution, "selected_companies", None
            ):
                names = "、".join(c.sec_name for c in resolution.selected_companies[:3])
            answer = (
                f"已识别 {names}，但你问题的表述中这些公司的主次或先后关系"
                "不够明确（如'提到''先看''再看'）。请换一种表述，例如"
                "「分析康美药业，顺带看下贵州茅台的公告」或「对比康美药业"
                "和贵州茅台」，我会按明确的主次关系分析。"
                if names
                else "你提到了多家公司，但这些公司的主次或先后关系不够明确，"
                "请换一种表述明确先后（如「先看A，再看B」）或主次（如"
                "「分析A，顺带看B」），我会按明确的关系分析。"
            )
            _emit_segment(state, answer)
            return {
                "final_response": FinalResponse(
                    answer=answer,
                    risk_level="unknown",
                    claims=[],
                    evidence=[],
                )
            }

        if intent == "comparison_guide":
            return _answer_comparison_guide(state)

        # v3.3.3 收口批次 F：comparison 场景 Resolver 派生 company=None
        # （targets 承载两家公司），light_comparison 必须在无 company
        # 分支也可达，否则官方双公司原题落通用 fallback
        if intent == "light_comparison":
            return _answer_light_comparison(state)

        if intent == "company_disambiguation":
            candidates = state.get("company_candidates", [])
            options = "、".join(
                f"{item.sec_name}（{item.wind_code}）" for item in candidates
            )
            # 8/16 语义裁决启用（suggest）：LLM 消歧推荐展示，不自动绑定
            suggested = state.get("suggested_company_code", "")
            hint = ""
            if suggested:
                for item in candidates:
                    if item.wind_code == suggested:
                        hint = f"（建议选择：{item.sec_name} {item.wind_code}）"
                        break
            answer = f"找到多个可能的公司：{options}。请选择一家后继续分析。"
            if hint:
                answer = f"找到多个可能的公司：{options}。{hint}请选择一家后继续分析。"
            _emit_segment(state, answer)
            return {
                "final_response": FinalResponse(
                    answer=answer,
                    risk_level="unknown",
                    claims=[],
                    evidence=[],
                )
            }

        # 寒暄/引导意图：先于研报检索处理（同学反馈"你好"答非所问）
        if intent == "chitchat":
            ql = user_query.lower()
            if any(kw in ql for kw in _THANKS_KW):
                chitchat_answer = (
                    "不客气。需要继续核查时，请告诉我上市公司名称或股票代码。"
                )
            elif any(kw in ql for kw in _FAREWELL_KW):
                chitchat_answer = "再见。之后需要核查财务、股权或公告风险时，随时回来。"
            else:
                intro = (
                    "我是织网鉴真，面向个人投资者的财报反欺诈助手。"
                    if any(kw in ql for kw in _CAPABILITY_KW)
                    else "你好！我是织网鉴真。"
                )
                chitchat_answer = (
                    f"{intro}我可以核查财务勾稽、股权控制链和公告舆情。\n"
                    "你可以这样问：\n"
                    "- 分析康美药业 2025 年报的财务异常\n"
                    "- 查看金牌家居的实际控制人链路\n"
                    "- 核对贵州茅台近期公告与财务数据\n"
                    "请输入上市公司名称或股票代码开始分析。"
                )
            _emit_segment(state, chitchat_answer)
            return {
                "final_response": FinalResponse(
                    answer=chitchat_answer,
                    risk_level="unknown",
                    claims=[],
                    evidence=[],
                )
            }
        if intent == "guide":
            ql = user_query.lower()
            if any(kw in ql for kw in _CONTEXT_REQUEST_KW):
                guide_answer = (
                    "我没有找到可延续的公司上下文。请补充上市公司名称或股票代码，"
                    "例如“继续分析康美药业的现金流”。"
                )
            elif any(kw in ql for kw in _CAPABILITY_KW):
                guide_answer = (
                    "我可以核查上市公司的财务勾稽、股权控制链和公告舆情。"
                    "例如可以问“分析康美药业 2025 年报”或“查看金牌家居的实控人链路”。"
                    "请输入上市公司名称或股票代码开始分析。"
                )
            else:
                guide_answer = (
                    "我不直接推荐股票，但可以核查你指定上市公司的财务、股权与公告风险。"
                    "请提供公司名称或股票代码，例如“分析康美药业”或“600518”。"
                )
            _emit_segment(state, guide_answer)
            return {
                "final_response": FinalResponse(
                    answer=guide_answer,
                    risk_level="unknown",
                    claims=[],
                    evidence=[],
                )
            }
        if intent == "unsupported":
            unsupported_answer = (
                "这个问题超出了织网鉴真的服务范围。"
                "我专注于上市公司财务勾稽、股权穿透、公告舆情和行业研报核查。"
                "请输入公司名称、股票代码或具体行业。"
            )
            _emit_segment(state, unsupported_answer)
            return {
                "final_response": FinalResponse(
                    answer=unsupported_answer,
                    risk_level="unknown",
                    claims=[],
                    evidence=[],
                )
            }

        # Phase D #10: 行业级研报问题（无公司也能检索，如"白酒行业近期研报观点"）
        runtime = state.get("runtime")
        turn_id = getattr(runtime, "turn_id", "") if runtime else ""
        trace_id = getattr(runtime, "trace_id", "") if runtime else ""
        as_of = plan.as_of.strftime("%Y%m%d") if plan and plan.as_of else ""
        try:
            from app.application.services.research_search import (
                is_research_query,
                report_insights_enabled,
                search_research_insights_sync,
            )

            if (
                intent == "research" or is_research_query(user_query)
            ) and report_insights_enabled():
                list_query = any(
                    cue in user_query
                    for cue in (
                        "哪些个股",
                        "竞争者",
                        "竞争对手",
                        "新兴公司",
                        "新兴企业",
                        "有哪些公司",
                        "公司有哪些",
                        "板块有哪些",
                        "行业有哪些",
                    )
                )
                insights = search_research_insights_sync(
                    user_query, top_k=8 if list_query else 3, as_of=as_of
                )
                # 8/23（row 1085 同款，company None 分支补齐）：单公司研报
                # 询问（"XX近期有研报吗"）但实体解析失败（库内名称缺失如
                # 成飞集成→中航成飞）时，检索会命中近名/他司研报——渲染
                # 泛化摘要答非所问，诚实拒答优于冒充答案。
                if re.search(
                    r"[\u4e00-\u9fff]{2,12}(?:近期|最近)?(?:有|有没有)(?:什么)?研报",
                    user_query,
                ):
                    insights = []
                # P2-1：先过滤可回查结果——只渲染成功生成 Evidence 的 insight
                research_evidence, research_claims, valid_insights = (
                    _research_evidence_and_claims(
                        insights,
                        company_code="",
                        turn_id=turn_id,
                        trace_id=trace_id,
                    )
                )
                if valid_insights:
                    parts = _format_research_insights(user_query, valid_insights)
                    # 8/23 展示修复：表格必须与引导语分行（Markdown 表格
                    # 解析要求表头前有空行/换行），否则前端渲染为原始竖线文本
                    answer = (
                        "当前问题未指定具体公司，以下是相关研报观点摘要：\n\n"
                        + parts.rstrip("。")
                        + "\n如需针对某家公司分析，请提供公司名称或股票代码。"
                    )
                    # #4：研报可回查 Evidence + research Claim（写入 AgentState + FinalResponse）
                    _emit_segment(state, answer)
                    return {
                        "final_response": FinalResponse(
                            answer=answer,
                            risk_level="unknown",
                            claims=research_claims,
                            evidence=research_evidence,
                        ),
                        "claims": research_claims,
                        "evidence": research_evidence,
                    }
        except Exception:  # noqa: BLE001 — 研报检索失败不影响主流程
            logger.warning(
                "generate_answer: 行业研报检索失败，回退提示语", exc_info=True
            )

        if intent == "research":
            fallback = (
                "当前数据覆盖范围内未找到与该主题匹配且可回查的研报。"
                "请补充更具体的行业、公司名称或研报关键词后重试。"
            )
            _emit_segment(state, fallback)
            return {
                "final_response": FinalResponse(
                    answer=fallback,
                    risk_level="unknown",
                    claims=[],
                    evidence=[],
                )
            }

        fallback = "未能在数据覆盖范围内找到匹配的公司，请提供完整公司名称或股票代码。"
        _emit_segment(state, fallback)
        return {
            "final_response": FinalResponse(
                answer=fallback,
                risk_level="unknown",
                claims=[],
                evidence=[],
            )
        }

    # R9：公司事实轻量回答（company_fact plan：requested_modules=[]，
    # 未执行 finance/equity/events/risk；诚实回答 + registry Evidence）
    plan = state.get("plan")
    if getattr(plan, "intent", "") == "research":
        return _answer_company_research(state)
    # 8/23 follow-up 定向路由：系统生成的规则明细 follow-up 文案
    # （"查看其他应收款明细"等）→ 直接渲染对应规则指标明细，不重新
    # 执行综合分析（点击 follow-up 后答非所问的修复）。
    if getattr(plan, "intent", "") == "rule_detail":
        return _answer_rule_detail(state, getattr(plan, "rule_id", "") or "")
    if getattr(plan, "intent", "") == "industry_benchmark":
        return _answer_industry_benchmark(state)
    if getattr(plan, "intent", "") == "market_quote":
        return _answer_market_quote(state, getattr(plan, "market_field", "") or "")
    if getattr(plan, "intent", "") == "unsupported":
        answer = (
            "这个问题超出了织网鉴真的服务范围。我专注于上市公司财务勾稽、"
            "股权穿透、公告舆情和行业研报核查。"
        )
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(answer=answer, risk_level="unknown"),
        }
    if getattr(plan, "intent", "") in ("investment_advice", "trade_execution"):
        name_code = f"{company.sec_name}（{company.wind_code}）"
        boundary = (
            f"{name_code}：系统不能代为买卖证券或提交交易指令。"
            if plan.intent == "trade_execution"
            else f"{name_code}：系统不提供是否买入或卖出的投资建议。"
        )
        answer = (
            boundary + "可以继续查询客观行情，或核查财务、股权与公告风险后自行判断。"
        )
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(answer=answer, risk_level="unknown"),
        }
    if getattr(plan, "intent", "") == "causal_query":
        answer = "当前系统不接入行情价格因果归因，无法仅凭财报、股权和公告模块确认这次涨跌原因。"
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(answer=answer, risk_level="unknown"),
        }
    query = state.get("user_query", "")
    if getattr(plan, "intent", "") == "unsupported_indicator":
        answer = f"当前数据覆盖范围暂不支持查询「{query}」，无法可靠返回该指标。"
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(answer=answer, risk_level="unknown"),
        }
    if getattr(plan, "intent", "") == "unsupported_scope" or any(
        keyword in query for keyword in _CONSOLIDATED_SCOPE_KW
    ):
        if "行业" in query and re.search(r"所属|所在", query):
            answer = (
                "当前行业基准只提供行业均值和分位，未覆盖该行业的整体汇总或个股排名，"
                "无法可靠回答这项行业统计。"
            )
        else:
            answer = (
                "当前系统固定使用母公司报表口径，不能切换为合并口径。"
                "本轮不返回可能被误解为合并口径的分析结果。"
            )
        _emit_segment(state, answer)
        return {
            "claims": [],
            "evidence": [],
            "final_response": FinalResponse(answer=answer, risk_level="unknown"),
        }
    # v3.3.3 批次 D：company 已识别但比较维度走页面的场景（单主体行业
    # 对比 → comparison_guide）——guide 分支在 company None 块内，
    # 此处补 company 非 None 的调用
    if getattr(plan, "intent", "") == "comparison_guide":
        return _answer_comparison_guide(state)
    directional_events = _answer_directional_events(state)
    if directional_events is not None:
        return directional_events
    if getattr(plan, "intent", "") == "indicator":
        return _answer_indicator(state, getattr(plan, "indicator", "") or "")
    # v3.3.3 批次 C：结构化轻量比较（同主体跨指标；批次 D 扩展跨公司）
    if getattr(plan, "intent", "") == "light_comparison":
        return _answer_light_comparison(state)
    if getattr(plan, "intent", "") == "company_fact":
        return _answer_company_fact(state, getattr(plan, "fact_key", "") or "")
    if getattr(plan, "intent", "") == "multi_metric":
        return _answer_multi_metric(state)
    if getattr(plan, "answer_target", "") == "risk_level":
        return _answer_risk_level(state)

    # ① 一句话结论（Phase C：Finance 执行时限定母公司报表口径；
    # #11 AnswerMode：按意图选择开场模板，不再一律"综合分析完成"）
    # #8：风险计数只统计叶子信号（排除综合 risk Claim 与绿色控制链）
    risk_count = len(_leaf_risk_claims(claims))
    degraded_summary = _degraded_module_summary(state)
    mode = _select_answer_mode(state, claims, finance_ran, finance_blocked)
    name_code = f"{company.sec_name}（{company.wind_code}）"
    if mode == "fraud_diagnosis":
        if risk_count:
            conclusion = (
                name_code + f"针对造假/舞弊疑点，共检测到 {risk_count} 项规则信号。"
            )
        elif degraded_summary:
            conclusion = (
                name_code
                + f"针对造假/舞弊疑点，本轮分析未完整完成（{degraded_summary}），"
                + "无法确认是否存在造假事实或异常信号。"
            )
        else:
            conclusion = name_code + "针对造假/舞弊疑点，当前证据未能认定存在造假事实。"
    elif mode == "equity":
        conclusion = (
            name_code
            + "股权穿透分析完成，"
            + (
                f"发现 {risk_count} 项股权风险信号。"
                if risk_count
                else (
                    f"本轮分析未完整完成（{degraded_summary}），无法确认是否存在股权风险信号。"
                    if degraded_summary
                    else "未发现股权风险信号。"
                )
            )
        )
    elif mode == "events":
        conclusion = (
            name_code
            + "舆情与事件分析完成，"
            + (
                f"检测到 {risk_count} 项风险信号。"
                if risk_count
                else (
                    f"本轮分析未完整完成（{degraded_summary}），无法确认是否存在明显异常信号。"
                    if degraded_summary
                    else "未发现明显异常信号。"
                )
            )
        )
    elif risk_count:
        if finance_ran:
            # 口径限定：本分析基于母公司报表及当前数据覆盖
            conclusion = (
                name_code + "综合分析完成，" + RISK_SIGNAL_IN_SCOPE.format(n=risk_count)
            )
        else:
            conclusion = name_code + f"综合分析完成，共检测到 {risk_count} 项风险信号。"
    elif finance_unknown_type:
        # 公司类型缺失：不得输出"未发现风险"
        conclusion = (
            name_code
            + "公司类型信息缺失，无法执行非金融财务规则，无法确认是否存在财务风险。"
        )
    elif finance_blocked:
        conclusion = (
            name_code + "在母公司报表及当前数据覆盖范围内，财务规则因不适用/数据不足"
            "未产出有效信号，未发现可确认的异常信号。"
        )
    elif degraded_summary:
        conclusion = (
            name_code
            + f"本轮分析未完整完成（{degraded_summary}），无法确认是否存在明显异常信号。"
        )
    elif finance_ran:
        conclusion = name_code + NO_SIGNAL_IN_SCOPE
    else:
        conclusion = name_code + "未发现明显异常信号。"

    # ② 多类核心信号摘要（含评级/交叉验证/综合风险）
    risk_output = state.get("risk_output")
    results = state.get("results")
    summary = _build_signal_summary(claims, results=results, risk_output=risk_output)
    # ③ 财务触发规则明细（V12 §4.3 规则触发清单）
    rule_details = _build_rule_details(state)

    # 分段组装（真流式：每构造完一个真实分层立即 push，再拼接完整 answer）
    segments: list[str] = []

    def append_segment(text: str) -> None:
        if not text:
            return
        rendered = text.strip()
        if segments:
            rendered = "\n\n" + rendered
        segments.append(rendered)
        _emit_segment(state, rendered)

    append_segment(conclusion)
    requested_period = getattr(plan, "requested_period_text", "") if plan else ""
    financial_claims = [
        c for c in claims if getattr(c, "claim_type", "") == "financial"
    ]
    if (
        requested_period
        and getattr(plan, "as_of_kind", "") == "report_period"
        and not financial_claims
    ):
        append_segment(
            f"未提取到{requested_period}可核验的财务指标；本次股权或事件信号"
            "不能替代该报告期的财务分析。"
        )
    # 8/22 晚全量 1410（row 729/710）：有财务 claims 但数据期早于请求期时
    # 同样要提示——问"2025年一季度季报"不能用 2024-12-31 数据冒充。
    elif requested_period and getattr(plan, "as_of_kind", "") == "report_period":
        req_as_of = getattr(plan, "as_of", None)
        # 数据覆盖期取 risk_output.as_of（证据期最大值，P2-4 契约）
        data_as_of = ""
        risk_output_local = state.get("risk_output")
        if risk_output_local is not None:
            data_as_of = getattr(risk_output_local, "as_of", "") or ""
        if req_as_of and data_as_of and len(data_as_of) >= 8:
            try:
                req_ym = int(req_as_of.strftime("%Y%m"))
                data_ym = int(str(data_as_of)[:6])
                if data_ym < req_ym:
                    append_segment(
                        f"请求期次为「{requested_period}」，但可用财务数据最新仅至 "
                        f"{str(data_as_of)[:4]}-{str(data_as_of)[4:6]}-"
                        f"{str(data_as_of)[6:8]}，请求期数据可能缺失，"
                        "以上信号基于最近可用期。"
                    )
            except (ValueError, TypeError):
                pass
    if summary:
        seg = summary + "。"
        append_segment(seg)
    brief = _build_company_brief_analysis(state, claims, risk_output=risk_output)
    if brief:
        append_segment(brief)
    append_segment(_build_cross_module_observation(state, claims))
    if mode == "equity":
        equity_overview = _build_equity_overview(state)
        append_segment(equity_overview)
    # B2 第二阶段：舆情影响结论段（事件模块有 impacts 才渲染；无则不渲染）
    impact_seg = _build_impact_conclusions_segment(state)
    if impact_seg:
        append_segment(impact_seg)
    if rule_details:
        append_segment(rule_details)
    # #7/#12：确定性四段解读（无 LLM 自由生成；仅消费规则引擎 explanation/
    # current 与 pattern_matches；含 #9 免责段）
    for seg in _build_interpretation_segments(state, claims):
        append_segment(seg)

    # Phase D #10: 研报/公告语义检索（问题涉及研报/行业/评级时可选调用）
    user_query = state.get("user_query", "")
    research_seg = ""
    research_claims: list = []
    research_evidence: list = []
    try:
        from app.application.services.research_search import (
            is_research_query,
            report_insights_enabled,
            search_research_insights_sync,
        )

        if is_research_query(user_query) and report_insights_enabled():
            plan_r = state.get("plan")
            as_of_r = plan_r.as_of.strftime("%Y%m%d") if plan_r and plan_r.as_of else ""
            list_query = any(
                cue in user_query
                for cue in (
                    "哪些个股",
                    "竞争者",
                    "竞争对手",
                    "新兴公司",
                    "新兴企业",
                    "值得关注",
                )
            )
            insights = search_research_insights_sync(
                user_query, top_k=8 if list_query else 3, as_of=as_of_r
            )
            # 8/22 晚全量 1410（row 360 海能达→春风动力 / 1085 成飞集成→
            # 中航成飞）：问题含公司名时按公司过滤，杜绝他司研报冒充。
            if company is not None:
                from app.agents.nodes._answer_research import (
                    filter_insights_by_company,
                )

                insights = filter_insights_by_company(
                    insights,
                    wind_code=company.wind_code or "",
                    sec_name=company.sec_name or "",
                )
            else:
                # row 1085 兜底：单公司研报询问（"XX近期有研报吗"）但实体
                # 解析失败（库内 sec_name 缺失如 002190.SZ 名称=代码）时，
                # 检索会命中近名公司（中航成飞）——诚实拒答优于渲染他司
                # 研报冒充答案（回答端对空 insights 已输出"未找到可回查
                # 研报"）。
                import re as _re

                if _re.search(
                    r"[\u4e00-\u9fff]{2,12}(?:近期|最近)?(?:有|有没有)(?:什么)?研报",
                    user_query,
                ):
                    insights = []
            # P2-1：先过滤可回查结果，只渲染成功生成 Evidence 的 insight
            company_code_r = company.wind_code if company else ""
            runtime_r = state.get("runtime")
            research_evidence, research_claims, valid_insights = (
                _research_evidence_and_claims(
                    insights,
                    company_code=company_code_r,
                    turn_id=getattr(runtime_r, "turn_id", "") if runtime_r else "",
                    trace_id=getattr(runtime_r, "trace_id", "") if runtime_r else "",
                )
            )
            if valid_insights:
                research_seg = "近期研报观点：\n\n" + _format_research_insights(
                    user_query, valid_insights
                )
                append_segment(research_seg)
    except Exception:  # noqa: BLE001 — 检索失败不影响主回答
        logger.warning("generate_answer: 研报检索段失败，跳过", exc_info=True)

    answer = "".join(segments)

    # #7：LLM 润色默认关闭（确定性输出优先，避免自由生成引入无证据推断）；
    # 保留 _polish_answer（含事实校验回退）供 ANSWER_POLISH_ENABLED 开关启用
    if not streaming and getattr(settings, "ANSWER_POLISH_ENABLED", False):
        answer = _polish_answer(answer)

    # 风险等级：优先使用 risk 节点输出（否则回退 claim 最高严重度）
    risk_level = (
        (getattr(risk_output, "risk_level", "") or _highest_severity(claims))
        if (risk_output is not None or claims)
        else "unknown"
    )

    # #4：研报 Claim/Evidence 合并进 FinalResponse（reducer 会再合并进
    # AgentState，validate_evidence → persist_turn 因此可完整落库/回查）
    final_claims = _merge_unique(claims + research_claims, key=lambda c: c.claim_id)
    final_evidence = _merge_unique(
        evidence + research_evidence, key=lambda e: e.evidence_id
    )

    return {
        "final_response": FinalResponse(
            answer=answer,
            risk_level=risk_level,
            claims=final_claims,
            evidence=final_evidence,
            follow_ups=_build_follow_ups(state),
        ),
        "claims": research_claims,
        "evidence": research_evidence,
    }
