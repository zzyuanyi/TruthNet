"""CompanySemanticSelector — 受约束 LLM 语义裁决（v3.1 冻结方案 §5/P1-1）.

职责：
- 仅在歧义场景调用（candidate_ambiguity OR relation_ambiguity OR
  segmentation_ambiguity）；高置信确定性场景零调用；
- 结构化输出 SemanticDecision（identity 与 role 拆分，P1-1）；
- 程序校验：mention_id ∈ 输入、selected ∈ 该 mention 候选集、
  role 覆盖全部采用 mention、relation/role 一致性；任一不合法 →
  整体 selector_status=invalid，不部分静默接受；
- mock / ENTITY_SEMANTIC_SELECTION_MODE=off → disabled（0 次调用）；
- suggest：记录选择但不绑定（用户确认）；auto：allowlist 内合法选择
  直接绑定；
- 超时/异常/空 → timeout，确定性降级（候选确认），不串历史主体。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from app.application.models.company_resolution import (
    EntityMention,
    SegmentationAlternative,
    SemanticDecision,
    SelectorStatus,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

# 锁定类状态：不接受 identity decision（P1-1）
_LOCKED_STATUSES = {"auto_selected", "llm_selected", "user_confirmed"}

# 允许 LLM 进行身份选择的 mention 状态（P1-3：截断/空候选不交 LLM）
_AMBIGUOUS_STATUSES = {"needs_confirmation"}


@dataclass(frozen=True)
class ValidatedSemanticDecision:
    """v3.3.1 §6.1：verifier 的完整验证快照（输入对象零修改）。

    - adopted_mentions：完成 selected alternative 替换与 identity/role
      模拟后的最终 mentions（全部为深拷贝，替换父已删除，子 mention
      为被选方案子 mention 的深拷贝）；not_found 与 abstain 父保留；
    - unresolved_parent_ids：segmentation abstain 的父 mention ID
      （保留在原 mentions 中，由 Resolver 做无查询纯降级）。
    auto 路径只能整体采用 adopted_mentions，不得重新 _finalize_span。
    """

    decision: SemanticDecision
    adopted_mentions: tuple[EntityMention, ...]
    unresolved_parent_ids: tuple[str, ...]


def _recent_context_text(memory) -> str:
    """最近明确主体/最近一轮上下文（只传必要信息，不传整表）。"""
    parts: list[str] = []
    if memory is not None:
        code = str(getattr(memory, "resolved_company_code", "") or "").strip()
        name = str(getattr(memory, "resolved_entity_name", "") or "").strip()
        if code:
            parts.append(f"最近明确主体代码: {code}")
        if name:
            parts.append(f"最近明确主体名称: {name}")
    return "；".join(parts)


def _build_messages(
    user_query: str,
    mentions: list[EntityMention],
    alternatives: list[SegmentationAlternative] | None,
    recent_context: str,
    current_relation: str = "",
) -> list[dict]:
    """构造语义裁决提示词。

    只传：原问题、当前确定性 relation（供复核与审计）、最近主体、
    每个 mention 原文/偏移/候选（wind_code/sec_name/industry_l1/exchange/
    match_kind/rank）、locked 标记、按父分组的分段方案（子 mention 显式
    携带 mention_id/start/end/完整候选）。不传整表。
    """
    mention_lines: list[str] = []
    for m in mentions:
        locked = (
            "locked（身份已确定，不可改写）" if m.status in _LOCKED_STATUSES else ""
        )
        cand_lines = [
            f"      - {c.company.wind_code} | {c.company.sec_name} | "
            f"行业:{c.company.industry_l1 or '未知'} | 交易所:{c.company.exchange or '未知'} "
            f"| kind:{c.match_kind} rank:{c.rank}"
            for c in m.candidates
        ]
        mention_lines.append(
            f"  mention_id={m.mention_id} 原文='{m.text}' ({m.start}:{m.end}) "
            f"{locked}\n"
            + (
                "\n".join(cand_lines)
                if cand_lines
                else "      （无候选，不得虚构代码）"
            )
        )

    # v3.3.1 §6.5：alternative 子 mention 必须携带完整候选 allowlist
    # （code/名称/匹配来源/rank），LLM 才能基于 allowlist 做子身份选择
    alt_lines: list[str] = []
    if alternatives:
        for alt in alternatives:
            sub_blocks: list[str] = []
            for m in alt.mentions:
                sub_lines = [
                    f"      - {c.company.wind_code} | {c.company.sec_name} | "
                    f"行业:{c.company.industry_l1 or '未知'} | 交易所:"
                    f"{c.company.exchange or '未知'} | kind:{c.match_kind} "
                    f"rank:{c.rank}"
                    for c in m.candidates
                ]
                sub_blocks.append(
                    f"    sub {m.mention_id}:'{m.text}'({m.start}:{m.end}) "
                    f"status={m.status}\n" + ("\n".join(sub_lines) if sub_lines else "")
                )
            alt_lines.append(
                f"  parent={alt.parent_mention_id} {alt.alternative_id}:\n"
                + "\n".join(sub_blocks)
            )

    system = (
        "你是财报问答系统的公司实体语义裁决器。用户问题可能涉及多家公司，"
        "或单个公司名称存在多个候选。你的任务：\n"
        "1. 判断关系 relation（single/comparison/reference/sequence/switch/"
        "continuation/no_company/ambiguous）；\n"
        "2. 只对标记为待确认（非 locked）的 mention 选择候选公司（identity "
        "decision），selected_wind_code 必须来自该 mention 的候选列表；\n"
        "3. 为所有 mention 分配 role（primary/comparison_peer/referenced）；\n"
        "4. 存在分段歧义时，为每个父 mention 输出一条 segmentation_decision"
        "（action=select/abstain；select 的 alternative_id 必须来自该父"
        " mention 的方案列表）。\n"
        "约束：\n"
        "- 绝不能生成候选列表之外的 wind_code；\n"
        "- 绝不能改写 locked mention 的身份（locked 不得出现在 identity "
        "decisions 中）；\n"
        "- 候选为空或只有一条时输出 abstain；\n"
        "- 可结合问题中的业务语义选择：如'存贷/存款/贷款'通常指银行、"
        "'理赔/保险'指保险公司、'经纪/承销'指证券公司；仍不确定时 "
        "abstain，不要猜测；\n"
        "- 只有一个 mention（一个候选组）时，relation 只能是 single（或 "
        "abstain 时 ambiguous），绝不能是 comparison；\n"
        "- '分析康美提到茅台的公告' 类主次不明 → relation=reference；\n"
        "- '先看康美，再分析茅台' 类先后不明 → relation=sequence；\n"
        "- 两家公司并列对比 → relation=comparison；\n"
        "- 不确定时 relation=ambiguous 且 abstain，不要猜测。\n"
        "输出 JSON 必须严格符合给定 schema。"
    )
    user_content = (
        f"用户问题：{user_query}\n"
        f"当前确定性 relation：{current_relation or '（无）'}\n"
        f"上下文：{recent_context or '（无）'}\n"
        f"mention 与候选：\n"
        + "\n".join(mention_lines)
        + (
            "\n分段方案（按父 mention 分组）：\n" + "\n".join(alt_lines)
            if alt_lines
            else ""
        )
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]


def _repair_messages(
    messages: list[dict],
    decision: SemanticDecision,
    error: str,
    current_relation: str = "",
) -> list[dict]:
    """v3.3.1 §6.5 repair：不得丢失第一次的原始用户消息与候选列表。

    序列：system → 原始 user payload（全部候选）→ assistant 上一轮
    invalid 输出 → user 精确错误与修复指令。
    """
    repair = (
        f"你上一次输出未通过程序校验：{error}\n"
        f"当前确定性 relation：{current_relation or '（无）'}\n"
        "请严格对照上方候选列表与约束修正后重新输出完整 JSON。"
    )
    return [
        messages[0],
        messages[1],
        {"role": "assistant", "content": decision.model_dump_json()},
        {"role": "user", "content": repair},
    ]


def validate_semantic_decision(
    decision: SemanticDecision,
    mentions: list[EntityMention],
    alternatives: list[SegmentationAlternative] | None,
) -> tuple[ValidatedSemanticDecision | None, str]:
    """v3.3.1 §6：完整不变量校验（§6.1 物化顺序 / §6.2-6.4 语义）。

    顺序（全部在深拷贝副本上执行，通过后返回验证快照；输入
    mentions/alternatives/decision 无论成功失败均零修改）：
      1. 输入 mention_id 无重复；
      2. 分段 decisions：按父分组、每父恰好一条、select 的 alternative
         属于对应 parent；物化 adopted（被选方案子 mention 深拷贝替换父，
         父 ID 从索引删除）；abstain 父保留且登记 unresolved；
      3. identity decisions：待裁决集合 = needs_confirmation + 候选
         非空 + 非 truncated + 非 abstain 父；每项恰好一条、无重复/
         未知/locked、select 属于 allowlist、abstain 不带 code；
      4. role assignments：覆盖全部 adopted 公司 mention（not_found 与
         abstain 父除外）、无未知/重复；
      5. relation/role/最终 code 一致性（§6.4 全 8 值覆盖；ambiguous
         允许已有 locked、禁止本次新增绑定）。

    任一失败 → (None, 原因)，调用方整体降级（selector_status=invalid），
    不部分接受。
    """
    # ── 1. 输入 mention 无重复 ──
    by_id = {m.mention_id: m for m in mentions}
    if len(by_id) != len(mentions):
        return None, "重复 mention_id"

    # ── 2. 分段裁决（按父分组）→ 物化 adopted mentions ──
    alt_by_parent: dict[str, list[SegmentationAlternative]] = {}
    for a in alternatives or []:
        alt_by_parent.setdefault(a.parent_mention_id, []).append(a)
    if alt_by_parent and not decision.segmentation_decisions:
        return None, "存在分段歧义但无 segmentation_decisions"
    if not alt_by_parent and decision.segmentation_decisions:
        return None, "无分段歧义却返回 segmentation_decisions"
    seen_parents: set[str] = set()
    abstained_parents: set[str] = set()
    for sd in decision.segmentation_decisions:
        if sd.parent_mention_id in seen_parents:
            return None, f"重复分段裁决: {sd.parent_mention_id}"
        seen_parents.add(sd.parent_mention_id)
        parent_alts = alt_by_parent.get(sd.parent_mention_id)
        if parent_alts is None:
            return None, f"未知分段父 mention: {sd.parent_mention_id}"
        if sd.action == "select":
            valid_ids = {a.alternative_id for a in parent_alts}
            if not sd.alternative_id or sd.alternative_id not in valid_ids:
                return None, f"越界 alternative_id: {sd.alternative_id}"
        elif sd.action == "abstain":
            # v3.3.1 §6.2：合法弃权路径（保留父，不要求其 identity/role）
            abstained_parents.add(sd.parent_mention_id)
        else:
            return None, f"非法分段 action: {sd.action}"
    for parent_id in alt_by_parent:
        if parent_id not in seen_parents:
            return None, f"分段父 mention 缺 decision: {parent_id}"

    # 物化副本：深拷贝输入 mentions；被选方案子 mention 深拷贝后替换父
    # （v3.3.1 §6.1：禁止原对象引用，模拟赋值不得污染 alternative）
    adopted = [m.model_copy(deep=True) for m in mentions]
    adopted_by_id = {m.mention_id: m for m in adopted}
    for sd in decision.segmentation_decisions:
        if sd.action != "select":
            continue
        chosen = next(
            a
            for a in alt_by_parent[sd.parent_mention_id]
            if a.alternative_id == sd.alternative_id
        )
        parent = adopted_by_id.get(sd.parent_mention_id)
        if parent is None:
            return None, f"分段父 mention 不在输入: {sd.parent_mention_id}"
        if parent.candidates:
            return None, f"分段父 mention 不应有候选: {sd.parent_mention_id}"
        adopted.remove(parent)
        del adopted_by_id[sd.parent_mention_id]  # §6.1 步骤 4
        for sub in chosen.mentions:
            if sub.mention_id in adopted_by_id:
                return None, f"子 mention 与既有 ID 冲突: {sub.mention_id}"
            copied_sub = sub.model_copy(deep=True)
            adopted_by_id[copied_sub.mention_id] = copied_sub
            adopted.append(copied_sub)

    # ── 3. identity decisions（§6.3 待裁决集合）──
    pending_ids = [
        m.mention_id
        for m in adopted
        if m.status == "needs_confirmation"
        and m.candidates
        and not m.truncated
        and m.mention_id not in abstained_parents
    ]
    covered: set[str] = set()
    for d in decision.identity_decisions:
        if d.mention_id in covered:
            return None, f"重复 identity decision: {d.mention_id}"
        covered.add(d.mention_id)
        m = adopted_by_id.get(d.mention_id)
        if m is None:
            return None, f"未知 mention_id: {d.mention_id}"
        if m.status not in _AMBIGUOUS_STATUSES:
            # locked（auto_selected/llm_selected/user_confirmed）出现在
            # identity decisions → 整体 invalid（v3.3：不再静默忽略）
            return (
                None,
                f"locked mention 不得出现在 identity decisions: {d.mention_id}",
            )
        if m.truncated or not m.candidates:
            return None, f"truncated/零候选 mention 禁止 LLM 裁决: {d.mention_id}"
        if m.mention_id in abstained_parents:
            return None, f"segmentation abstain 父禁止 identity 裁决: {d.mention_id}"
        if d.action == "select":
            if not d.selected_wind_code:
                return None, f"select 缺少 wind_code: {d.mention_id}"
            allowed = {c.company.wind_code for c in m.candidates}
            if d.selected_wind_code not in allowed:
                return None, f"库外 wind_code: {d.selected_wind_code}"
        elif d.action == "abstain":
            if d.selected_wind_code:
                return None, f"abstain 不得携带 wind_code: {d.mention_id}"
        else:
            return None, f"非法 action: {d.action}"
    missing = [mid for mid in pending_ids if mid not in covered]
    if missing:
        return None, f"待裁决 mention 缺 identity decision: {missing}"

    # ── 4. role assignments：覆盖要求（abstain 父除外，§6.2）──
    roles: dict[str, str] = {}
    for r in decision.role_assignments:
        if r.mention_id not in adopted_by_id:
            return None, f"未知 role mention_id: {r.mention_id}"
        if r.mention_id in roles:
            return None, f"重复 role: {r.mention_id}"
        roles[r.mention_id] = r.role
    for m in adopted:
        if m.status == "not_found":
            continue
        if m.mention_id in abstained_parents:
            continue  # v3.3.1 §6.2：abstain 父不要求 role
        if m.mention_id not in roles:
            return None, f"role 缺失: {m.mention_id}"

    # ── 5. 模拟 identity + role 到副本（输入对象零修改）──
    for d in decision.identity_decisions:
        if d.action == "select":
            adopted_by_id[d.mention_id].selected_wind_code = d.selected_wind_code
    for r in decision.role_assignments:
        adopted_by_id[r.mention_id].role = r.role

    # ── 6. relation 一致性（§6.4 全 8 值；locked 与新增绑定区分）──
    bound = [m for m in adopted if m.selected_wind_code]
    primaries = [m for m in adopted if m.role == "primary"]
    new_select_ids = {
        d.mention_id for d in decision.identity_decisions if d.action == "select"
    }
    if decision.relation in ("single", "continuation", "switch"):
        if len(bound) != 1 or len(primaries) != 1:
            return None, f"{decision.relation} 需要恰好一个已绑定 primary"
    elif decision.relation == "comparison":
        codes = [m.selected_wind_code for m in adopted if m.selected_wind_code]
        if len(adopted) < 2 or len(codes) < 2 or len(set(codes)) < 2:
            return None, "comparison 需要至少两个不同 code 且全部绑定"
        if len(primaries) != 1:
            return None, "comparison 需要恰好一个 primary"
        if any(
            m.role != "comparison_peer"
            for m in adopted
            if m.role != "primary" and m.role is not None
        ):
            return None, "comparison 其余 mention 必须全部 comparison_peer"
    elif decision.relation in ("reference", "sequence"):
        # v3.3.1 §6.4：至少两个已绑定 mention + 恰好一个 primary +
        # 其余 referenced（sequence 顺序由原始 start 偏移保存，本轮
        # 仍不可自动重跑，进入 relation_clarify）
        if len(bound) < 2:
            return None, f"{decision.relation} 需要至少两个已绑定 mention"
        if len(primaries) != 1 or not any(m.role == "referenced" for m in adopted):
            return (
                None,
                f"{decision.relation} 需要恰好一个 primary 且至少一个 referenced",
            )
    elif decision.relation == "ambiguous":
        # v3.3.1 §6.3：允许输入中已有 locked 绑定，禁止本次新增绑定
        if new_select_ids:
            return None, "ambiguous 不得产生新的身份绑定"
    elif decision.relation == "no_company":
        if bound:
            return None, "no_company 不得存在公司绑定"
    else:
        return None, f"未知 relation: {decision.relation}"
    return (
        ValidatedSemanticDecision(
            decision=decision,
            adopted_mentions=tuple(adopted),
            unresolved_parent_ids=tuple(sorted(abstained_parents)),
        ),
        "",
    )


def apply_semantic_decision(
    decision: SemanticDecision,
    mentions: list[EntityMention],
    mode: str,
) -> None:
    """应用校验通过的决策（就地修改 mentions）。

    mode=suggest：只应用 relation 与 role，身份保持 needs_confirmation
    （记录 LLM 选择但不绑定，供真实评测）；
    mode=auto：身份选择直接绑定（llm_selected，仅 allowlist 内合法值，
    已在 validate_semantic_decision 保证）。
    """
    by_id = {m.mention_id: m for m in mentions}
    for r in decision.role_assignments:
        m = by_id.get(r.mention_id)
        if m is not None:
            m.role = r.role
    if mode != "auto":
        # suggest：记录 LLM 身份选择（不绑定），供真实评测（v3.1 §5）
        for d in decision.identity_decisions:
            if d.action == "select" and d.selected_wind_code:
                logger.info(
                    "Selector(suggest): LLM 选择 mention=%s -> %s（不绑定，等待用户确认）",
                    d.mention_id,
                    d.selected_wind_code,
                )
        return
    for d in decision.identity_decisions:
        if d.action != "select" or not d.selected_wind_code:
            continue
        m = by_id.get(d.mention_id)
        if m is None or m.status not in _AMBIGUOUS_STATUSES:
            continue  # locked：不接受
        allowed = {c.company.wind_code for c in m.candidates}
        if d.selected_wind_code not in allowed:
            continue  # 校验已在 validate 完成，双保险
        m.selected_wind_code = d.selected_wind_code
        m.status = "llm_selected"
        m.resolution_source = "llm"


class CompanySemanticSelector:
    """受约束 LLM 语义选择器（同步；经 llm_sync 调用结构化输出）。

    v3.3 批次 C：verifier 失败时带精确错误原因做一次 repair（最多两次
    调用共享总墙钟预算）；suggest 完全只读（由 resolver 侧保证，审计
    属性 last_attempts/last_validation_error 供其记录）。
    """

    def __init__(
        self, mode: str | None = None, total_budget_seconds: float | None = None
    ) -> None:
        self._mode = mode or settings.ENTITY_SEMANTIC_SELECTION_MODE
        # v3.3.1 §9.4：构造参数统一为 query 级总预算（原 timeout 语义
        # 被 5s 默认截断，已删除）——首次裁决与 repair 共享该 deadline
        self._total_budget = (
            total_budget_seconds
            if total_budget_seconds is not None
            else float(settings.ENTITY_SEMANTIC_SELECTION_TOTAL_BUDGET_SECONDS)
        )
        # v3.3 批次 C 审计（resolver 写入 EntityResolutionResult）
        self.last_attempts = 0
        self.last_validation_error = ""
        # v3.3.1 §6.1：最近一次通过的验证快照（auto 路径整体采用
        # adopted_mentions，不重新 _finalize_span）
        self.last_validated: ValidatedSemanticDecision | None = None

    @property
    def mode(self) -> str:
        return self._mode

    def decide(
        self,
        *,
        user_query: str,
        mentions: list[EntityMention],
        alternatives: list[SegmentationAlternative] | None = None,
        current_relation: str = "",
        memory=None,
    ) -> tuple[SelectorStatus, SemanticDecision | None]:
        """语义裁决入口（v3.3 批次 C：repair + 总预算）。

        Returns:
            (selector_status, decision|None)
            disabled（mock/off）| timeout（超时/异常/空）| invalid（两次
            调用均未通过 verifier）| completed（有效决策）
        """
        # mock / off：显式失败关闭（P0-4/v3 §5），0 次调用
        if settings.LLM_BACKEND == "mock" or self._mode == "off":
            self.last_attempts = 0
            self.last_validation_error = ""
            self.last_validated = None
            return "disabled", None

        from app.agents.llm_sync import run_llm_structured

        budget = self._total_budget
        max_attempts = int(settings.ENTITY_SEMANTIC_SELECTION_MAX_SEMANTIC_ATTEMPTS)
        started = time.perf_counter()
        recent_context = _recent_context_text(memory)
        messages = _build_messages(
            user_query, mentions, alternatives, recent_context, current_relation
        )

        decision: SemanticDecision | None = None
        validation_error = ""
        attempts = 0
        self.last_validated = None
        while attempts < max_attempts:
            # v3.3.1 §9.4：单次调用直接使用剩余 deadline（首次 + repair
            # 共享同一总预算；第一次 invalid 很快返回时 repair 用剩余
            # 时间；真正超时耗尽总预算时不再伪造第二次 repair）
            remaining = budget - (time.perf_counter() - started)
            if remaining <= 0:
                logger.warning("Selector: 语义裁决总预算耗尽（%.1fs）", budget)
                self.last_attempts = attempts
                self.last_validation_error = validation_error
                return "timeout", None
            try:
                decision = run_llm_structured(
                    messages, SemanticDecision, timeout=remaining
                )
            except Exception:  # noqa: BLE001 — 任何异常按失败降级
                logger.warning("Selector: LLM 语义裁决异常，确定性降级", exc_info=True)
                self.last_attempts = attempts
                self.last_validation_error = validation_error
                return "failed", None
            attempts += 1
            if decision is None:
                logger.warning(
                    "Selector: LLM 语义裁决超时/空（%.1fs），确定性降级", remaining
                )
                self.last_attempts = attempts
                self.last_validation_error = validation_error
                return "timeout", None
            validated, reason = validate_semantic_decision(
                decision, mentions, alternatives
            )
            if validated is not None:
                self.last_attempts = attempts
                self.last_validation_error = ""
                self.last_validated = validated
                return "completed", decision
            validation_error = reason
            logger.warning(
                "Selector: 语义裁决校验失败（%s），attempt=%d/%d",
                reason,
                attempts,
                max_attempts,
            )
            # v3.3 批次 C repair：把原决策与精确错误原因作为修复消息再问一次
            messages = _repair_messages(messages, decision, reason, current_relation)
        self.last_attempts = attempts
        self.last_validation_error = validation_error
        return "invalid", None
