"""ResolveEntity — 实体解析节点（v3.1 冻结方案，步骤 11 删除旧实现后）.

职责（文档 §4）：委托 CompanyEntityResolver（application 层编排），
由权威结果 entity_resolution_result 一次性派生旧 AgentState 字段
（company/company_candidates/comparison_targets 等）。节点不再持有
SQL/Engine/正则词表——候选召回在 infrastructure adapter，语义裁决在
CompanySemanticSelector，复合分段与历史防串在 Resolver。
"""

from __future__ import annotations

import logging
import re

from app.agents.state import AgentState
from app.application.models.company_resolution import (
    EntityResolutionResult,
    validate_finalized_relation_roles,
)
from app.application.services.company_entity_resolver import CompanyEntityResolver
from app.application.services.company_mentionness_classifier import (
    CompanyMentionnessClassifier,
)
from app.application.services.company_semantic_selector import CompanySemanticSelector
from app.application.services.company_resolver import get_company_repository

logger = logging.getLogger(__name__)


def _derive_legacy_fields(result: EntityResolutionResult) -> dict:
    """由权威结果一次性派生旧 AgentState 字段（v3.1 §4）。

    派生规则（P0-5 契约分流）：
    - single/switch/continuation → company（primary）；
    - comparison → comparison_targets + comparison_requested=True；
    - 恰好 1 个未确认 mention → company_candidates 输出该 mention 候选
      （旧客户端兼容）；≥2 个 → 空（不返回可操作扁平列表）；
    - reference/sequence/ambiguous → relation_clarify（不派生 company）；
    - not_found/needs_refinement → entity_resolution_error + unresolved。
    """
    mentions = result.mentions
    unresolved_mentions = result.unresolved_mentions
    confirmable = [m for m in mentions if m.status == "needs_confirmation"]

    derived: dict = {
        "entity_resolution_result": result,
        "company": None,
        "company_candidates": [],
        "comparison_targets": [],
        "comparison_requested": False,
        "candidates_truncated": any(m.truncated for m in mentions),
        "entity_resolution_error": "",
        "unresolved_fragments": unresolved_mentions,
    }

    if result.intent == "comparison":
        # v3.3 批次 B（P1-5）：comparison_targets 只从已绑定身份的
        # mentions 派生；中间确认态连已锁定的一家也不能单独进入
        # comparison guide。只有严格终态通过后才暴露 comparison 路由。
        finalized = validate_finalized_relation_roles(result.intent, mentions)
        if finalized:
            derived["comparison_targets"] = list(result.selected_companies)
            derived["comparison_requested"] = True
    elif result.intent in ("single", "switch", "continuation"):
        primary = next(
            (m for m in mentions if m.role == "primary" and m.selected_wind_code),
            None,
        )
        if primary is not None:
            for c in primary.candidates:
                if c.company.wind_code == primary.selected_wind_code:
                    derived["company"] = c.company
                    break
        # 派生后仍无 company（防御）→ 取 selected_companies 首家
        if derived["company"] is None and result.selected_companies:
            derived["company"] = result.selected_companies[0]

    # P0-5：恰好一个未确认 mention → 输出旧扁平候选；多 mention → 空
    if len(confirmable) == 1 and confirmable[0].candidates:
        derived["company_candidates"] = [c.company for c in confirmable[0].candidates]
    elif result.needs_confirmation:
        derived["company_candidates"] = []

    # 未识别状态
    if any(m.status == "not_found" for m in mentions):
        derived["entity_resolution_error"] = "company_not_found"
    elif any(m.status == "needs_refinement" for m in mentions):
        derived["entity_resolution_error"] = "too_many_candidates"
    elif result.intent == "no_company" and result.reason_code == "company_not_found":
        derived["entity_resolution_error"] = "company_not_found"

    # 8/16 语义裁决启用（suggest 模式）：LLM 消歧推荐——disambiguation
    # 文案展示"建议选择"（不自动绑定，用户确认兜底 fail-closed）
    suggested_code = ""
    suggestion = result.semantic_suggestion
    if suggestion is not None and result.mentions:
        select_map = {
            d.mention_id: d.selected_wind_code
            for d in suggestion.identity_decisions
            if d.action == "select" and d.selected_wind_code
        }
        for m in result.mentions:
            code = select_map.get(m.mention_id)
            if code:
                suggested_code = code
                break
    derived["suggested_company_code"] = suggested_code
    return derived


def resolve_entity_node(state: AgentState) -> dict:
    """实体解析节点（v3.1 新架构）— 委托 CompanyEntityResolver。

    优先级（服务编排）：request_context.entity_overrides（局部确认重跑）
    > request_context.company_code > query 内嵌代码 > 显式 mention 解析
    > 复合分段 > 语义裁决 > 纯指代/主语省略历史延续 > 未识别防串。
    """
    user_query = state.get("user_query", "")
    request_context = state.get("request_context")
    explicit_company_code = (
        getattr(request_context, "company_code", "") if request_context else ""
    )

    # 高置信寒暄/引导/范围外短路（复用现有检测器，不进实体解析）
    from app.agents.nodes.plan_modules import detect_chitchat_intent

    pre_intent = detect_chitchat_intent(user_query)
    if not explicit_company_code and pre_intent in {"chitchat", "guide"}:
        return {
            "company": None,
            "company_candidates": [],
            "entity_resolution_result": EntityResolutionResult(
                intent="no_company", reason_code="chitchat"
            ),
        }

    # 8/23 follow-up 定向路由：系统生成的 follow-up 文案（"查看其他应收款
    # 明细"/"查看公司事件时间线"/"查看实控人控制的其他上市公司"等）本身
    # 不含公司名，但必须延续会话当前主体——否则"公司/存贷双高/扣非"等词
    # 会被实体提取器当成疑似公司名（"公司"→中金公司/中微公司），落
    # entity_error/company_disambiguation 答非所问。
    # 保护：query 含明确公司名/代码时不得短路（"查看海能达的其他应收款
    # 明细"必须解析出海能达，而不是沿用上一轮主体）。
    from app.agents.nodes.plan_modules import (
        _detect_rule_detail_follow_up,
        _detect_system_follow_up,
    )

    has_explicit_code_in_query = bool(
        re.search(r"(?<!\d)\d{6}(?:\.[A-Za-z]{2})?(?!\d)", user_query)
    )
    if (
        not explicit_company_code
        and not has_explicit_code_in_query
        and _detect_system_follow_up(user_query)
    ):
        from app.application.services.exact_company_spotter import (
            spot_exact_company_spans,
        )

        if not spot_exact_company_spans(user_query):
            memory_context = state.get("memory_context")
            current_code = ""
            if memory_context is not None:
                current_code = str(
                    getattr(memory_context, "current_company_code", "") or ""
                ).strip()
                if not current_code:
                    prev = getattr(memory_context, "previous_company_codes", None) or []
                    current_code = str(prev[0]).strip() if prev else ""
            if current_code:
                resolver = CompanyEntityResolver(
                    get_company_repository(),
                    selector=CompanySemanticSelector(),
                    mentionness=CompanyMentionnessClassifier(),
                )
                company = resolver._resolve_code_or_name(current_code)
                if company is not None:
                    return {
                        "company": company,
                        "company_candidates": [],
                        "comparison_targets": [],
                        "comparison_requested": False,
                        "candidates_truncated": False,
                        "entity_resolution_error": "",
                        "unresolved_fragments": [],
                        "suggested_company_code": "",
                        "entity_resolution_result": resolver._history_result(
                            company, "follow_up_system"
                        ),
                    }
            # 无当前主体：交给 plan_modules 走 guide（要求先提供公司名）
            return {
                "company": None,
                "company_candidates": [],
                "entity_resolution_result": EntityResolutionResult(
                    intent="no_company", reason_code="chitchat"
                ),
            }

    from app.application.services.market_quote_service import (
        detect_market_quote_field,
    )

    market_field = detect_market_quote_field(user_query)
    unsupported_market_query = pre_intent == "unsupported"
    memory_context = state.get("memory_context")
    has_current_company = bool(
        getattr(memory_context, "current_company_code", "")
        or getattr(memory_context, "resolved_company_code", "")
        or (getattr(memory_context, "previous_company_codes", None) or [])
    )
    has_exact_company = False
    if (unsupported_market_query or market_field) and not explicit_company_code:
        # 无主体的市场级问题可以直接拒答；含明确公司名时仍需先解析主体，
        # 例如“商品价格对某公司业绩影响”不能被市场级词提前吞掉。
        from app.application.services.exact_company_spotter import (
            spot_exact_company_spans,
        )

        has_exact_company = bool(spot_exact_company_spans(user_query))
    has_explicit_code = bool(
        re.search(r"(?<!\d)\d{6}(?:\.[A-Za-z]{2})?(?!\d)", user_query)
    )
    if (
        not explicit_company_code
        and not has_exact_company
        and not has_explicit_code
        and not has_current_company
    ):
        # 无主体的行情字段不能进入实体召回，否则整句会被当成疑似公司。
        if market_field:
            return {
                "company": None,
                "company_candidates": [],
                "entity_resolution_result": EntityResolutionResult(
                    intent="no_company", reason_code="company_not_found"
                ),
            }
    if not explicit_company_code and not has_exact_company and not has_explicit_code:
        from app.application.services.market_quote_service import (
            detect_market_quote_field,
        )

        # 无主体的行情字段不能进入实体召回，否则整句会被当成疑似公司。
        # 但有结构化当前主体时，允许裸字段追问进入 resolver 的延续逻辑。
        if detect_market_quote_field(user_query) and not has_current_company:
            return {
                "company": None,
                "company_candidates": [],
                "entity_resolution_result": EntityResolutionResult(
                    intent="no_company", reason_code="company_not_found"
                ),
            }
    if not explicit_company_code and unsupported_market_query and not has_exact_company:
        return {
            "company": None,
            "company_candidates": [],
            "entity_resolution_result": EntityResolutionResult(
                intent="no_company", reason_code="chitchat"
            ),
        }

    # 行业/板块/产业主题没有显式公司名时，不继承上一轮主体，也不把主题词
    # 当公司候选。精确公司名仍由同一名称索引判断。
    if any(
        marker in user_query
        for marker in (
            "行业",
            "板块",
            "产业",
            "概念",
            "题材",
            "政策",
            "技术",
            "研发",
            "工艺",
            "应用领域",
        )
    ) and not any(marker in user_query for marker in ("所属", "所在")):
        from app.application.services.exact_company_spotter import (
            spot_exact_company_spans,
        )

        if not spot_exact_company_spans(user_query):
            return {
                "company": None,
                "company_candidates": [],
                "entity_resolution_result": EntityResolutionResult(
                    intent="no_company", reason_code="industry_context"
                ),
            }

    resolver = CompanyEntityResolver(
        get_company_repository(),
        selector=CompanySemanticSelector(),
        # 8/16 语义裁决启用（队长拍板）：mentionness 随全局模式生效——
        # off 零调用；suggest/auto 时 non_company_context 判定 + sub_span
        # 子实体提取（8/17 收敛 A：合并原独立 span_extractor 组件）应用
        mentionness=CompanyMentionnessClassifier(),
        # 8/17 收敛 B：QuerySubjectInterpreter 下线（从未被验证应用：
        # fallback 实测不稳定，off 恒零调用）——不注入，resolver 内
        # interpreter 分支成为死路径（保留代码待后续清理）
    )
    result = resolver.resolve(
        user_query,
        memory=state.get("memory_context"),
        request_context=request_context,
    )
    derived = _derive_legacy_fields(result)
    logger.info(
        "ResolveEntity: intent=%s mentions=%d selected=%d confirm=%s status=%s "
        "interp=%s",
        result.intent,
        len(result.mentions),
        len(result.selected_companies),
        result.needs_confirmation,
        result.selector_status,
        result.subject_interpreter_status,
    )
    return derived
