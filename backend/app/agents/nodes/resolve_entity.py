"""ResolveEntity — 实体解析节点（v3.1 冻结方案，步骤 11 删除旧实现后）.

职责（文档 §4）：委托 CompanyEntityResolver（application 层编排），
由权威结果 entity_resolution_result 一次性派生旧 AgentState 字段
（company/company_candidates/comparison_targets 等）。节点不再持有
SQL/Engine/正则词表——候选召回在 infrastructure adapter，语义裁决在
CompanySemanticSelector，复合分段与历史防串在 Resolver。
"""

from __future__ import annotations

import logging

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
from app.application.services.company_span_llm_service import (
    CompanySpanLLMExtractor,
)
from app.application.services.company_resolver import get_company_repository
from app.application.services.query_subject_interpreter import (
    QuerySubjectInterpreter,
)

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

    if not explicit_company_code and detect_chitchat_intent(user_query) in {
        "chitchat",
        "guide",
        "unsupported",
    }:
        return {
            "company": None,
            "company_candidates": [],
            "entity_resolution_result": EntityResolutionResult(
                intent="no_company", reason_code="chitchat"
            ),
        }

    resolver = CompanyEntityResolver(
        get_company_repository(),
        selector=CompanySemanticSelector(),
        # 8/16 语义裁决启用（队长拍板）：mentionness 随全局模式生效——
        # off 零调用；suggest/auto 时 non_company_context 判定应用
        mentionness=CompanyMentionnessClassifier(),
        # 8/17 LLM-NER 子实体提取（业界 NER→链接 第三步）：长 not_found
        # span（施事/介词句式）提取片段内公司名子串 → 二次链接；
        # off 零调用，suggest/auto 启用，失败 fail-closed
        span_extractor=CompanySpanLLMExtractor(),
        # v3.3.2-R1 §7：低置信主体语义解析器——模式读
        # ENTITY_QUERY_INTERPRETER_MODE（off 生产默认零调用；
        # shadow/fallback 经环境变量显式启用）
        interpreter=QuerySubjectInterpreter(),
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
