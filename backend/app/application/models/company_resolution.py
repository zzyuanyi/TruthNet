"""公司实体解析应用 DTO — 方案 v3.1 冻结 §4/§5 落地.

本模块只定义结构化模型与纯函数（不依赖数据库、LLM 或会话状态）：

- `EntityMention` / `CandidateMatch` / `SegmentationAlternative`
- `PendingEntityResolution` / `EntityResolutionOverride`
- `SemanticDecision`（LLM 结构化输出，P1-1 拆分为身份决策与角色分配）
- 枚举：relation / match_kind / mention_status / role / lifecycle / relation_status
- 纯函数：mention_id、query_fingerprint、relation 映射、role 一致性校验、
  匹配来源派生

设计约束（文档 §4）：
- 不在 AgentState 增加平行 mention 字段；state 保留权威
  `entity_resolution_result`，旧字段由节点返回时一次性派生。
"""

from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, Field

from app.agents.state import CompanyRef

# ── 枚举（v3.1 §4 / P1-3 / v3 §5）────────────────────────────

# 八种关系（P0-3）：仅 EXECUTABLE_RELATIONS 中的四种可生成自动重跑 override
Relation = Literal[
    "single",
    "comparison",
    "reference",
    "sequence",
    "switch",
    "continuation",
    "no_company",
    "ambiguous",
]

# 候选匹配来源（P1-2）
MatchKind = Literal[
    "exact_code",
    "exact_name",
    "exact_legal_name",
    "exact_alias",
    "prefix",
    "contains",
    "reverse_contains",
]

# mention 状态（P1-3 七态）：只有 needs_confirmation 可进入 company.confirm
MentionStatus = Literal[
    "auto_selected",
    "llm_selected",
    "needs_confirmation",
    "user_confirmed",
    "needs_refinement",  # 候选被截断 → 需补充名称
    "not_found",  # 零候选且疑似新实体 → 需重述
]

MentionRole = Literal["primary", "comparison_peer", "referenced"]

# pending 生命周期（P0-1）
LifecycleStatus = Literal["collecting", "ready_to_resume", "resuming", "consumed"]

# 关系状态（P0-3）：resolved 且可执行才允许自动重跑
RelationStatus = Literal["resolved", "needs_clarification", "unsupported"]

# 整体语义选择状态（v3 §5 修订：不再用单个 selected/abstained 表达部分成功）
SelectorStatus = Literal[
    "not_needed", "disabled", "completed", "timeout", "failed", "invalid"
]

# 每 mention 解析来源（P1-2：由实际 match_kind 派生，不能仅凭 len==1 判断）
ResolutionSource = Literal[
    "code",
    "exact_name",
    "exact_legal_name",
    "exact_alias",
    "substring",
    "history",
    "llm",
    "user_confirm",
]

# 当前下游可执行关系（P0-3）：reference/sequence/ambiguous 进入 relation_clarify，
# 不生成自动重跑 override、不进入 comparison_guide。
EXECUTABLE_RELATIONS: frozenset[str] = frozenset(
    {"single", "continuation", "switch", "comparison"}
)

# 唯一匹配策略（P1-2 拍板）：默认 safe_reverse_contains
UniqueMatchPolicy = Literal[
    "exact_only", "safe_reverse_contains", "confirm_all_heuristic"
]


# ── 纯函数：稳定 ID 与指纹（P1-4）────────────────────────────


def make_mention_id(start: int, end: int, normalized_text: str) -> str:
    """稳定 mention ID：`m_{start}_{end}_{sha256(normalized_text)[:8]}`。

    不直接包含完整用户文本；start/end 必须对应**原始 query** 偏移
    （非清洗后重算）；同一输入恒生成同一 ID，跨重跑可关联。
    """
    digest = hashlib.sha256((normalized_text or "").encode("utf-8")).hexdigest()[:8]
    return f"m_{start}_{end}_{digest}"


def make_query_fingerprint(question: str) -> str:
    """query fingerprint：原始问题 UTF-8 SHA256（固定算法，不随版本变化）。"""
    return hashlib.sha256((question or "").encode("utf-8")).hexdigest()


def is_executable_relation(relation: str | None) -> bool:
    """relation 是否属于当前下游可执行集合（P0-3）。"""
    return relation in EXECUTABLE_RELATIONS


def resolution_source_from_match_kind(kind: MatchKind) -> ResolutionSource:
    """由实际 match_kind 派生 resolution_source（P1-2）。"""
    mapping: dict[str, ResolutionSource] = {
        "exact_code": "code",
        "exact_name": "exact_name",
        "exact_legal_name": "exact_legal_name",
        "exact_alias": "exact_alias",
        "prefix": "substring",
        "contains": "substring",
        "reverse_contains": "substring",
    }
    return mapping[kind]


# ── 候选与 mention（P1-2 / P1-3 / §4）────────────────────────


class CandidateMatch(BaseModel):
    """候选命中 — 携带匹配来源与命中文本（P1-2）。

    Resolver 据此执行"高置信唯一自动锁定"，不依赖扁平 CompanyRef。
    """

    company: CompanyRef
    match_kind: MatchKind
    matched_text: str = ""
    rank: int = 0


class CandidateLookupResult(BaseModel):
    """单个 mention 的候选查询结果（P1-3：limit+1 截断，truncated 按 mention）。

    组件边界（P0-2）：Repository 只接收一个 mention.text，返回候选，
    不拆分 mention；truncated=True 表示候选集合不完整（须要求用户
    补充名称，不得交给 LLM 从不完整集合选择）。
    """

    matches: list[CandidateMatch] = Field(default_factory=list)
    truncated: bool = False


class EntityMention(BaseModel):
    """原文中的公司 mention（§4）。

    origin=query：start/end 为原始 query 偏移（显式 mention）；
    origin=history（最终续审 §4 A2）：结构化历史主体，start=end=None、
    resolution_source="history"，不伪造 query span、不参与 span verifier。
    mention_id 由 make_mention_id 生成（history 用 h_* 稳定 ID）。
    """

    mention_id: str
    text: str
    origin: Literal["query", "history"] = "query"
    start: int | None = None
    end: int | None = None
    candidates: list[CandidateMatch] = Field(default_factory=list)
    truncated: bool = False
    status: MentionStatus = "needs_confirmation"
    selected_wind_code: str | None = None
    role: MentionRole | None = None
    resolution_source: ResolutionSource | None = None

    @property
    def is_confirmable(self) -> bool:
        """只有 needs_confirmation 可以进入 company.confirm（P1-3）。"""
        return self.status == "needs_confirmation"

    @property
    def is_locked(self) -> bool:
        """唯一高置信命中已锁定（身份不可被 LLM/确认改写）。"""
        return self.status in ("auto_selected", "llm_selected", "user_confirmed")


class SegmentationAlternative(BaseModel):
    """复合片段的一种合法分段方案（P0-4 + v3.3 批次 C 按父分组）。

    parent_mention_id 标识方案归属的父 span（一个 query 可存在多个
    歧义父 span，单个全局 alternative_id 无法表达）；alternative_id
    由 parent_id + 子 mention IDs 稳定生成；mentions 为子 mention
    （基于父 span 绝对偏移生成 ID）。
    """

    parent_mention_id: str = ""
    alternative_id: str
    mentions: list[EntityMention] = Field(default_factory=list)
    reason: str = ""


class EntityResolutionIssue(BaseModel):
    """实体解析流程 issue（v3.3.1 §8.1）——审计与前端澄清的只读信息。

    三种已知 issue：候选查询预算耗尽、顶层实体数超限、分段歧义
    （均不影响已锁定身份，仅记录/提示）。
    """

    code: Literal[
        "proposal_budget_exceeded",
        "too_many_entity_mentions",
        "segmentation_ambiguous",
        # 最终续审 §4 A4：终态关系结构非法（如单主体 comparison）
        "invalid_relation",
    ]
    mention_ids: list[str] = Field(default_factory=list)
    message: str = ""


# ── 会话 pending 状态（P0-1/P0-2/P0-3）────────────────────────


class PendingEntityResolution(BaseModel):
    """会话级待确认实体解析（§4 + 生命周期状态）。

    生命周期（P0-1）：
      collecting → ready_to_resume → resuming → consumed
    确认完成只把状态改为 ready_to_resume，不直接清空；
    由 claim_pending_resume 原子领取启动 T+1。
    """

    origin_turn_id: str
    revision: int = 0
    lifecycle_status: LifecycleStatus = "collecting"
    resolution_version: int = 1
    question: str = ""
    query_fingerprint: str = ""
    relation: Relation | None = None
    relation_status: RelationStatus = "needs_clarification"
    segmentation_alternatives: list[SegmentationAlternative] = Field(
        default_factory=list
    )
    selected_alternative_id: str | None = None
    mentions: dict[str, EntityMention] = Field(default_factory=dict)
    resumed_turn_id: str | None = None

    @property
    def remaining_mention_ids(self) -> list[str]:
        """仅 needs_confirmation 的 mention（P0-1：唯一候选已锁定不计入）。"""
        return [mid for mid, m in self.mentions.items() if m.is_confirmable]

    @property
    def all_identities_selected(self) -> bool:
        """所有必需 mention 身份已选择（auto_selected/llm_selected/user_confirmed）。"""
        return not any(m.status == "needs_confirmation" for m in self.mentions.values())

    @property
    def can_resume(self) -> bool:
        """可恢复重跑（P0-3）：身份全确认 AND relation_status==resolved
        AND relation 属于可执行集合。"""
        return (
            self.all_identities_selected
            and self.relation_status == "resolved"
            and is_executable_relation(self.relation)
        )


class OverrideDecision(BaseModel):
    """override 中单个 mention 的完整决策（P0-3：保留 role，防 reference/sequence 被错当比较）。"""

    mention_id: str
    text: str = ""
    start: int = 0
    end: int = 0
    wind_code: str = ""
    role: MentionRole | None = None


class EntityResolutionOverride(BaseModel):
    """重跑注入的结构化覆盖（§4 / P0-3）。

    resolve_entity 重跑时校验 query_fingerprint、span、候选身份后，
    恢复完整 relation/role 决策，不把任意 2+ mentions 无条件派生为比较。
    """

    resolution_version: int = 1
    query_fingerprint: str = ""
    relation: Relation = "ambiguous"
    selected_alternative_id: str | None = None
    decisions: list[OverrideDecision] = Field(default_factory=list)


# ── LLM 语义决策（P1-1：身份与角色拆开）───────────────────────


class IdentityDecision(BaseModel):
    """身份决策 — 只针对歧义 mention（locked mention 不接受）。"""

    mention_id: str
    action: Literal["select", "abstain"] = "abstain"
    selected_wind_code: str | None = None
    evidence_span: str = ""  # 审计用：原问题原文片段（不作选择有效性必要条件）


class RoleAssignment(BaseModel):
    """角色分配 — 针对全部最终采用的 mention（含 locked）。"""

    mention_id: str
    role: MentionRole


class SegmentationDecision(BaseModel):
    """v3.3 批次 C：按父 mention 分组的单条分段裁决。

    每个有 alternatives 的父 mention 必须恰好一条 decision；
    select 时 alternative_id 必须属于该父 mention 的方案集合。
    """

    parent_mention_id: str
    action: Literal["select", "abstain"] = "abstain"
    alternative_id: str | None = None


class MentionnessVerdict(BaseModel):
    """v3.3 批次 D：零候选 span 的三态 NIL 判定。

    不含 wind_code/补全文本字段——schema 即约束（LLM 无法输出代码）。
    """

    span_id: str
    verdict: Literal["company_mention", "non_company_context", "abstain"]
    evidence: str = ""


class MentionnessDecision(BaseModel):
    """v3.3.1 §9.3：批量 NIL 判定——一条 query 最多一次 mentionness
    LLM 调用；程序校验要求每个输入 span_id 恰好一个 verdict（无
    未知/重复/遗漏）。"""

    verdicts: list[MentionnessVerdict] = Field(default_factory=list)


# ── v3.3.2-R1 §6：低置信 query 主体语义解释 schema ─────────────


class MentionExtractionResult(BaseModel):
    """最终续审 §5 B1：Extractor 结构化输出——span 与掩码过程元数据。

    Resolver 消费元数据做确定性主体路由，不得再扫描第二套回指词表。
    """

    mentions: list["EntityMention"] = Field(default_factory=list)
    had_subject_terminator: bool = False
    explicit_anaphora: bool = False
    back_reference: bool = False
    explicit_switch: bool = False
    residual_text: str = ""


class UnresolvedMentionInput(BaseModel):
    """Interpreter 输入：未检索到候选的原文片段（中间验收 P1-1）。

    Resolver 构造时填入完整原文信息，LLM 才能可靠完成 disposition。
    """

    mention_id: str
    text: str
    start: int
    end: int


class ProposedCompanySpan(BaseModel):
    """Interpreter 提出的公司原文 span（必须等于 query 切片，不得编造）。"""

    text: str
    start: int
    end: int


class InputSpanDisposition(BaseModel):
    """对输入 unresolved span 的三分类（NIL 判定的一部分）。"""

    mention_id: str
    kind: Literal["company", "context", "uncertain"]
    proposed_company_spans: list[ProposedCompanySpan] = Field(default_factory=list)


class QuerySubjectInterpretation(BaseModel):
    """低置信 query 的主体语义解释（§6.2 schema）。

    无 wind_code 字段——LLM 结构上不可能输出代码；模型不确定必须输出
    uncertain，不得用自报 confidence 授权。
    """

    subject_reference: Literal["new", "previous", "none", "uncertain"]
    input_span_dispositions: list[InputSpanDisposition] = Field(default_factory=list)
    additional_company_spans: list[ProposedCompanySpan] = Field(default_factory=list)
    company_relation: Literal[
        "single", "comparison", "reference", "sequence", "none", "uncertain"
    ] = "uncertain"
    # 最终续审 §4 A1：新公司 + 当前主体构成 comparison（"那茅台呢，
    # 对比一下"——当前主体作为历史 peer，不伪造 query span）
    include_current_subject: bool = False
    plan_hint: Literal[
        "indicator",
        "diagnostic",
        "summary",
        "comparison",
        "research",
        "analysis",
        "chitchat",
        "unsupported",
        "other",
    ] = "other"


class SemanticDecision(BaseModel):
    """LLM 结构化输出（P1-1 拆分 + v3.3 批次 C 分组分段）。

    默认 abstain：模型不能默认选择第一家；locked mention 的身份
    决策被服务端忽略，但其 role 必须被校验。
    """

    relation: Relation = "ambiguous"
    # v3.3 批次 C：单个全局 alternative_id 无法表达多个歧义父 span，
    # 改为按父分组的裁决列表
    segmentation_decisions: list[SegmentationDecision] = Field(default_factory=list)
    identity_decisions: list[IdentityDecision] = Field(default_factory=list)
    role_assignments: list[RoleAssignment] = Field(default_factory=list)
    abstain_reason: str = ""


# ── 权威结果（§4：AgentState 保留一个 entity_resolution_result）─


class EntityResolutionResult(BaseModel):
    """实体解析权威结果 — AgentState 只保留此字段，旧字段派生。

    v3 §2 字段 + v3.1 修订（整体 selector_status + 每 mention 状态/来源）。
    """

    intent: Relation = "ambiguous"
    mentions: list[EntityMention] = Field(default_factory=list)
    selected_companies: list[CompanyRef] = Field(default_factory=list)
    unresolved_mentions: list[str] = Field(default_factory=list)
    needs_confirmation: bool = False
    reason_code: str = ""
    selector_status: SelectorStatus = "not_needed"
    # v3.3 批次 C（§5.4）：suggest 模式内部审计字段——只记录建议，
    # 不改变权威结果（离线影子评测消费，不必暴露旧前端）
    semantic_suggestion: SemanticDecision | None = None
    semantic_attempts: int = 0
    semantic_validation_error: str = ""
    # v3.3 批次 D：零候选 span 的 NIL 三态审计（suggest/auto 模式记录，
    # 第一阶段不改变生产路由）
    mentionness_verdicts: list[MentionnessVerdict] = Field(default_factory=list)
    # v3.3.1 §8.1：grouped alternatives 与 issue 进入权威结果（审计/
    # 前端澄清消费；PendingEntityResolution 的同名字段是 pending 侧
    # 兼容结构，两者数据源均为 resolver 输出）
    segmentation_alternatives: list[SegmentationAlternative] = Field(
        default_factory=list
    )
    resolution_issues: list[EntityResolutionIssue] = Field(default_factory=list)
    # 权威选择映射 parent_mention_id -> alternative_id（多 parent 完整
    # 记录；Pending 的单值 selected_alternative_id 由它派生兼容）
    selected_alternative_ids: dict[str, str] = Field(default_factory=dict)
    # v3.3.2-R1 §8：低置信主体语义解释审计字段（shadow 记录/Plan 复用；
    # fallback 应用的解释同样保留，供真机观测与评测）
    subject_interpretation: QuerySubjectInterpretation | None = None
    subject_interpreter_status: Literal[
        "not_needed",
        "disabled",
        "shadow",
        "completed",
        "timeout",
        "invalid",
        "failed",
    ] = "not_needed"


# ── 纯函数：relation/role 一致性校验（P1-1）───────────────────


def validate_relation_roles(relation: str, mentions: list[EntityMention]) -> bool:
    """relation/role 一致性校验（P1-1）。

    - single/continuation/switch：最终只有一个 primary；
    - comparison：至少两个不同 wind_code（已绑定），或（角色分配含
      primary + comparison_peer 且 mention 数 ≥2——身份待确认时
      关系可先行判定，绑定后重跑再验证）；
    - reference：一个 primary，至少一个 referenced（基于角色分配，
      未绑定 mention 的身份确认后重跑再验证）；
    - no_company：不得选择公司；
    - ambiguous：不得生成可执行 override（恒 False）。
    """
    selected = [m for m in mentions if m.selected_wind_code]
    roles = [m.role for m in mentions if m.role]
    primaries = [r for r in roles if r == "primary"]
    if relation in ("single", "continuation", "switch"):
        return len(primaries) == 1
    if relation == "comparison":
        codes = {m.selected_wind_code for m in selected}
        if len(codes) >= 2:
            return True
        return len(mentions) >= 2 and len(primaries) == 1 and "comparison_peer" in roles
    if relation == "reference":
        return len(primaries) == 1 and "referenced" in roles
    if relation == "no_company":
        return not selected
    # ambiguous 及其余关系不得生成可执行决策
    return False


def validate_finalized_relation_roles(
    relation: str, mentions: list[EntityMention]
) -> bool:
    """override 严格终态校验（v3.2.1 批次 4）——只验证用户确认后的
    最终可执行结果，不允许"身份待确认"的部分状态：

    - single/continuation/switch：恰好一个最终公司 mention、恰好一个
      已选择代码、角色为 primary；
    - comparison：至少两个 mention、全部已选择、至少两个不同 wind_code、
      恰好一个 primary、其余全部 comparison_peer；
    - 其余 relation（reference/sequence/no_company/ambiguous）一律 False。

    比 validate_relation_roles() 更严格：本函数用于 override 重跑前的
    终态闸门，两者不可互相替代。
    """
    if not mentions:
        return False
    if relation in ("single", "continuation", "switch"):
        if len(mentions) != 1:
            return False
        m = mentions[0]
        return bool(m.selected_wind_code) and m.role == "primary"
    if relation == "comparison":
        if len(mentions) < 2:
            return False
        # "已选择" = 有绑定身份（auto_selected/llm_selected/user_confirmed
        # 均算），允许锁定方与确认方混合（如茅台锁定 + 平安确认）
        if any(not m.selected_wind_code for m in mentions):
            return False
        codes = [m.selected_wind_code for m in mentions]
        if len(set(codes)) < 2:
            return False
        primaries = [m for m in mentions if m.role == "primary"]
        if len(primaries) != 1:
            return False
        return all(
            m.role == "comparison_peer" for m in mentions if m is not primaries[0]
        )
    return False
