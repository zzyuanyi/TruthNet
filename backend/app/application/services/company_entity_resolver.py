"""CompanyEntityResolver — 实体解析编排（v3.1 冻结方案 P0-2/P1-2/P0-3/P0-4）.

职责（组件边界冻结）：
- 编排 Extractor（span）→ CandidateLookup（候选）→ 分段 alternatives →
  唯一高置信锁定 → 历史延续与防串 → 关系判定；
- 不持有 SQL/Engine（lookup 经 port 注入，P1-6）；
- 需要语义裁决的点（候选歧义/关系歧义/分段歧义）输出待确认状态，
  由 CompanySemanticSelector（步骤 7）接入。

锁定策略（P1-2 拍板 ENTITY_UNIQUE_MATCH_POLICY=safe_reverse_contains）：
六项安全条件全部成立才自动锁定；变体命中（matched_text != mention.text）
不锁定（普通 prefix/contains、截短命中一律要求确认）。
"""

from __future__ import annotations

import logging
import re
from typing import Literal

from app.agents.state import CompanyRef, MemoryContext, RequestContext
from app.application.models.company_resolution import (
    CandidateMatch,
    EntityMention,
    EntityResolutionIssue,
    EntityResolutionResult,
    MentionnessVerdict,
    SegmentationAlternative,
    UnresolvedMentionInput,
    is_executable_relation,
    make_mention_id,
    resolution_source_from_match_kind,
    validate_finalized_relation_roles,
)
from app.application.ports.company_candidate_lookup import CompanyCandidateLookup
from app.application.services.canonical_business_registry import (
    explainable_as_canonical_context,
)
from app.application.services.company_mention_extractor import (
    extract_company_mention_result,
)
from app.application.services.company_mention_proposal_service import (
    _MAX_LOOKUPS_PER_QUERY,
    BudgetedLookupOutcome,
    ProposalLookupBudget,
)
from app.application.services.company_semantic_selector import (
    CompanySemanticSelector,
)
from app.application.services.query_subject_interpreter import (
    QuerySubjectInterpreter,
    _all_company_spans,
)
from app.core.config import settings
from app.domain.comparison.scope_registry import COMPARISON_FULL_SCOPE_WORDS

logger = logging.getLogger(__name__)

# 语法后缀变体（v8 _GRAMMAR_SUFFIX_CHARS 平移）
_GRAMMAR_SUFFIX_CHARS = frozenset("的是呢吗了")

# v3.2.1 批次 2：业务上下文词（封闭集合）——仅当已存在有效公司 mention 时，
# 零候选 span 精确等于其中之一才被忽略（不进 mentions/unresolved/relation）
_CONTEXT_WORDS = frozenset({"年报", "中报", "季报", "半年报", "一季报", "三季报"})

# v3.3.4 收口复核清单 §6：比较语法范围词（comparison operator）。
# 与 _CONTEXT_WORDS 分离：只在该 span 经 Repository 查询无任何候选
# （not_found）、且与比较 cue（对比/比较）紧邻（前或后）时忽略——
# 不进全局清洗词表、不做全局 replace；合法公司名（如「全面科技」命中
# 候选）不受影响。
# 收口复核审查 P2a：词表统一取自 domain/comparison/scope_registry
# （与计划层 requested_scope=full 判定同一来源，含 多维/整体）。
_COMPARISON_OPERATOR_WORDS = frozenset(COMPARISON_FULL_SCOPE_WORDS)
_COMPARISON_OPERATOR_CUES = ("对比", "比较")

# v3.2.1 批次 2：明确无公司行业研究主题模板（窄规则，无法确定按 not_found）
_RESEARCH_STRONG_CUES = ("研报",)
_RESEARCH_TOPIC_CUES = ("行业", "板块")
_RESEARCH_VIEW_CUES = ("观点", "趋势", "前景", "景气")
# 公司形态后缀：出现即视为疑似公司语境，不得放行 research
_COMPANY_FORM_SUFFIXES = (
    "公司",
    "股份",
    "集团",
    "银行",
    "保险",
    "证券",
    "科技",
    "药业",
    "实业",
    "控股",
)
# 公司事实问法模板：出现即保持公司解析
_COMPANY_FACT_TEMPLATES = ("属于什么行业", "所属行业", "是什么行业")

# 内嵌 Wind Code（v8 正则平移）：6 位数字 ± 后缀，lookaround 防前后粘连数字
_WIND_CODE_RE = re.compile(
    r"(?<!\d)(\d{6}(?:\.(?:S[HZ]|BJ|XSHG|XSHE))?)(?!\d)", re.IGNORECASE
)

# 复合切分连接词与深度上限（v8 平移 + P0-3 reference 场景扩展：
# "分析康美提到茅台的公告" 需按 提到/提及 切分两家）
_COMPOUND_CONNECTORS = ("和", "与", "跟", "及", "提到", "提及", "谈到", "谈及")
_MAX_COMPOUND_ENTITIES = 4

# 比较信号（v8 P1-1 分级平移）
# v3.3.3 收口批次 C：补「A 比 B 高/低多少、早/晚几年」类比较句式
# （通用比较语义，非公司名专用词）
_STRONG_COMPARISON_CUES = (
    "对比",
    "比较",
    "差距",
    "谁更",
    "低多少",
    "高多少",
    "高出",
    "更低",
    "更高",
    "早几年",
    "晚几年",
    "谁高",
    "谁低",
)
_WEAK_COORDINATION_CUES = ("和", "与", "还是")
_SINGLE_COMPANY_COMPARISON_EXCLUSIONS = (
    "行业",
    "同比",
    "去年",
    "今年",
    "上年",
    "指标",
    "增速",
    "变化",
    "环比",
)
# reference 信号（P0-3：mention 到关系 → 澄清）
_REFERENCE_CUES = ("提到", "提及", "谈到", "谈及")


def _history_mention_id(wind_code: str) -> str:
    """最终续审 §4 A2：历史 mention 稳定 ID（由 Wind Code 哈希，
    不伪装原文 span 坐标）。"""
    import hashlib

    return "h_" + hashlib.sha256(wind_code.encode("utf-8")).hexdigest()[:12]


def _make_history_mention(company: CompanyRef, role: str = "primary") -> EntityMention:
    """最终续审 §4 A2：结构化历史主体 mention——origin=history、
    start=end=None、resolution_source="history"，不参与 query span
    verifier、不伪造原文坐标。

    candidates 携带公司引用，使 selected_companies 收集循环无需为
    history mention 开分支。
    """
    return EntityMention(
        mention_id=_history_mention_id(company.wind_code),
        text=company.sec_name,
        origin="history",
        start=None,
        end=None,
        status="auto_selected",
        selected_wind_code=company.wind_code,
        role=role,
        resolution_source="history",
        candidates=[CandidateMatch(company=company, match_kind="exact_name")],
    )


def _mention_offset_key(m: EntityMention) -> tuple[int, int]:
    """排序键：history mention（start=None）排在所有 query mention 之后，
    不依赖 None 与 int 比较。"""
    if m.origin == "history" or m.start is None:
        return (10**9, 0)
    return (m.start, m.end)


def _merge_exact_spots(
    query: str, mentions: list[EntityMention]
) -> list[EntityMention]:
    """v3.3.3 收口批次 C（方案 §3.5）：数据库精确名称 spotting 并行通道。

    补召回 extractor 漏提的完整 sec_name span（官方三题反例的第二家
    公司）；span 只进入主流程由 Repository 二次链接（身份单一来源），
    此处不绑定公司；与既有 span 重叠时精确名称优先；与既有 span 完全
    一致时去重。不向终止词表添加官方题目专用词。
    """
    from app.application.services.exact_company_spotter import (
        spot_exact_company_spans,
    )

    try:
        spans = spot_exact_company_spans(query)
    except Exception:  # noqa: BLE001 — spotting 失败不阻断实体主流程
        return mentions
    if not spans:
        return mentions

    kept: list[EntityMention] = []
    for m in mentions:
        if m.start is None or m.end is None:
            kept.append(m)
            continue
        # 与某个精确 span 重叠但非同一 span → 精确名称优先（丢弃粗 span）
        if any(not (m.end <= s.start or s.end <= m.start) for s in spans) and not any(
            m.start == s.start and m.end == s.end and (m.text or "") == s.text
            for s in spans
        ):
            continue
        kept.append(m)

    existing_keys = {(m.start, m.end, (m.text or "").strip()) for m in kept}
    for span in spans:
        key = (span.start, span.end, span.text)
        if key in existing_keys:
            continue
        kept.append(
            EntityMention(
                mention_id=make_mention_id(span.start, span.end, span.text),
                text=span.text,
                start=span.start,
                end=span.end,
            )
        )
    kept.sort(key=_mention_offset_key)
    return kept


def deterministic_subject_reference(
    *,
    has_current_subject: bool,
    explicit_anaphora: bool,
    back_reference: bool,
    had_subject_terminator: bool,
    has_new_entity_evidence: bool,
) -> Literal["previous", "not_decided"]:
    """最终续审 §5 B4：SubjectDecision 优先级第 3 层——确定性延续。

    输入全部来自 Extractor 的结构化元数据（MentionExtractionResult），
    Resolver 不再扫描第二套回指词表。优先级：
      显式新公司（调用方）> 防串阻断（has_new_entity_evidence）
      > 明确回指/回指框架/业务谓词追问（本函数）
      > not_decided（Interpreter 或 fail-closed）。

    无 current subject 或存在疑似新实体证据时不延续（不伪造、不吞掉）。
    """
    if not has_current_subject:
        return "not_decided"
    if has_new_entity_evidence:
        return "not_decided"
    if explicit_anaphora or back_reference or had_subject_terminator:
        return "previous"
    return "not_decided"


def validate_relation_final_state(
    relation: str, mentions: list[EntityMention]
) -> str | None:
    """最终续审 §4 A4：可执行关系终态结构校验（统一入口）。

    - single/continuation/switch：恰好一个已绑定主体；零绑定但存在
      待确认候选（needs_confirmation）属合法非终态（确认流程），
      不在此拦截；
    - comparison：至少两个已绑定、至少两个不同 wind_code，且不得残留
      not_found/needs_refinement mention（v3.3.4 收口复核审查 P1：NIL
      主体不得被静默丢弃后执行错误范围的比较——降级澄清并保留
      unresolved）；needs_confirmation 属候选确认流程，不在此拦截；
    - 其余 relation 不在此校验（reference/sequence 为不可执行澄清态）。

    返回 None=通过；否则返回稳定 reason_code。
    """
    bound = [m for m in mentions if m.selected_wind_code]
    if relation in ("single", "continuation", "switch"):
        if len(bound) >= 2:
            return "invalid_relation_participants"
        if len(bound) == 0 and any(m.status == "needs_confirmation" for m in mentions):
            return None  # 候选确认流程，非终态
        if len(bound) == 0:
            return "invalid_relation_participants"
    elif relation == "comparison":
        codes = {m.selected_wind_code for m in bound}
        if len(bound) < 2 or len(codes) < 2:
            return "comparison_missing_peer"
        # 收口复核审查 P1：比较中残留 NIL/refinement → 不可执行比较
        # （不得静默截断为两家）；needs_confirmation 不在此拦截
        if any(m.status in ("not_found", "needs_refinement") for m in mentions):
            return "comparison_nil_participant"
    return None


def apply_relation_proposal(
    relation: str,
    relation_status: str,
    proposal: str | None,
    mentions: list[EntityMention],
) -> tuple[str, str]:
    """中间验收 P1-2：Interpreter relation proposal 的消费裁决。

    - proposal 非 comparison/reference/sequence → 原样返回；
    - 全部 mention 唯一绑定（无 needs_confirmation/needs_refinement）
      且 ≥2 个不同 wind_code → 应用（comparison=resolved，
      reference/sequence=needs_clarification）；
    - 任一 span NIL/歧义 → 不应用，保留旧 relation/status。
    """
    if proposal not in ("comparison", "reference", "sequence"):
        return relation, relation_status
    all_bound = (
        len(mentions) >= 2
        and all(m.selected_wind_code for m in mentions)
        and all(
            m.status not in ("needs_confirmation", "needs_refinement") for m in mentions
        )
        and len({m.selected_wind_code for m in mentions}) >= 2
    )
    if not all_bound:
        return relation, relation_status
    return proposal, "resolved" if proposal == "comparison" else "needs_clarification"


def _suffix_variants(frag: str) -> list[str]:
    """语法后缀变体：只递归删除尾部 的呢吗了是（v8 平移）。

    变体命中不满足锁定条件 4（matched_text != mention.text），
    只用于"有唯一候选但需确认"的候选展示。
    """
    variants = [frag]
    current = frag
    while len(current) >= 2 and current[-1] in _GRAMMAR_SUFFIX_CHARS:
        current = current[:-1]
        variants.append(current)
    return variants


def _detect_comparison(query: str, resolved_names: list[str]) -> bool:
    """比较意图检测（v8 P1-1 分级平移，resolved_names 替代扁平候选）。"""
    q = (query or "").lower()
    if re.search(r"\bvs\.?\b", q, re.IGNORECASE):
        return True
    rest = q
    for name in resolved_names:
        if name and name in rest:
            rest = rest.replace(name, "", 1)
    hit_count = len(resolved_names)
    has_strong = any(cue in q for cue in _STRONG_COMPARISON_CUES)
    has_weak = any(cue in q for cue in _WEAK_COORDINATION_CUES)
    if has_strong:
        if hit_count == 0:
            return not any(
                excl in rest for excl in _SINGLE_COMPANY_COMPARISON_EXCLUSIONS
            )
        if hit_count == 1:
            for cue in _WEAK_COORDINATION_CUES:
                idx = rest.find(cue)
                if idx >= 0:
                    after = rest[idx + len(cue) :].strip(" 的")
                    if not after:
                        continue
                    if any(
                        after.startswith(excl)
                        for excl in _SINGLE_COMPANY_COMPARISON_EXCLUSIONS
                    ):
                        return False
                    return True
            return not any(
                excl in rest for excl in _SINGLE_COMPANY_COMPARISON_EXCLUSIONS
            )
        return True
    if has_weak:
        return hit_count >= 2
    return False


def _detect_reference(query: str) -> bool:
    """reference 信号（P0-3）："分析康美提到茅台的公告"类主次不明。"""
    return any(cue in (query or "") for cue in _REFERENCE_CUES)


def _is_definite_research_topic_query(query: str) -> bool:
    """v3.2.1 批次 2：整句是否"明确无公司行业研究主题"（窄规则）。

    所有 span 均无公司候选时才调用。必须同时满足：
      - 无内嵌 Wind Code；
      - 无公司形态后缀（公司/股份/集团/银行/保险/证券/科技/药业/
        实业/控股——"火星科技行业风险/研报"仍视为疑似公司）；
      - 无公司事实问法模板（属于什么行业/所属行业/是什么行业）；
      - 强研究信号："研报"，或"行业/板块 + 观点/趋势/前景/景气"。

    无法确定时返回 False（保持 not_found 阻断），不猜测。
    """
    q = (query or "").strip()
    if not q:
        return False
    if _WIND_CODE_RE.search(q):
        return False
    if any(s in q for s in _COMPANY_FORM_SUFFIXES):
        return False
    if any(t in q for t in _COMPANY_FACT_TEMPLATES):
        return False
    if any(c in q for c in _RESEARCH_STRONG_CUES):
        return True
    return any(c in q for c in _RESEARCH_TOPIC_CUES) and any(
        c in q for c in _RESEARCH_VIEW_CUES
    )


# v3.2.1 批次 3：受控所有格边界的封闭业务前缀（startswith 命中，非子串）
_BUSINESS_PHRASE_PREFIXES = frozenset(
    {
        "存贷",
        "营收",
        "利润",
        "风险",
        "财务",
        "现金流",
        "应收账款",
        "应付账款",
        "资产负债",
        "毛利",
        "净利",
        "负债",
        "资产",
        "成本",
        "费用",
        "分红",
        "回购",
        "业绩",
        "经营",
        "现金",
        "收入",
        "应收",
        "应付",
        "存货",
        "增长",
        "增速",
        "变化",
        "趋势",
    }
)

# 候选驱动的尾部谓语边界。只有完整 span 仅产生低置信 contains 候选、
# 且谓语左侧能独立召回公司时才剥离一次。不能放回 Extractor 全局终止符，
# 否则会破坏“有友食品”等公司名。
_TRAILING_COMPANY_PREDICATES = ("存在", "拥有", "持有", "有")


def _possessive_splits(frag: str) -> list[tuple[str, str]]:
    """从右向左枚举"的"切分点（v3.2.1 批次 3）。

    从右向左避免优先取到名称内部"的"（如"美的"）造成左侧 <2 字；
    每个切分点返回 (left, right)，由调用方逐个验证。
    """
    splits: list[tuple[str, str]] = []
    idx = frag.rfind("的")
    while idx >= 0:
        splits.append((frag[:idx], frag[idx + 1 :]))
        idx = frag.rfind("的", 0, idx)
    return splits


def _is_business_phrase(right: str) -> bool:
    """右侧是否以封闭业务词开头（startswith，不用任意子串命中）。"""
    return any(right.startswith(w) for w in _BUSINESS_PHRASE_PREFIXES)


class CompanyEntityResolver:
    """实体解析编排器（同步；lookup 经 port 注入）。"""

    def __init__(
        self,
        lookup: CompanyCandidateLookup,
        policy: str | None = None,
        selector: CompanySemanticSelector | None = None,
        mentionness=None,
        lookup_limit: int | None = None,
        interpreter: QuerySubjectInterpreter | None = None,
    ) -> None:
        self._lookup = lookup
        self._policy = policy or settings.ENTITY_UNIQUE_MATCH_POLICY
        self._selector = selector
        # v3.3 批次 D：零候选 span 的 NIL 三态判定器（off 零调用；
        # 结果仅记录审计字段，第一阶段不改变权威行为）
        self._mentionness = mentionness
        # v3.3.2-R1 §7：低置信 query 主体语义解析器（off 零调用；
        # shadow 记录不应用；fallback 低置信路径应用）
        self._interpreter = interpreter
        # v3.3 批次 B：每 query 的有界候选召回（12 次去重查询上限 +
        # memoize）；每次 resolve() 入口重建。v3.3.1 §5.2：limit 可
        # 显式注入（测试小预算/单一来源），默认 _MAX_LOOKUPS_PER_QUERY
        self._lookup_limit = lookup_limit
        self._budget: ProposalLookupBudget | None = None
        # v3.3.1 §8.1：本 query 的实体解析 issues（审计/前端澄清）
        self._issues: list[EntityResolutionIssue] = []
        # v3.3.2-R1 中间验收 P1-2：Interpreter 的 relation proposal
        # （仅在 spans 二次链接全部绑定后消费；每次 resolve 重置）
        self._relation_proposal: str | None = None

    def _add_issue(self, code: str, mention_ids: list[str], message: str = "") -> None:
        """追加实体解析 issue（code 为 EntityResolutionIssue.Literal 之一）。"""
        self._issues.append(
            EntityResolutionIssue(code=code, mention_ids=mention_ids, message=message)
        )

    def _budget_exhausted_fallback(
        self, mention: EntityMention
    ) -> tuple[list[EntityMention], list]:
        """v3.3.1 §5.1：查询预算耗尽的统一降级（needs_refinement + issue）。

        禁止继续分段、所有格、连接词或任何 .matches 访问。
        """
        mention.status = "needs_refinement"
        mention.truncated = True
        mention.resolution_source = None
        self._add_issue(
            "proposal_budget_exceeded",
            [mention.mention_id],
            f"候选查询预算耗尽：{mention.text}",
        )
        logger.warning("Resolver: proposal 查询预算耗尽，span=%s", mention.text)
        return [mention], []

    def _budgeted_lookup(self, text: str) -> BudgetedLookupOutcome:
        """经查询预算的候选召回（v3.3.1 §5.1：预算耗尽返回显式
        Outcome，调用方降级 needs_refinement，不得访问 result）。"""
        if self._budget is None:
            self._budget = ProposalLookupBudget(self._lookup)
        return self._budget.lookup(text)

    # ── 锁定判定（P1-2 六项安全条件）─────────────────────────

    def _should_auto_lock(self, mention: EntityMention, lookup_result) -> bool:
        """唯一命中自动锁定。

        exact_only / confirm_all_heuristic：仅精确类；
        safe_reverse_contains：唯一 + 未截断 + matched_text == mention.text
          （排除变体/截短命中，条件 2/4）+ 无分段歧义（条件 6 前半，
          由调用方在分段歧义时跳过本路径）+ 无历史冲突（显式 mention
          存在时不走历史路径，流程层保证）。
        v3.2.1 批次 7：单字不锁定（P1-2 条件 1 长度 ≥2）；普通 contains
        一律不自动锁定（对齐冻结方案 P1-2）。
        """
        if len(mention.text) < 2:
            return False  # 条件 1：mention 长度不少于 2 个汉字
        if len(lookup_result.matches) != 1 or lookup_result.truncated:
            return False  # 条件 3
        match = lookup_result.matches[0]
        exact_kinds = {"exact_code", "exact_name", "exact_legal_name", "exact_alias"}
        if match.match_kind in exact_kinds:
            return True
        if self._policy in ("exact_only", "confirm_all_heuristic"):
            return False
        # 普通 contains 一律不自动锁定（v3.2.1 批次 7，冻结方案 P1-2：
        # mention 包含完整 sec_name 的方向命中唯一也进入确认）
        if match.match_kind == "contains":
            return False
        # prefix / reverse_contains：条件 4（sec_name 完整包含原 mention，
        # matched_text == mention.text，排除变体/截短命中）
        return match.matched_text == mention.text

    # ── 候选查询（含语法后缀变体路径）─────────────────────────

    def _lookup_mention_with_variants(
        self, mention: EntityMention
    ) -> BudgetedLookupOutcome:
        """查询候选；无直接命中时尝试语法后缀变体（变体命中不锁定）。

        v3.3 批次 B：全部经查询预算（memoize + 上限）。
        v3.3.1 §5.1：预算耗尽立即返回 exhausted Outcome（不再继续
        尝试下一个变体——耗尽后再查询只会再次耗尽）。
        """
        outcome = self._budgeted_lookup(mention.text)
        if outcome.budget_exhausted or outcome.result.matches:
            return outcome
        for variant in _suffix_variants(mention.text)[1:]:
            variant_outcome = self._budgeted_lookup(variant)
            if variant_outcome.budget_exhausted:
                return variant_outcome
            if variant_outcome.result.matches:
                return variant_outcome
        return outcome

    # ── 复合分段（P0-4，递归 + 方案去重）──────────────────────

    def _segment_compound(
        self, parent: EntityMention, depth: int
    ) -> list[SegmentationAlternative]:
        """对无候选的 span 尝试内部 和/与/跟/及 切分（递归）。

        子 mention 基于父 span 绝对偏移生成 ID（P1-4）；两侧子片段均
        能独立命中候选（子片段无候选时递归切分）才合法；按 mention_id
        集合去重后返回合法方案列表（>1 → 分段歧义）。
        """
        if depth >= _MAX_COMPOUND_ENTITIES:
            return []
        frag = parent.text
        alternatives: list[SegmentationAlternative] = []
        seen_keys: set[tuple] = set()
        # 连接词位置（多字词整词定位）
        connector_hits: list[tuple[int, str]] = []
        for connector in _COMPOUND_CONNECTORS:
            idx = frag.find(connector)
            while idx >= 0:
                connector_hits.append((idx, connector))
                idx = frag.find(connector, idx + 1)
        for pos, connector in connector_hits:
            left, right = frag[:pos], frag[pos + len(connector) :]
            if len(left) < 2 or len(right) < 2:
                continue
            left_m = EntityMention(
                mention_id=make_mention_id(parent.start, parent.start + pos, left),
                text=left,
                start=parent.start,
                end=parent.start + pos,
            )
            right_m = EntityMention(
                mention_id=make_mention_id(
                    parent.start + pos + len(connector), parent.end, right
                ),
                text=right,
                start=parent.start + pos + len(connector),
                end=parent.end,
            )
            left_final, _ = self._finalize_span(left_m, depth + 1)
            if not left_final or any(
                m.status in ("not_found", "needs_refinement") for m in left_final
            ):
                continue
            right_final, _ = self._finalize_span(right_m, depth + 1)
            if not right_final or any(
                m.status in ("not_found", "needs_refinement") for m in right_final
            ):
                continue
            merged = left_final + right_final
            key = tuple(m.mention_id for m in merged)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            alternatives.append(
                SegmentationAlternative(
                    # v3.3 批次 C：方案归属父 span，alternative_id 由
                    # parent_id + 子 mention IDs 稳定生成（跨父 span 不重名）
                    parent_mention_id=parent.mention_id,
                    alternative_id=(f"alt_{parent.mention_id}_{pos}_{connector}"),
                    mentions=merged,
                    reason=f"split@{pos}:{connector}",
                )
            )
        return alternatives

    @staticmethod
    def _dedupe_top_mentions(
        mentions: list[EntityMention],
    ) -> list[EntityMention]:
        """v3.3.1 §5.2：顶层 span 按 (start, end, normalized_text) 去重
        （fail-closed 计数与 prime 去重共用同一口径）。"""
        seen: set[tuple] = set()
        out: list[EntityMention] = []
        for m in mentions:
            key = (m.start, m.end, (m.text or "").strip())
            if key in seen:
                continue
            seen.add(key)
            out.append(m)
        return out

    # ── 业务上下文过滤（v3.2.1 批次 2 + v3.3.4 收口复核清单 §6）──

    @staticmethod
    def _is_comparison_operator_position(query: str, mention: EntityMention) -> bool:
        """span 是否处于比较语法位置：与「对比/比较」cue 紧邻
        （cue 紧跟 span 之后，或紧贴 span 之前）。"""
        start = mention.start or 0
        end = mention.end or 0
        after = query[end : end + 2]
        before = query[max(0, start - 2) : start]
        return after in _COMPARISON_OPERATOR_CUES or before in _COMPARISON_OPERATOR_CUES

    @staticmethod
    def _drop_ignored_context(
        mentions: list[EntityMention],
        query: str = "",
    ) -> list[EntityMention]:
        """零候选 span 若精确等于封闭上下文词，且已存在有效公司 mention，
        则从最终 mentions 移除（ignored context，不进入 unresolved/relation/
        Selector）。无有效公司时不忽略——全部 not_found 交由
        research_context 模板或阻断路径处理。

        v3.3.4 收口复核清单 §6：比较语法范围词（全面/综合/全方位/整体）
        仅在比较 cue 紧邻、且 Repository 确认无候选（not_found）时按
        comparison operator 忽略；合法公司名（候选命中）与普通
        not_found 不受影响。"""
        has_valid = any(m.status != "not_found" for m in mentions)
        if not has_valid:
            return mentions
        kept = []
        dropped: list[str] = []
        for m in mentions:
            is_comparison_operator = (
                m.status == "not_found"
                and m.text in _COMPARISON_OPERATOR_WORDS
                and bool(query)
                and CompanyEntityResolver._is_comparison_operator_position(query, m)
            )
            if m.status == "not_found" and (
                m.text in _CONTEXT_WORDS or is_comparison_operator
            ):
                dropped.append(m.text)
                continue
            kept.append(m)
        if dropped:
            logger.info("Resolver: 忽略业务上下文片段 %s", dropped)
        return kept

    # ── 默认角色派生（v3.2.1 批次 4 配套）───────────────────────

    @staticmethod
    def _assign_default_roles(relation: str, mentions: list[EntityMention]) -> None:
        """确定性路径按原文顺序补 role（仅对 role 为 None 的公司 mention）。

        - single/continuation/switch：唯一 primary；
        - comparison：按原文顺序第一个 primary、其余 comparison_peer
          （history mention 无坐标，恒排最后）；
        - reference/sequence（中间验收 P1-2）：第一个 primary、其余
          referenced（P0-3 保留 role，防被下游错当 comparison）；
        not_found/needs_refinement 不参与（无身份可绑定）。
        selector 快照已赋 role 的 mention 不受影响（role 非 None 跳过）。
        """
        company_mentions = [m for m in mentions if m.status != "not_found"]
        if relation in ("single", "continuation", "switch"):
            for m in company_mentions:
                if m.role is None:
                    m.role = "primary"
        elif relation == "comparison":
            ordered = sorted(company_mentions, key=_mention_offset_key)
            for idx, m in enumerate(ordered):
                if m.role is None:
                    m.role = "primary" if idx == 0 else "comparison_peer"
        elif relation in ("reference", "sequence"):
            ordered = sorted(company_mentions, key=_mention_offset_key)
            for idx, m in enumerate(ordered):
                if m.role is None:
                    m.role = "primary" if idx == 0 else "referenced"

    # ── span 落定（查询 → 状态赋值 / 分段 / 未识别）────────────

    def _finalize_span(
        self, mention: EntityMention, depth: int = 0
    ) -> tuple[list[EntityMention], list[SegmentationAlternative]]:
        """解析单个 span 为最终 mentions 与未决分段方案。

        Returns:
            (final_mentions, alternatives) — 父 span 若被复合切分返回
            子 mentions；多方案歧义时父保留（status=needs_confirmation），
            方案列表交给语义裁决（P0-4）。
        """
        lookup = self._lookup_mention_with_variants(mention)
        # v3.3.1 §5.1：预算耗尽显式降级（P0——None 访问 .matches 崩溃）
        if lookup.budget_exhausted:
            return self._budget_exhausted_fallback(mention)
        lookup_result = lookup.result

        # 纯 contains 是结构不明确的低置信召回：复合公司名应先分段，
        # “公司名 + 有/存在/持有/拥有”应先做一次候选驱动谓语剥离。
        # 精确名称、别名、prefix/reverse_contains 仍保持原优先级。
        if lookup_result.matches and all(
            match.match_kind == "contains" for match in lookup_result.matches
        ):
            alternatives = self._segment_compound(mention, depth)
            if len(alternatives) == 1:
                chosen = alternatives[0]
                merged: list[EntityMention] = []
                nested: list[SegmentationAlternative] = []
                for sub in chosen.mentions:
                    sub_final, sub_alts = self._finalize_span(sub, depth + 1)
                    merged.extend(sub_final)
                    nested.extend(sub_alts)
                return merged, nested
            if len(alternatives) > 1:
                mention.status = "needs_confirmation"
                mention.resolution_source = None
                return [mention], alternatives

            for predicate in _TRAILING_COMPANY_PREDICATES:
                if not mention.text.endswith(predicate):
                    continue
                left = mention.text[: -len(predicate)]
                if len(left) < 2:
                    continue
                left_outcome = self._budgeted_lookup(left)
                if left_outcome.budget_exhausted:
                    return self._budget_exhausted_fallback(mention)
                left_result = left_outcome.result
                if not left_result.matches or left_result.truncated:
                    continue
                mention.text = left
                mention.end = mention.start + len(left)
                mention.mention_id = make_mention_id(mention.start, mention.end, left)
                lookup_result = left_result
                break
            # v3.3 批次 B：contains 低置信命中时优先尝试段首连接词剥离
            # （"与康美药业"→"康美药业"精确命中，不留在 contains 确认态）
            if lookup_result.matches and all(
                match.match_kind == "contains" for match in lookup_result.matches
            ):
                for connector in _COMPOUND_CONNECTORS:
                    if not mention.text.startswith(connector):
                        continue
                    left = mention.text[len(connector) :]
                    if len(left) < 2:
                        continue
                    left_outcome = self._budgeted_lookup(left)
                    if left_outcome.budget_exhausted:
                        return self._budget_exhausted_fallback(mention)
                    left_result = left_outcome.result
                    if left_result.matches and not left_result.truncated:
                        mention.text = left
                        mention.start = mention.start + len(connector)
                        mention.end = mention.start + len(left)
                        mention.mention_id = make_mention_id(
                            mention.start, mention.end, left
                        )
                        lookup_result = left_result
                        break

        if lookup_result.matches:
            mention.candidates = lookup_result.matches
            if lookup_result.truncated:
                mention.status = "needs_refinement"  # 候选截断：需补充名称
                mention.truncated = True  # v3.2.1 批次 7：按 mention 粒度置位
                mention.resolution_source = resolution_source_from_match_kind(
                    lookup_result.matches[0].match_kind
                )
                return [mention], []
            unique = len(lookup_result.matches) == 1
            if unique and self._should_auto_lock(mention, lookup_result):
                mention.status = "auto_selected"
                mention.selected_wind_code = lookup_result.matches[0].company.wind_code
                mention.resolution_source = resolution_source_from_match_kind(
                    lookup_result.matches[0].match_kind
                )
            elif unique:
                # 变体命中唯一：候选确认（条件 4 不满足，不自动锁定）
                mention.status = "needs_confirmation"
                mention.resolution_source = resolution_source_from_match_kind(
                    lookup_result.matches[0].match_kind
                )
            else:
                mention.status = "needs_confirmation"
                mention.resolution_source = resolution_source_from_match_kind(
                    lookup_result.matches[0].match_kind
                )
            return [mention], []

        # 无候选：复合分段
        alternatives = self._segment_compound(mention, depth)
        if len(alternatives) == 1:
            chosen = alternatives[0]
            merged: list[EntityMention] = []
            nested: list[SegmentationAlternative] = []
            for sub in chosen.mentions:
                sub_final, sub_alts = self._finalize_span(sub, depth + 1)
                merged.extend(sub_final)
                nested.extend(sub_alts)
            return merged, nested
        if len(alternatives) > 1:
            # P0-4：分段歧义 → 语义裁决/澄清，不扁平合并
            mention.status = "needs_confirmation"
            mention.resolution_source = None
            return [mention], alternatives
        # v3.2.1 批次 3：受控所有格边界（替代任意逐字截短）——
        # 直接查询与复合分段均无候选后，仅当"的"左侧存在未截断候选
        # 且右侧以封闭业务词开头时才解析左侧；命中固定 needs_confirmation
        # （matched_text != 原 span，不满足锁定条件 4，绝不自动锁定）；
        # 禁止递归截短；无合法边界即 not_found
        for left, right in _possessive_splits(mention.text):
            if len(left) < 2 or not _is_business_phrase(right):
                continue
            left_outcome = self._budgeted_lookup(left)
            if left_outcome.budget_exhausted:
                return self._budget_exhausted_fallback(mention)
            left_result = left_outcome.result
            if left_result.matches and not left_result.truncated:
                mention.text = left
                mention.end = mention.start + len(left)
                mention.mention_id = make_mention_id(mention.start, mention.end, left)
                mention.candidates = left_result.matches
                mention.status = "needs_confirmation"
                mention.resolution_source = "substring"
                return [mention], []
        # v3.3 批次 B：段首单字连接词剥离方案（"和茅台"→"茅台"）——
        # 合法性由候选召回验证；命中后按正常锁定判定（原文连续子区间、
        # 非逐字截短）
        for connector in _COMPOUND_CONNECTORS:
            if not mention.text.startswith(connector):
                continue
            left = mention.text[len(connector) :]
            if len(left) < 2:
                continue
            left_outcome = self._budgeted_lookup(left)
            if left_outcome.budget_exhausted:
                return self._budget_exhausted_fallback(mention)
            left_result = left_outcome.result
            if left_result.matches and not left_result.truncated:
                mention.text = left
                mention.start = mention.start + len(connector)
                mention.end = mention.start + len(left)
                mention.mention_id = make_mention_id(mention.start, mention.end, left)
                lookup_result = left_result
                break
        if lookup_result.matches:
            mention.candidates = lookup_result.matches
            unique = len(lookup_result.matches) == 1
            if unique and self._should_auto_lock(mention, lookup_result):
                mention.status = "auto_selected"
                mention.selected_wind_code = lookup_result.matches[0].company.wind_code
            else:
                mention.status = "needs_confirmation"
            mention.resolution_source = resolution_source_from_match_kind(
                lookup_result.matches[0].match_kind
            )
            return [mention], []
        # v3.3 §4.2 / v3.3.1 §5.1：查询预算耗尽 → 显式 needs_refinement
        # + issue，不得静默丢弃后继续自动绑定（各查询点已提前返回，此为
        # 缓存命中零候选时预算恰好耗尽的兜底）
        if self._budget is not None and self._budget.exhausted:
            return self._budget_exhausted_fallback(mention)
        mention.status = "not_found"
        mention.resolution_source = None
        return [mention], []

    def _relink_with_sub_spans(
        self,
        user_query: str,
        mentions: list[EntityMention],
        verdicts: list[MentionnessVerdict],
    ) -> list[EntityMention] | None:
        """8/17 收敛 A：消费 mentionness 的 sub_span 做二次链接。

        对 verdict=company_mention 且携带有效 sub_span（原文子串 ≠ 整句）
        的 not_found mention：用子实体重新查库——
        - 子实体命中候选 → 用子实体 mention 替换原整句（治本：库内
          公司被"施事+介词"句式吞掉的场景）；
        - 子实体仍无候选 → 用子实体替代原整句（报"金百泽"疑似而非
          "证券机构对金百泽"）。
        无有效 sub_span → 返回 None（保持原逻辑）。
        """
        sub_by_id: dict[str, str] = {}
        for v in verdicts or []:
            sub = (v.sub_span or "").strip()
            if v.verdict == "company_mention" and len(sub) >= 2:
                sub_by_id[v.span_id] = sub
        if not sub_by_id:
            return None
        q = user_query or ""
        out: list[EntityMention] = []
        changed = False
        for m in mentions:
            sub = sub_by_id.get(m.mention_id)
            if m.status != "not_found" or not sub or sub == m.text:
                out.append(m)
                continue
            start = q.find(sub, m.start or 0, m.end or len(q))
            if start < 0:
                out.append(m)
                continue
            sub_mention = EntityMention(
                mention_id=make_mention_id(start, start + len(sub), sub),
                text=sub,
                start=start,
                end=start + len(sub),
            )
            sub_final, _alts = self._finalize_span(sub_mention, depth=1)
            if not sub_final:
                out.append(m)
                continue
            changed = True
            if all(x.status in ("not_found", "needs_refinement") for x in sub_final):
                # 子实体仍无候选 → 报子实体疑似（替代整句，坐标对齐原文）
                out.append(
                    m.model_copy(
                        update={
                            "text": sub,
                            "start": start,
                            "end": start + len(sub),
                            "mention_id": sub_mention.mention_id,
                        }
                    )
                )
            else:
                out.extend(sub_final)
        return out if changed else None

    # ── 关系判定（P0-3 映射）────────────────────────────────

    def _decide_relation(
        self,
        query: str,
        mentions: list[EntityMention],
        memory: MemoryContext | None,
    ) -> tuple[str, str]:
        """返回 (relation, relation_status)。

        单个 mention（即使身份待确认）→ single（确认后即唯一主体）；
        多个 mention 且比较/参考信号明确 → comparison/reference。
        """
        if not mentions:
            return ("no_company", "resolved")
        selected = [m for m in mentions if m.selected_wind_code]
        if _detect_reference(query) and len(mentions) >= 2:
            return ("reference", "needs_clarification")
        if _detect_comparison(query, [m.text for m in mentions]):
            return ("comparison", "resolved")
        if len(mentions) == 1:
            prev_code = ""
            if memory is not None:
                prev_code = str(
                    getattr(memory, "resolved_company_code", "") or ""
                ).strip()
            if selected and prev_code and prev_code != selected[0].selected_wind_code:
                return ("switch", "resolved")
            return ("single", "resolved")
        if len(mentions) >= 2:
            return ("ambiguous", "needs_clarification")
        return ("no_company", "resolved")

    # ── 隐式主体（无显式 mention）────────────────────────────

    def _resolve_implicit(
        self, user_query: str, memory: MemoryContext | None
    ) -> EntityResolutionResult:
        """纯指代 → 历史主体延续（memory.is_anaphora 快照）；无历史 → no_company。

        v3.3.2-R1 批次 C（R6 Parallel Change）：主语省略开放词表
        （_CONTEXT_CONTINUATION_CUES）已删除——隐性延续只由确定性
        回指闸门 / Interpreter 决策，本函数不再猜词；target 优先
        结构化 current_company_code（§5.1）。
        """
        if memory is None:
            return EntityResolutionResult(intent="no_company", reason_code="no_memory")
        if not bool(getattr(memory, "is_anaphora", False)):
            return EntityResolutionResult(
                intent="no_company",
                reason_code="no_entity",
                subject_interpretation=self._interp_result,
                subject_interpreter_status=self._interp_status,
            )
        target = self._current_company_code(memory)
        if not target:
            resolved_code = str(
                getattr(memory, "resolved_company_code", "") or ""
            ).strip()
            resolved_name = str(
                getattr(memory, "resolved_entity_name", "") or ""
            ).strip()
            target = resolved_code or resolved_name
        if target:
            company = self._resolve_code_or_name(target)
            if company is not None:
                return self._history_result(company, "history_anaphora")
        return EntityResolutionResult(intent="no_company", reason_code="no_entity")

    @staticmethod
    def _current_company_code(memory: MemoryContext | None) -> str:
        """v3.3.2-R1 §5.1：结构化当前主体（会话状态，非当前轮决定）。"""
        if memory is None:
            return ""
        code = str(getattr(memory, "current_company_code", "") or "").strip()
        if code:
            return code
        # 兼容：老记忆无该字段时回退最近 code
        prev = getattr(memory, "previous_company_codes", None) or []
        return str(prev[0]).strip() if prev else ""

    def _resolve_no_spans(self, user_query: str, memory: MemoryContext | None):
        """v3.3.2-R1 批次 C：Extractor 无 span 的收尾决策。

        确定性回指闸门与 Interpreter 已在 resolve() 主流程处理；此处
        仅保留记忆快照 is_anaphora 的历史延续（老语义兼容）。旧金融
        词表延续路径已删除（R6 Parallel Change）。
        """
        return self._resolve_implicit(user_query, memory)

    def _interpreter_fail_closed(
        self,
        reason_code: str,
        mentionness_verdicts: list[MentionnessVerdict] | None = None,
    ) -> EntityResolutionResult:
        """中间验收 P0-2：Interpreter 未产出可应用裁决（timeout/invalid/
        failed/disabled 或 none/uncertain）→ no_company clarify。

        不沿用历史主体、不落开放金融词表（fail-closed 语义）。
        """
        return EntityResolutionResult(
            intent="no_company",
            reason_code=reason_code,
            selector_status="not_needed",
            mentionness_verdicts=mentionness_verdicts or [],
            resolution_issues=self._issues,
            subject_interpretation=self._interp_result,
            subject_interpreter_status=self._interp_status,
        )

    @staticmethod
    def _history_result(
        company: CompanyRef,
        reason: str,
        subject_interpretation=None,
        interpreter_status: str = "not_needed",
    ) -> EntityResolutionResult:
        # 最终续审 §4 A2：历史 mention 经统一 helper（origin=history，
        # 不伪造 query span）
        mention = _make_history_mention(company, role="primary")
        return EntityResolutionResult(
            intent="continuation",
            mentions=[mention],
            selected_companies=[company],
            reason_code=reason,
            selector_status="not_needed",
            subject_interpretation=subject_interpretation,
            subject_interpreter_status=interpreter_status,
        )

    def _resolve_code_or_name(self, target: str) -> CompanyRef | None:
        """按代码或名称确定性解析（exact 路径）。"""
        result = self._lookup.lookup_mention(target)
        if len(result.matches) == 1 and not result.truncated:
            return result.matches[0].company
        return None

    # ── override 重跑路径（P0-3：局部确认完成后恢复完整决策）────

    def _resolve_with_override(
        self,
        user_query: str,
        override,
        memory: MemoryContext | None,
    ) -> EntityResolutionResult:
        """应用确认后的结构化覆盖重跑。

        校验（任一失败 → 拒绝 override，走正常解析）：
          - query_fingerprint 与当前问题指纹一致；
          - 每个 decision 的 mention_id/span/text 与重新提取结果一致；
          - wind_code 属于该 mention 候选集；
        全部通过 → 恢复 relation + role + 身份，派生 company/
        comparison_targets（relation 不可执行 → 澄清）。
        """
        from app.application.models.company_resolution import make_query_fingerprint

        if make_query_fingerprint(user_query) != override.query_fingerprint:
            logger.warning("Resolver: override 指纹不匹配，拒绝走正常解析")
            return self.resolve(user_query, memory=memory, request_context=None)

        raw_mentions = extract_company_mention_result(user_query).mentions
        # 与主流程一致：先过复合分段（override 的 mention_id 是子 mention，
        # 如 "平安和茅台" → [平安(0,2), 茅台(3,5)]）+ 业务上下文过滤
        finalized: list[EntityMention] = []
        for m in raw_mentions:
            fm, _ = self._finalize_span(m)
            finalized.extend(fm)
        finalized = self._drop_ignored_context(finalized, user_query)
        by_id = {m.mention_id: m for m in finalized}
        # v3.2.1 批次 4 校验 2/3/4：finalized ID 无重复、decisions 非空且
        # 无重复、covered 与 finalized 完全一致（不缺失、不多余）
        if not finalized or len(by_id) != len(finalized):
            logger.warning("Resolver: override finalized mention 异常，拒绝")
            return self.resolve(user_query, memory=memory, request_context=None)
        if not override.decisions:
            logger.warning("Resolver: override decisions 为空，拒绝")
            return self.resolve(user_query, memory=memory, request_context=None)
        covered = {d.mention_id for d in override.decisions}
        if len(covered) != len(override.decisions) or covered != set(by_id):
            logger.warning("Resolver: override 不完整（缺失/多余/重复 mention），拒绝")
            return self.resolve(user_query, memory=memory, request_context=None)
        # 应用决策（span/text/候选身份校验 + 空值拒绝）
        applied: list[EntityMention] = []
        for d in override.decisions:
            m = by_id.get(d.mention_id)
            if m is None:
                logger.warning("Resolver: override mention 未匹配，拒绝")
                return self.resolve(user_query, memory=memory, request_context=None)
            if (m.text, m.start, m.end) != (d.text, d.start, d.end):
                logger.warning("Resolver: override span 不匹配，拒绝")
                return self.resolve(user_query, memory=memory, request_context=None)
            if not d.wind_code or not d.role:
                logger.warning("Resolver: override 空 wind_code/role，拒绝")
                return self.resolve(user_query, memory=memory, request_context=None)
            outcome = self._lookup_mention_with_variants(m)
            if (
                outcome.budget_exhausted
                or not outcome.result.matches
                or outcome.result.truncated
            ):
                logger.warning("Resolver: override 候选不可用，拒绝")
                return self.resolve(user_query, memory=memory, request_context=None)
            allowed = {c.company.wind_code for c in outcome.result.matches}
            if d.wind_code not in allowed:
                logger.warning("Resolver: override 库外代码 %s，拒绝", d.wind_code)
                return self.resolve(user_query, memory=memory, request_context=None)
            m.candidates = outcome.result.matches
            m.selected_wind_code = d.wind_code
            m.status = "user_confirmed"
            m.role = d.role
            m.resolution_source = "user_confirm"
            applied.append(m)
        # v3.2.1 批次 4 校验 7/9：relation 可执行 + 严格终态 role 校验
        if not is_executable_relation(override.relation):
            logger.warning(
                "Resolver: override relation %s 不可执行，拒绝", override.relation
            )
            return self.resolve(user_query, memory=memory, request_context=None)
        if not validate_finalized_relation_roles(override.relation, applied):
            logger.warning("Resolver: override 终态 role/身份校验失败，拒绝")
            return self.resolve(user_query, memory=memory, request_context=None)

        relation = override.relation
        selected_companies: list[CompanyRef] = []
        for me in applied:
            if me.selected_wind_code:
                for c in me.candidates:
                    if c.company.wind_code == me.selected_wind_code:
                        selected_companies.append(c.company)
                        break
        return EntityResolutionResult(
            intent=relation,
            mentions=applied,
            selected_companies=selected_companies,
            unresolved_mentions=[],
            needs_confirmation=False,
            reason_code="override",
            selector_status="not_needed",
            resolution_issues=self._issues,
        )

    # ── 主流程 ──────────────────────────────────────────────

    def resolve(
        self,
        user_query: str,
        memory: MemoryContext | None = None,
        request_context: RequestContext | None = None,
    ) -> EntityResolutionResult:
        """实体解析主入口（确定性路径；语义裁决点输出待确认状态）。

        优先级：
          0. request_context.entity_overrides（局部确认重跑，最高优先）
          1. request_context.company_code（显式代码）
          2. 显式 mention 提取与候选解析（未识别 → 不沿用历史，防串）
          3. 纯指代/主语省略 → 历史延续
        """
        # v3.3 批次 B / v3.3.1 §5.2：每次解析入口重置查询预算与 issues；
        # limit 单一来源 _MAX_LOOKUPS_PER_QUERY（测试可注入较小预算）
        self._budget = ProposalLookupBudget(
            self._lookup,
            limit=self._lookup_limit or _MAX_LOOKUPS_PER_QUERY,
        )
        self._issues = []
        # v3.3.2-R1 §8：低置信主体解释审计（每次解析重置）
        self._interp_status = "not_needed"
        self._interp_result = None
        self._relation_proposal = None
        override = (
            getattr(request_context, "entity_overrides", None)
            if request_context
            else None
        )
        if override is not None:
            return self._resolve_with_override(user_query, override, memory)
        explicit_code = (
            getattr(request_context, "company_code", "") if request_context else ""
        )
        if explicit_code:
            company = self._resolve_code_or_name(explicit_code)
            if company is None:
                return EntityResolutionResult(
                    intent="no_company",
                    reason_code="company_not_found",
                    selector_status="not_needed",
                )
            mention = EntityMention(
                mention_id=make_mention_id(0, 0, "explicit"),
                text=explicit_code,
                start=0,
                end=0,
                status="auto_selected",
                selected_wind_code=company.wind_code,
                role="primary",
                resolution_source="code",
            )
            return EntityResolutionResult(
                intent="single",
                mentions=[mention],
                selected_companies=[company],
                reason_code="explicit_code",
                selector_status="not_needed",
            )

        # v3.3 批次 B（P1-4）：query 内嵌 Wind Code 不再提前 return single——
        # 代码 span 由 extractor finditer 提取进 mention 集合（与名称 span
        # 同集合），统一走 _finalize_span 查候选与关系判定（"600518.SH 和
        # 600519.SH 对比"→ 两个代码 mention；"600518.SH 和茅台对比"→
        # 代码 + 名称）
        extraction = extract_company_mention_result(user_query)
        raw_mentions = extraction.mentions
        # v3.3.3 收口批次 C（方案 §3.5）：数据库精确名称 spotting 并行
        # 通道补召回（官方三题反例），身份仍由 Repository 二次链接
        raw_mentions = _merge_exact_spots(user_query, raw_mentions)
        if not raw_mentions:
            current_code = self._current_company_code(memory)
            # 最终续审 §5 B2/B4：确定性主体决策（零 LLM）——元数据来自
            # Extractor 结构化结果（明确回指/回指框架/业务谓词追问）。
            # 有 current → continuation；无 current → no_company
            # （已知业务追问不伪造主体，也不浪费 LLM）
            subject_signal = (
                extraction.explicit_anaphora
                or extraction.back_reference
                or extraction.had_subject_terminator
            )
            if subject_signal and bool(current_code):
                company = self._resolve_code_or_name(current_code)
                if company is not None:
                    return self._history_result(
                        company, "continuation:deterministic_subject"
                    )
            # subject_signal 但无 current：跳过 Interpreter（零 LLM），
            # 落 _resolve_no_spans（is_anaphora 记忆快照兼容）——
            # 已知业务追问不伪造主体、不浪费 LLM
            # v3.3.2-R1 §7：低置信语义——Interpreter 单次裁决
            # （可提出新公司 span 进入主流程二次链接，或判定 previous）
            if not subject_signal and self._interpreter is not None:
                status, interp = self._interpreter.interpret(
                    query=user_query,
                    unresolved_mentions=[],
                    has_current_subject=bool(current_code),
                )
                # shadow/timeout/invalid 均只记录审计（权威不变）
                self._interp_status = (
                    "shadow" if self._interpreter.mode == "shadow" else status
                )
                self._interp_result = interp
                if self._interpreter.mode == "fallback":
                    if status == "completed" and interp is not None:
                        if interp.subject_reference == "previous":
                            company = self._resolve_code_or_name(current_code)
                            if company is not None:
                                return self._history_result(
                                    company,
                                    "continuation:interpreter_previous",
                                    subject_interpretation=interp,
                                    interpreter_status="completed",
                                )
                        elif interp.subject_reference == "new":
                            # 提出的 span 进入主流程（prime/finalize/
                            # relation 全套；Repository 二次链接，
                            # 零候选继续 not_found）
                            raw_mentions = [
                                EntityMention(
                                    mention_id=make_mention_id(s.start, s.end, s.text),
                                    text=s.text,
                                    start=s.start,
                                    end=s.end,
                                )
                                for s in _all_company_spans(interp)
                            ]
                            # P1-2：relation 只作 proposal，主流程统一裁决
                            self._relation_proposal = interp.company_relation
                        else:
                            return self._interpreter_fail_closed(
                                "interpreter_no_subject"
                            )
                    else:
                        # P0-2：timeout/invalid/failed/disabled 或 completed
                        # 但 none/uncertain → 尊重裁决 fail-closed，
                        # 不得落入金融词表沿用历史主体
                        return self._interpreter_fail_closed(
                            (
                                "interpreter_unresolved"
                                if status != "completed"
                                else "interpreter_no_subject"
                            )
                        )
        if not raw_mentions:
            # v3.3.2 §6.3：无 span 也必须经主体动作决策（明确回指/
            # 金融追问 + 历史 → continuation；off/shadow 权威不变）
            return self._resolve_no_spans(user_query, memory)

        # v3.3.1 §5.2 阶段 1：顶层原始 span 预留查询（公平召回）。
        # 顶层唯一 span 数超过预算上限 → 整句 fail closed：全部
        # needs_refinement、零自动绑定（不得只解析前 limit 个）
        unique_top = self._dedupe_top_mentions(raw_mentions)
        if len(unique_top) > self._budget.limit:
            for m in raw_mentions:
                m.status = "needs_refinement"
                m.truncated = True
                m.resolution_source = None
            self._add_issue(
                "too_many_entity_mentions",
                [m.mention_id for m in raw_mentions],
                f"顶层实体 span 数 {len(unique_top)} 超过查询预算上限 "
                f"{self._budget.limit}",
            )
            return EntityResolutionResult(
                intent="ambiguous",
                mentions=raw_mentions,
                unresolved_mentions=[m.text for m in raw_mentions],
                needs_confirmation=False,
                reason_code="too_many_entity_mentions",
                selector_status="not_needed",
                resolution_issues=self._issues,
            )
        # 所有顶层原始 span 先各获得一次查询机会（结果进 memoize 缓存，
        # _finalize_span 首次查询直接读缓存，不重复访问 Repository）
        self._budget.prime_originals(raw_mentions)

        final_mentions: list[EntityMention] = []
        pending_alternatives: list[SegmentationAlternative] = []
        for m in raw_mentions:
            finalized, alts = self._finalize_span(m)
            final_mentions.extend(finalized)
            pending_alternatives.extend(alts)

        # v3.2.1 批次 2：业务上下文过滤——不扩张 MentionStatus，直接从
        # 最终 mentions 移除；pending/override/REST/WS 只保留公司身份 mention
        # v3.3.4 收口复核清单 §6：比较语法范围词同样在此按条件忽略
        final_mentions = self._drop_ignored_context(final_mentions, user_query)
        # 所有 span 均无公司候选 且 整句为明确行业研究主题 → 非阻断
        # no_company，由意图层继续路由 research（本层不置任何公司错误）；
        # 模板不命中（如"火星科技行业风险"）保持 not_found 阻断。
        # 中间验收 P0-2：提前到 Interpreter/Mentionness 之前——纯模板
        # 零 LLM 优先，避免 fallback 失败边界把行业研报问题变成 clarify
        if all(m.status == "not_found" for m in final_mentions) and (
            _is_definite_research_topic_query(user_query)
        ):
            return EntityResolutionResult(
                intent="no_company",
                reason_code="research_context",
                selector_status="not_needed",
                resolution_issues=self._issues,
            )

        # v3.3 批次 D：零候选 span 的 NIL 三态判定。8/16 语义裁决启用
        # （队长拍板，suggest/auto）：non_company_context 生效（下方
        # 应用，移除不报"疑似公司"）；off 模式零调用、结果仅进审计。
        # 调用条件：任一 not_found span 即批量判定（一次 LLM 调用），
        # company_mention 保持 not_found、abstain 保持澄清。
        # 8/17 收敛 A：mentionness 同时输出 sub_span（片段内公司名子串），
        # 完成后立即消费做二次链接（合并原独立 span_extractor 组件）。
        mentionness_verdicts: list[MentionnessVerdict] = []
        not_found_mentions = [m for m in final_mentions if m.status == "not_found"]
        if self._mentionness is not None and not_found_mentions:
            # v3.3.1 §9.3：批量判定——一条 query 最多一次 mentionness
            # LLM 调用（classify_many 内程序校验 span 一一对应）
            status, decision = self._mentionness.classify_many(
                user_query=user_query,
                spans=[
                    {"span_id": m.mention_id, "span_text": m.text}
                    for m in not_found_mentions
                ],
            )
            if status == "completed" and decision is not None:
                mentionness_verdicts = decision.verdicts
                relinked = self._relink_with_sub_spans(
                    user_query, final_mentions, decision.verdicts
                )
                if relinked is not None:
                    final_mentions = relinked
                    not_found_mentions = [
                        m for m in final_mentions if m.status == "not_found"
                    ]
        # v3.3.2 §6.3：有效公司 mention 为空 → 主体动作决策。历史延续
        # 是一等决策；疑似新公司（plausible/uncertain）阻断继承
        effective = [
            m
            for m in final_mentions
            if m.status not in ("not_found", "needs_refinement")
        ]
        if not effective:
            # 最终续审 §5 B3：全 NIL span 完全由 canonical 业务术语 +
            # 语法成分解释（如"存贷双高"来自 R3 元数据）→ 业务谓词
            # 追问 context，按结构化元数据确定性延续（零 LLM）；
            # 残留疑似新公司证据时照常阻断（防串）
            if (
                final_mentions
                and all(m.status == "not_found" for m in final_mentions)
                and all(
                    explainable_as_canonical_context(m.text) for m in final_mentions
                )
            ):
                current_code = self._current_company_code(memory)
                if (
                    deterministic_subject_reference(
                        has_current_subject=bool(current_code),
                        explicit_anaphora=extraction.explicit_anaphora,
                        back_reference=extraction.back_reference,
                        had_subject_terminator=extraction.had_subject_terminator,
                        has_new_entity_evidence=False,
                    )
                    == "previous"
                ):
                    company = self._resolve_code_or_name(current_code)
                    if company is not None:
                        return self._history_result(
                            company, "continuation:canonical_context"
                        )
                # 已知业务追问但无 current → 零 LLM no_company（不伪造）
                return EntityResolutionResult(
                    intent="no_company",
                    reason_code="no_entity",
                    selector_status="not_needed",
                    resolution_issues=self._issues,
                )
            # v3.3.2-R1 §7：低置信主体决策——先尝试 Interpreter
            # （off 零调用；shadow 只记录权威不变；fallback 应用）
            if self._interpreter is not None:
                current_code = self._current_company_code(memory)
                status, interp = self._interpreter.interpret(
                    query=user_query,
                    unresolved_mentions=[
                        UnresolvedMentionInput(
                            mention_id=m.mention_id,
                            text=m.text,
                            start=m.start,
                            end=m.end,
                        )
                        for m in final_mentions
                    ],
                    has_current_subject=bool(current_code),
                )
                # shadow/timeout/invalid 均只记录审计（权威不变）
                self._interp_status = (
                    "shadow" if self._interpreter.mode == "shadow" else status
                )
                self._interp_result = interp
                if self._interpreter.mode == "fallback":
                    if status == "completed" and interp is not None:
                        if interp.subject_reference == "previous":
                            company = self._resolve_code_or_name(current_code)
                            if company is not None:
                                return self._history_result(
                                    company,
                                    "continuation:interpreter_previous",
                                    subject_interpretation=interp,
                                    interpreter_status="completed",
                                )
                        elif interp.subject_reference == "new":
                            # Repository 二次链接 Interpreter 提出的原文
                            # span；有 uncertain disposition 时不应用
                            # （fail-closed）
                            any_uncertain = any(
                                d.kind == "uncertain"
                                for d in interp.input_span_dispositions
                            )
                            re_final: list[EntityMention] = []
                            re_alts: list[SegmentationAlternative] = []
                            for s in _all_company_spans(interp):
                                m = EntityMention(
                                    mention_id=make_mention_id(s.start, s.end, s.text),
                                    text=s.text,
                                    start=s.start,
                                    end=s.end,
                                )
                                fm, alts = self._finalize_span(m)
                                re_final.extend(fm)
                                re_alts.extend(alts)
                            if re_final and not any_uncertain:
                                final_mentions = re_final
                                pending_alternatives.extend(re_alts)
                                # P1-2：relation 只作 proposal——是否
                                # 应用在 _decide_relation 后统一裁决
                                self._relation_proposal = interp.company_relation
                        else:
                            # completed 但 none/uncertain → 尊重裁决
                            return self._interpreter_fail_closed(
                                "interpreter_no_subject",
                                mentionness_verdicts,
                            )
                    else:
                        # P0-2：timeout/invalid/failed/disabled 或 completed
                        # 但 none/uncertain → 尊重裁决 fail-closed，
                        # 不得落入金融词表沿用历史主体
                        return self._interpreter_fail_closed(
                            (
                                "interpreter_unresolved"
                                if status != "completed"
                                else "interpreter_no_subject"
                            ),
                            mentionness_verdicts,
                        )
            # v3.3.2-R1 批次 C（R6 Parallel Change）：旧金融词表延续
            # 路径已删除——off/shadow 模式此处落下文（relation 层
            # no_company），fallback 失败已在批次 A2 fail-closed。

        # 8/16 语义裁决启用（队长拍板，suggest/auto）：mentionness 的
        # non_company_context 判定生效——被判定为非公司上下文的零候选
        # span 从候选集合移除，不再报"疑似公司"（根治停用词穷举：
        # 评价/点评/聊聊等无需逐个进词表）。canonical 业务延续与
        # Interpreter 已在上方优先处理，此处仅解释剩余未检索到候选
        # 且被判定为非公司的 span；company_mention/abstain 保持原状
        # （fail-closed：不猜测、不伪造主体）。
        if self._mentionness is not None and self._mentionness.mode in (
            "suggest",
            "auto",
        ):
            non_company_ids = {
                v.span_id
                for v in mentionness_verdicts
                if v.verdict == "non_company_context"
            }
            if non_company_ids:
                remaining = [
                    m for m in final_mentions if m.mention_id not in non_company_ids
                ]
                if not remaining:
                    # 全部 span 均解释为非公司上下文 → 温和 no_company，
                    # 不报"疑似公司"、不伪造主体（含无历史时可引导）。
                    return EntityResolutionResult(
                        intent="no_company",
                        reason_code="non_company_context",
                        mentions=final_mentions,
                        selected_companies=[],
                        unresolved_mentions=[],
                        needs_confirmation=False,
                        selector_status="not_needed",
                        resolution_issues=self._issues,
                        segmentation_alternatives=pending_alternatives,
                        selected_alternative_ids={},
                        subject_interpretation=self._interp_result,
                        subject_interpreter_status=self._interp_status,
                        semantic_suggestion=None,
                        semantic_attempts=0,
                        semantic_validation_error="",
                        mentionness_verdicts=mentionness_verdicts,
                    )
                final_mentions = remaining

        relation, relation_status = self._decide_relation(
            user_query, final_mentions, memory
        )

        # v3.3.2-R1 中间验收 P1-2：Interpreter 的 company_relation 作为
        # relation proposal——仅当 spans 经 Repository 二次链接后全部
        # 唯一绑定且 ≥2 个不同 wind_code 时应用；任一 span NIL/歧义 →
        # 不应用，保留 candidates/clarify。role 由原文顺序物化
        # （_assign_default_roles），Interpreter 无权决定 identity/role。
        relation, relation_status = apply_relation_proposal(
            relation,
            relation_status,
            self._relation_proposal,
            final_mentions,
        )

        # 最终续审 §4 A3：单绑定新公司 + comparison 语义 + 不同 current
        # subject → 物化历史 peer（origin=history，不伪造 query span）；
        # 无 current 或同代码 → 关系澄清，不得生成单主体 comparison
        if relation == "comparison" and len(final_mentions) == 1:
            new_code = final_mentions[0].selected_wind_code
            if new_code:
                current_code = self._current_company_code(memory)
                if current_code and current_code != new_code:
                    peer = self._resolve_code_or_name(current_code)
                    if peer is not None:
                        final_mentions[0].role = "primary"
                        final_mentions.append(
                            _make_history_mention(peer, role="comparison_peer")
                        )
                    else:
                        relation_status = "needs_clarification"
                else:
                    relation_status = "needs_clarification"

        # 语义裁决（v3.1 §5）：候选歧义 OR 关系歧义 OR 分段歧义
        selector_status = "not_needed"
        # v3.3 批次 C（§5.4）：suggest 审计建议——默认 None，仅在
        # suggest 模式 completed 时记录（不改变权威结果）
        semantic_suggestion = None
        # v3.3.1 §8.1：权威选择映射 parent_mention_id -> alternative_id
        # （仅 auto 全部 select 时记录；suggest/off 恒为空）
        selected_alternative_ids: dict[str, str] = {}
        if self._selector is not None:
            # 每次解析前重置 selector 审计（避免高置信场景沿用上次
            # 裁决的 attempts/error 残留）
            self._selector.last_attempts = 0
            self._selector.last_validation_error = ""
        if self._selector is not None and (
            any(m.status == "needs_confirmation" for m in final_mentions)
            or relation_status == "needs_clarification"
            or pending_alternatives
        ):
            selector_status, decision = self._selector.decide(
                user_query=user_query,
                mentions=final_mentions,
                alternatives=pending_alternatives or None,
                current_relation=relation,
                memory=memory,
            )
            if selector_status == "completed" and decision is not None:
                if self._selector.mode == "suggest":
                    # v3.3 批次 C（§5.4）：suggest 完全只读——只保存审计
                    # 建议，不改变 mention 状态/身份/relation/role/分段/
                    # 下游路由（离线影子评测消费）
                    semantic_suggestion = decision
                else:
                    # v3.3.1 §6.1：auto 只能整体采用 verifier 验证快照，
                    # 不得重新 _finalize_span（避免重复查库/耗预算/候选集
                    # 漂移）。任一 abstain 存在时不应用任何新增身份。
                    validated = self._selector.last_validated
                    if validated is None:
                        logger.warning(
                            "Resolver: auto completed 但无验证快照，降级不清洗"
                        )
                    else:
                        has_abstain = bool(validated.unresolved_parent_ids) or any(
                            d.action == "abstain" for d in decision.identity_decisions
                        )
                        if not has_abstain:
                            # 全部 select：整体替换为快照（子 mention 已含
                            # 模拟身份/role），补状态与来源
                            final_mentions = list(validated.adopted_mentions)
                            for d in decision.identity_decisions:
                                if d.action != "select":
                                    continue
                                m = next(
                                    (
                                        x
                                        for x in final_mentions
                                        if x.mention_id == d.mention_id
                                    ),
                                    None,
                                )
                                if m is not None:
                                    m.status = "llm_selected"
                                    m.resolution_source = "llm"
                            # §8.1：权威选择映射（Pending 兼容单值由
                            # ws_turn_runner 派生）
                            selected_alternative_ids = {
                                sd.parent_mention_id: sd.alternative_id or ""
                                for sd in decision.segmentation_decisions
                                if sd.action == "select" and sd.alternative_id
                            }
                        # abstain 存在：不替换 mentions、不应用身份/role
                        # （§6.1/6.3：整体不应用新身份，纯降级在下方
                        # 未解决分段处理中执行）
                        relation = decision.relation
                        relation_status = (
                            "resolved"
                            if relation
                            in ("single", "continuation", "switch", "comparison")
                            else "needs_clarification"
                        )
        # v3.3.1 §6.2 / §8.1：权威结果存在未解决分段歧义父（off/超时/
        # invalid/segmentation abstain/suggest 未采用）时，父 mention 不得
        # 以"无候选 needs_confirmation"进入 WS 确认（用户无法操作且
        # pending 不携带 alternatives）——降级 needs_refinement 并写
        # segmentation_ambiguous issue（auto 全 select 已替换父，无此状态；
        # 无候选的 needs_confirmation 只可能是分段歧义父）
        if pending_alternatives:
            unresolved_ids: list[str] = []
            for m in final_mentions:
                if m.status == "needs_confirmation" and not m.candidates:
                    m.status = "needs_refinement"
                    m.truncated = True
                    m.resolution_source = None
                    unresolved_ids.append(m.mention_id)
            if unresolved_ids:
                self._add_issue(
                    "segmentation_ambiguous",
                    sorted(unresolved_ids),
                    "分段方案存在歧义，请补充完整公司名称澄清",
                )
        # v3.2.1 批次 4 配套：确定性路径补默认 role（override 严格终态
        # 校验与 claim 快照依赖完整 role）
        self._assign_default_roles(relation, final_mentions)
        selected_companies: list[CompanyRef] = []
        for me in final_mentions:
            if me.selected_wind_code:
                for c in me.candidates:
                    if c.company.wind_code == me.selected_wind_code:
                        selected_companies.append(c.company)
                        break

        needs_confirmation = any(
            me.status == "needs_confirmation" for me in final_mentions
        )
        # 语义裁决后重算 unresolved（已绑定/已锁定的不再计入）
        unresolved = [
            me.text
            for me in final_mentions
            if me.status in ("not_found", "needs_refinement", "needs_confirmation")
        ]
        # 最终续审 §4 A4：统一终态校验——非法可执行 relation 不得
        # 离开 Resolver（保留诊断 issue，降级 ambiguous 澄清，不静默
        # 删公司）
        invalid_reason = validate_relation_final_state(relation, final_mentions)
        if invalid_reason:
            self._add_issue(
                "invalid_relation",
                [m.mention_id for m in final_mentions],
                invalid_reason,
            )
            # 降级策略（§4 A4）：NIL/refinement 零绑定 → no_company。
            # comparison 在部分身份待确认时保留 comparison 关系，避免
            # 丢失 WS 局部确认所需的关系语义；最后一个身份确认后由
            # ws_session_manager 再做严格终态校验。已绑定但同码、单主体
            # 或包含 NIL/refinement 的 comparison 仍降级为 ambiguous。
            bound = [m for m in final_mentions if m.selected_wind_code]
            is_nil_like = not bound and all(
                m.status in ("not_found", "needs_refinement") for m in final_mentions
            )
            pending_comparison = (
                relation == "comparison"
                and needs_confirmation
                and not any(
                    m.status in ("not_found", "needs_refinement")
                    for m in final_mentions
                )
            )
            downgraded_intent = (
                "no_company"
                if is_nil_like
                else ("comparison" if pending_comparison else "ambiguous")
            )
            return EntityResolutionResult(
                intent=downgraded_intent,
                mentions=final_mentions,
                selected_companies=selected_companies,
                unresolved_mentions=unresolved,
                needs_confirmation=(needs_confirmation or not is_nil_like),
                reason_code=invalid_reason,
                selector_status=selector_status,
                resolution_issues=self._issues,
                segmentation_alternatives=pending_alternatives,
                selected_alternative_ids=selected_alternative_ids,
                subject_interpretation=self._interp_result,
                subject_interpreter_status=self._interp_status,
                semantic_suggestion=semantic_suggestion,
                semantic_attempts=(
                    self._selector.last_attempts if self._selector is not None else 0
                ),
                semantic_validation_error=(
                    self._selector.last_validation_error
                    if self._selector is not None
                    else ""
                ),
                mentionness_verdicts=mentionness_verdicts,
            )
        return EntityResolutionResult(
            intent=relation,
            mentions=final_mentions,
            selected_companies=selected_companies,
            unresolved_mentions=unresolved,
            needs_confirmation=needs_confirmation,
            reason_code="deterministic",
            selector_status=selector_status,
            resolution_issues=self._issues,
            segmentation_alternatives=pending_alternatives,
            selected_alternative_ids=selected_alternative_ids,
            subject_interpretation=self._interp_result,
            subject_interpreter_status=self._interp_status,
            # v3.3 批次 C（§5.4）：suggest 审计字段（离线影子评测消费）
            semantic_suggestion=semantic_suggestion,
            semantic_attempts=(
                self._selector.last_attempts if self._selector is not None else 0
            ),
            semantic_validation_error=(
                self._selector.last_validation_error
                if self._selector is not None
                else ""
            ),
            mentionness_verdicts=mentionness_verdicts,
        )
