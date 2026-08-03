"""Agent State — V12 §7.3.

TypedDict + Annotated reducer pattern for LangGraph StateGraph.
"""

from datetime import date
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import add_messages
from pydantic import BaseModel, Field


# ── V12 §7.3 模型 ──────────────────────────────────────────


class CompanyRef(BaseModel):
    """公司引用 — V12 §7.3."""

    entity_id: str
    wind_code: str
    sec_name: str
    exchange: str
    industry_l1: str | None = None


class ExecutionPlan(BaseModel):
    """执行计划 — V12 §7.3."""

    intent: str = ""
    requested_modules: list[str] = Field(default_factory=list)
    cross_checks: list[str] = Field(default_factory=list)
    as_of: date | None = None
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


class EvidenceRef(BaseModel):
    """证据引用 — V12 §9.1 + Phase C 全局追溯字段."""

    evidence_id: str
    source_type: str = ""
    source_record_id: str = ""
    field_path: str | None = None
    period: str | None = None
    value: str | None = None
    source_title: str = ""
    # Phase C: 全局追溯字段
    turn_id: str = ""
    trace_id: str = ""
    company_code: str = ""
    module: str = ""
    source_table: str | None = None
    unit: str | None = None
    statement_scope: str | None = None
    source_uri: str | None = None
    source_excerpt: str | None = None
    dataset_version: str = ""
    retrieved_at: str = ""


class Claim(BaseModel):
    """结论声明 — V12 §9.2 + Phase C 全局追溯字段."""

    claim_id: str
    text: str
    claim_type: str = ""
    severity: str = "unknown"
    confidence: float | None = None
    rule_id: str | None = None
    rule_version: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    verification_status: str = "pending"
    limitations: list[str] = Field(default_factory=list)
    # Phase C: 全局追溯字段
    turn_id: str = ""
    trace_id: str = ""
    company_code: str = ""
    module: str = ""
    generated_at: str = ""


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
    is_anaphora: bool = Field(
        False, description="当前 query 是否包含指代词（它/上次那家/该公司等）"
    )
    previous_companies: list[str] = Field(
        default_factory=list, description="历史轮次中涉及的股票简称列表"
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
    warnings: list[str] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)


class EquityResult(BaseModel):
    graph: dict = Field(default_factory=dict)
    chains: list[dict] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)


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
    messages: Annotated[list[Any], add_messages]
    company: CompanyRef | None
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
    memory_context: MemoryContext | None
    provenance_report: Any | None
    cross_validation: CrossValidationResult | None = None
    risk_output: Any | None = None
