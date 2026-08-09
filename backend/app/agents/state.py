"""Agent State — V12 §7.3.

TypedDict + Annotated reducer pattern for LangGraph StateGraph.
"""

from datetime import date
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import add_messages
from pydantic import BaseModel, Field

# canonical 模型定义于 domain/evidence/models.py，此处 re-export 保持导入兼容
from app.domain.evidence.models import Claim, EvidenceRef


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
    as_of: date | None = None
    # 期次语义（#5 期次解析）：report_period=财报期 / as_of=信息截止日 / ""=未指定
    as_of_kind: str = ""
    # 用户原话中的期次文本（如 "2025年报"），用于回答/API meta 展示
    requested_period_text: str = ""
    deadline_ms: int = 8000


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


class FinalResponse(BaseModel):
    """最终响应 — V12 §11.4."""

    answer: str = ""
    risk_level: str = "unknown"
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)


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
    runtime: RuntimeState
    # Phase D #11: 造假模式匹配结果（list[dict]，pattern_match 节点产出）
    pattern_matches: list[dict]
    memory_context: MemoryContext | None
    # 远期记忆摘要（load_context 注入，dict 形态避免分层反向依赖）
    memory_summary: dict[str, Any] | None
    # 近期轮次的公司代码（最近优先，load_context 注入）
    recent_company_codes: list[str]
    provenance_report: Any | None
    cross_validation: CrossValidationResult | None = None
    risk_output: Any | None = None
    # Phase D #2: 深度数值冲突检测结果（list[dict]，CV-NUM-01/02）
    numerical_conflicts: list[dict] | None = None
