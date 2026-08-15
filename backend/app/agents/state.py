"""Agent State — V12 §7.3.

TypedDict + Annotated reducer pattern for LangGraph StateGraph.
"""

from datetime import date
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import add_messages
from pydantic import BaseModel, Field

# canonical 模型定义于 domain/evidence/models.py，此处 re-export 保持导入兼容
from app.domain.evidence.models import Claim, EvidenceRef

# 舆情影响结论（⑧ B2）复用 REST schema，保证 REST/WS/Agent 三出口同构
from app.api.v1.schemas.events import ImpactConclusion


# ── V12 §7.3 模型 ──────────────────────────────────────────


class CompanyRef(BaseModel):
    """公司引用 — V12 §7.3."""

    entity_id: str
    wind_code: str
    sec_name: str
    exchange: str
    industry_l1: str | None = None
    # 公司事实轻量查询（R10）：resolve_entity 查询时一并填充，
    # generate_answer 无需再建数据库连接
    listing_date: str | None = Field(None, description="上市日期(YYYY-MM-DD)")
    comp_type_code: str | None = Field(None, description="企业类型代码")


class ComparisonSpec(BaseModel):
    """v3.3.3 批次 C（方案 §5.1）+ v3.3.4（方案 §3.1）：结构化轻量比较规格。

    不变量（方案 §5.1，计划层 fail closed）：
      - cross_company + indicator：至少两个不同 finalized code 且
        metric_ids 恰好一个（批次 D）；
      - same_company_cross_indicator：恰好一个公司且 metric_ids 恰好两个；
      - company_fact：fact_key 非空且 period_policy=not_applicable；
      - overview（v3.3.4）：恰好两个不同 finalized code，不携带外部
        metric_ids/fact_key（服务端固定 profile 注入）；
      - missing_dimension/full：不得启动数值查询。

    v3.3.4 Preview First（方案 §3.1）：mode 表示本轮实际执行的安全模式，
    requested_scope 表示用户请求的范围，两者分离——「全面对比」在两家已
    确认时是 mode=overview + requested_scope=full，而不是把 full 当成已
    完成完整比较。
    """

    scope: Literal["cross_company", "same_company_cross_indicator", "industry"] = (
        "cross_company"
    )
    mode: Literal[
        "indicator",
        "overview",
        "risk",
        "company_fact",
        "full",
        "missing_dimension",
    ] = "indicator"
    # v3.3.4 方案 §3.1：用户请求范围（与 mode 分离）。
    # full/industry 只能在恰好两家 finalized 的 overview 预览中使用；
    # 三家及以上走 comparison_guide（页面/选两家保底），不进入本规格。
    requested_scope: Literal[
        "indicator", "overview", "risk", "company_fact", "full", "industry"
    ] = "indicator"
    metric_ids: list[str] = Field(default_factory=list)
    fact_key: str = ""
    operation: Literal[
        "difference",
        "greater_than",
        "less_than",
        "ranking",
        "risk_level",
        "earlier_than",
    ] = "difference"
    period_policy: Literal[
        "latest_common_period", "explicit_period", "not_applicable"
    ] = "latest_common_period"


# v3.3.4 方案 §2.4：多主体比较参与方上限（交互与查询保护）。
# 超过上限必须要求缩小范围：不传入部分主体、不默认选择、不发起指标查询。
MAX_MULTI_COMPARISON_PARTICIPANTS: int = 5


def validate_comparison_spec(
    spec: ComparisonSpec, participant_codes: list[str]
) -> list[str]:
    """ComparisonSpec 领域不变量（v3.3.3 收口批次 B，方案 §3.2）。

    计划层与比较服务层共用同一校验（plan 后、service 入口各执行一次）。
    返回 issue 列表（空 = 合法）。规则：
      - cross_company + indicator：恰好 2 个不同公司、恰好 1 个 metric；
      - cross_company + overview（v3.3.4）：恰好 2 个不同公司、不携带
        外部 metric_ids/fact_key（profile 由服务端固定注入）；
      - same_company_cross_indicator：恰好 1 个公司、恰好 2 个不同 metric；
      - cross_company + company_fact：恰好 2 家、fact_key 非空、
        period_policy=not_applicable；
      - cross_company + risk/missing_dimension：恰好 2 家、不携带 metric_ids；
      - full/industry：不得进入轻量比较（不得启动数值查询）。
      - v3.3.4 §3.1 第 8 条（收口复核清单 §2.1：入口全局校验）：
        requested_scope=full/industry 只允许由恰好两家 different code 的
        cross_company+overview 预览承载，任何其他组合 fail closed；
        overview 模式的 requested_scope 必须属于 overview/full/industry。
    """
    codes = sorted({str(c) for c in participant_codes if str(c)})
    issues: list[str] = []
    # v3.3.4 §3.1 第 8 条（全局 fail closed，收口复核清单 §2.1/§3.1）：
    # requested_scope=full/industry 只能由恰好两家 different code 的
    # cross_company+overview 预览承载；任何其他 scope/mode/主体数组合
    # （含 same_company_cross_indicator、三家及以上）都必须拒绝。
    # 放在入口统一校验，不依赖某个 scope 分支。
    if spec.requested_scope in ("full", "industry") and not (
        spec.scope == "cross_company" and spec.mode == "overview" and len(codes) == 2
    ):
        issues.append(
            "requested_scope=full/industry 只能由双主体 cross_company+overview 承载"
        )
    if spec.scope == "cross_company":
        if len(codes) != 2:
            issues.append(f"cross_company 需要恰好两家不同公司（实际 {len(codes)} 家）")
        if spec.mode == "indicator":
            if len(spec.metric_ids) != 1:
                issues.append("cross_company+indicator 需要恰好一个指标")
        elif spec.mode == "overview":
            if spec.metric_ids:
                issues.append("overview 不得携带外部 metric_ids（服务端固定 profile）")
            if spec.fact_key:
                issues.append("overview 不得携带 fact_key")
            if spec.requested_scope not in ("overview", "full", "industry"):
                issues.append(
                    "overview 的 requested_scope 必须为 overview/full/industry"
                )
        elif spec.mode == "company_fact":
            if not spec.fact_key:
                issues.append("company_fact 需要 fact_key")
            if spec.period_policy != "not_applicable":
                issues.append("company_fact 的 period_policy 必须为 not_applicable")
        elif spec.mode in ("risk", "missing_dimension"):
            if spec.metric_ids:
                issues.append(f"{spec.mode} 不得携带 metric_ids")
        elif spec.mode == "full":
            issues.append("full 不得进入轻量比较（页面引导）")
        else:
            issues.append(f"未知 mode: {spec.mode}")
    elif spec.scope == "same_company_cross_indicator":
        if spec.mode != "indicator":
            issues.append("same_company_cross_indicator 只支持 indicator 模式")
        if len(codes) != 1:
            issues.append(
                f"same_company_cross_indicator 需要恰好一家公司（实际 {len(codes)} 家）"
            )
        if len(spec.metric_ids) != 2 or len(set(spec.metric_ids)) != 2:
            issues.append("same_company_cross_indicator 需要恰好两个不同指标")
    elif spec.scope == "industry":
        issues.append("industry 不得进入轻量比较（页面行业对标）")
    else:
        issues.append(f"未知 scope: {spec.scope}")
    return issues


class ExecutionPlan(BaseModel):
    """执行计划 — V12 §7.3."""

    intent: str = ""
    requested_modules: list[str] = Field(default_factory=list)
    cross_checks: list[str] = Field(default_factory=list)
    # 公司事实轻量查询键（R9）：industry/exchange/listing_date/comp_type/business/total_shares
    fact_key: str = ""
    # 财务指标短答键（Phase D #3A）
    indicator: str = ""
    # 结构化回答目标（Phase D #3B，如 risk_level）
    answer_target: str = ""
    # v3.3.3 收口批次 D（方案 §3.6）：指标回答语义操作——
    # value=只答数值；assessment=需历史/行业基准判断（如"正常吗"）；
    # trend=需多期间序列；""=默认 value
    answer_operation: str = ""
    as_of: date | None = None
    # 期次语义（#5 期次解析）：report_period=财报期 / as_of=信息截止日 / ""=未指定
    as_of_kind: str = ""
    # 用户原话中的期次文本（如 "2025年报"），用于回答/API meta 展示
    requested_period_text: str = ""
    deadline_ms: int = 8000
    # B2 批次 A（方案 §二）：是否请求舆情影响分析。仅当计划层确定性
    # 双条件（事件指代 cue + 影响/风险 cue）命中才置 True；综合诊断/
    # 宽泛风险/仅公告查询/LLM events=True 一律 False（加性字段，默认 False）。
    impact_requested: bool = False
    # v3.3.3 批次 C（方案 §5.1）：结构化比较规格（唯一比较入口，
    # 禁止散装字段形成非法组合）
    comparison: ComparisonSpec | None = None


class ModuleStatus(BaseModel):
    """模块状态 — V12 §7.3."""

    state: Literal[
        "pending", "running", "success", "partial", "failed", "skipped", "cancelled"
    ] = "pending"
    error_code: str | None = None
    recoverable: bool = False
    duration_ms: int | None = None


class RuntimeState(BaseModel):
    """运行上下文 — V12 §7.3."""

    request_id: str = ""
    trace_id: str = ""
    session_id: str = ""
    thread_id: str = ""
    turn_id: str = ""
    sequence: int = 0
    warnings: list[str] = Field(default_factory=list)


class RequestContext(BaseModel):
    """Explicit client context; takes precedence over text parsing."""

    company_code: str = ""
    as_of: date | None = None
    as_of_kind: str = ""
    requested_period_text: str = ""
    # v3.1 P0-3：局部确认完成后的结构化覆盖（EntityResolutionOverride）。
    # 含 query_fingerprint/relation/decisions（mention 身份+role），
    # 重跑时校验指纹/span/候选身份后恢复完整决策，防止 reference/sequence
    # 被错当 comparison。用 Any 避免 agents↔application 循环导入。
    entity_overrides: Any = None


class FinalResponse(BaseModel):
    """最终响应 — V12 §11.4."""

    answer: str = ""
    risk_level: str = "unknown"
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)


class ExecutedMetricRef(BaseModel):
    """v3.3.3 批次 B（方案 §5.4）：一轮成功执行的指标结构化引用。

    metric_id 为 indicator_semantics 的 canonical ID；只在查询 status=ok
    时写入，not_found/clarification/timeout/unsupported/失败轮不得写入。
    v3.3.3 收口批次 B（方案 §3.4）：company_code 为指标所属公司，
    切换公司后不得跨主体串用历史指标。
    """

    metric_id: str
    period: str = ""
    unit: str = ""
    status: str = "ok"
    company_code: str = ""


class MemoryContext(BaseModel):
    """记忆上下文 — V12 §7.6.

    多轮对话中的指代消解结果与实体跟踪状态。
    """

    resolved_entity_name: str | None = Field(
        None, description="指代消解后的实体名称（如'康美药业'）"
    )
    resolved_company_code: str | None = Field(
        None,
        description="指代消解后的公司代码（摘要/近期轮次 company_code 恢复）",
    )
    is_anaphora: bool = Field(
        False, description="当前 query 是否包含指代词（它/上次那家/该公司等）"
    )
    previous_companies: list[str] = Field(
        default_factory=list, description="历史轮次中涉及的股票简称列表"
    )
    previous_company_codes: list[str] = Field(
        default_factory=list, description="历史轮次中的公司代码（最近优先）"
    )
    referenced_indicators: list[str] = Field(
        default_factory=list, description="历史轮次中提及的财务指标"
    )
    # v3.3.3 批次 B（方案 §5.4）：结构化历史指标——优先消费（canonical
    # ID/period/unit/status），referenced_indicators 文本提取仅作旧数据兼容
    recent_executed_metrics: list[ExecutedMetricRef] = Field(
        default_factory=list, description="历史最近成功执行的规范指标（最近优先）"
    )
    # v3.3.2-R1 §5.1：结构化当前主体——会话状态（与当前 query 是否含
    # 指代词无关；not_found 轮次不清空）。生成：recent_company_codes[0]
    # （含 response_meta.active_company_code 优先）> 摘要 last_company_code
    current_company_code: str | None = Field(
        None, description="结构化当前主体代码（会话级，最近有效主体）"
    )


# ── 模块结果（并行写入，各自隔离） ─────────────────────────


class FinanceResult(BaseModel):
    rule_statuses: dict[str, str] = Field(default_factory=dict)
    rules: list[Any] = Field(default_factory=list)
    periods_available: int = 0
    industry_benchmark: dict = Field(default_factory=dict)
    # 规则明细：rule_id → {rule_name, explanation, severity}（规则引擎产出，供回答展开清单）
    rule_details: dict[str, dict] = Field(default_factory=dict)
    # Phase D #12: LLM 财务解读（固定四段：预警点/数据对比/可能模式/限制说明）
    interpretation: str = ""
    warnings: list[str] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)


class EquityResult(BaseModel):
    graph: dict = Field(default_factory=dict)
    chains: list[dict] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    # Phase D #12: 正式链路载荷（含风险标签/证据/合并说明）
    chain_details: list[dict] = Field(default_factory=list)
    # Phase D #3C: 最新报告期主要股东（确定性回答 DTO）
    shareholders: list[dict] = Field(default_factory=list)


class EventsResult(BaseModel):
    timeline: list[dict] = Field(default_factory=list)
    clusters: list[dict] = Field(default_factory=list)
    rating_changes: list[dict] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    # B2 第二阶段（方案 §4.1）：舆情影响结论 + 降级提示。
    # impacts 复用 REST ImpactConclusion（REST/WS 三出口同构）；
    # 失败/超时/空 → impacts=[] + warning，不阻断既有 timeline/clusters/evidence。
    impacts: list[ImpactConclusion] = Field(default_factory=list)
    impact_warnings: list[str] = Field(default_factory=list)


# ── 交叉验证模型（Phase C 任务 3）──────────────────────────


class CrossValidationCheck(BaseModel):
    """单条交叉验证检查记录."""

    check_id: str
    check_type: str  # equity_vs_events / financial_vs_cashflow / dependency / identity
    status: str  # pass / partial / fail / skipped
    left_module: str
    right_module: str
    time_range: dict = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    warning: str | None = None
    details: dict = Field(default_factory=dict)


class CrossValidationResult(BaseModel):
    """交叉验证结果."""

    checks: list[CrossValidationCheck] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ModuleResults(BaseModel):
    """三模块结果容器。None 表示该模块未执行。"""

    finance: FinanceResult | None = None
    equity: EquityResult | None = None
    events: EventsResult | None = None


# ── AgentState (TypedDict + Annotated) — V12 §7.3 ──────────


class AgentState(TypedDict, total=False):
    user_query: str
    request_context: RequestContext | None
    messages: Annotated[list[Any], add_messages]
    company: CompanyRef | None
    company_candidates: list[CompanyRef]
    # 实体解析权威结果（v3.1 §4）：application/models/company_resolution.py
    # EntityResolutionResult。旧字段 company/company_candidates/
    # comparison_targets 均由 resolve_entity 节点返回时一次性派生，
    # 不在 state 再增加平行 mention 字段。用 Any 避免 agents↔application
    # 循环导入。
    entity_resolution_result: Any
    # 实体解析错误（2026-08-12 三轮审查修订）：company_not_found / too_many_candidates。
    # total=False 无运行时默认值，消费处必须 state.get("entity_resolution_error") or ""
    entity_resolution_error: str
    # 疑似公司但未能识别的片段（如"台积电"），用于回答文案；
    # 消费处必须 state.get("unresolved_fragments") or []
    unresolved_fragments: list[str]
    # 全局候选超过上限被截断（不静默截断展示）
    candidates_truncated: bool
    # 多公司比较目标（R13）：resolve_entity 检出 ≥2 家实体时填充，
    # plan_modules 据此生成 comparison_guide（引导对比页，不静默选一家）
    comparison_targets: list[CompanyRef]
    # P2-2：比较意图标志（命中比较词恒 True，即使 0/1 家候选）——
    # 避免用空列表同时表达"不是比较"和"比较但零命中"
    comparison_requested: bool
    plan: ExecutionPlan | None
    module_status: Annotated[dict[str, ModuleStatus], lambda a, b: {**a, **b}]
    results: Annotated[
        ModuleResults,
        lambda a, b: ModuleResults(
            finance=b.finance or (a and a.finance),
            equity=b.equity or (a and a.equity),
            events=b.events or (a and a.events),
        ),
    ]
    evidence: Annotated[list[EvidenceRef], lambda a, b: a + b]
    claims: Annotated[list[Claim], lambda a, b: a + b]
    final_response: FinalResponse | None
    # v3.3.4 方案 §3.3：轻量概览结构化载荷（{"comparison_mode", "overview_rows"}），
    # generate_answer 产出 → REST/WS 只读透出；非比较轮次为空 dict
    light_comparison: dict[str, Any]
    runtime: RuntimeState
    # Phase D #11: 造假模式匹配结果（list[dict]，pattern_match 节点产出）
    pattern_matches: list[dict]
    memory_context: MemoryContext | None
    # 远期记忆摘要（load_context 注入，dict 形态避免分层反向依赖）
    memory_summary: dict[str, Any] | None
    # 近期轮次的公司代码（最近优先，load_context 注入）
    recent_company_codes: list[str]
    # v3.3.3 批次 B：历史最近成功执行的规范指标（最近优先，load_context 注入，
    # memory 节点消费后写入 MemoryContext.recent_executed_metrics）
    recent_executed_metrics: list[Any]
    # v3.3.3 批次 B：本轮成功执行的指标（generate_answer 产出，persist_turn
    # 写入 response_meta.executed_metrics；失败/澄清/unsupported 轮不写入）
    executed_metric: Any
    provenance_report: Any | None
    cross_validation: CrossValidationResult | None = None
    risk_output: Any | None = None
    # Phase D #2: 深度数值冲突检测结果（list[dict]，CV-NUM-01/02）
    numerical_conflicts: list[dict] | None = None
