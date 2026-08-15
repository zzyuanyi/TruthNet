"""API v1 对话 Schema — V12 baseline."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.api.v1.schemas.events import ImpactConclusion

_SESSION_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$"


class ChatContextV1(BaseModel):
    """Optional explicit analysis context."""

    company_code: str | None = Field(default=None, min_length=1, max_length=32)
    fiscal_year: int | None = Field(default=None, ge=1990, le=2100)


class ChatRequestV1(BaseModel):
    """POST /api/v1/chat 请求体 — V12."""

    question: str = Field(..., min_length=1, max_length=2000, description="用户问题")
    session_id: str | None = Field(
        None,
        max_length=64,
        pattern=_SESSION_ID_PATTERN,
        description="会话 ID，用于多轮对话",
    )
    context: ChatContextV1 | None = Field(None, description="附加上下文信息")

    @field_validator("question")
    @classmethod
    def _strip_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("question 不能为空")
        return value


class CompanyCandidateV1(BaseModel):
    """Company option returned when an input matches multiple entities."""

    entity_id: str
    wind_code: str
    sec_name: str
    exchange: str = ""
    industry_l1: str | None = None

    @classmethod
    def from_company(cls, company) -> "CompanyCandidateV1":
        source = company if isinstance(company, dict) else company.model_dump()
        return cls(**source)


class ChatEvidenceV1(BaseModel):
    """chat 响应证据项 — 旧契约 source/field/value 兼容 + V12 canonical 字段.

    此前 evidence 为无类型约束的 list[dict]（{source, field, value}），
    与 ORM（source_type/field_path）和 Lookup 端点形状脱节。
    """

    # 旧契约兼容字段（前端已消费，不删除）
    source: str = ""
    field: str = ""
    value: str = ""
    # V12 canonical 字段（与 EvidenceRef / ORM 列名一致）
    evidence_id: str = ""
    source_type: str = ""
    source_record_id: str = ""
    source_title: str = ""
    field_path: str | None = None
    period: str | None = None
    unit: str | None = None
    source_uri: str | None = None
    dataset_version: str = ""

    @classmethod
    def from_evidence(cls, ev) -> "ChatEvidenceV1":
        """从 EvidenceRef（模型对象）或 ORM dict 构造.

        chat 响应使用；provenance Lookup 端点返回完整 ORM 行（字段对齐，
        不经此 DTO 截断）。输入缺字段时输出空值。
        """
        src = ev if isinstance(ev, dict) else ev.model_dump()
        raw_value = src.get("value")
        return cls(
            # source 优先可读标题（如"2023年报 利润表"），而非机器值 financial_statement
            source=src.get("source_title") or src.get("source_type", ""),
            field=src.get("field_path", "") or "",
            value="" if raw_value is None else str(raw_value),
            evidence_id=src.get("evidence_id", ""),
            source_type=src.get("source_type", ""),
            source_record_id=src.get("source_record_id", ""),
            source_title=src.get("source_title", ""),
            field_path=src.get("field_path"),
            period=src.get("period"),
            unit=src.get("unit"),
            source_uri=src.get("source_uri"),
            dataset_version=src.get("dataset_version", ""),
        )


class ClaimV1(BaseModel):
    """chat 响应结论声明项 — API 公共投影（非完整 domain/ORM 字段集）.

    透出结论声明的可展示字段；limitations 对 partial/证据不足/降级场景重要。
    """

    claim_id: str = ""
    text: str = ""
    claim_type: str = ""
    severity: str = "unknown"
    confidence: float | None = None
    rule_id: str | None = None
    rule_version: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    verification_status: str = "pending"
    limitations: list[str] = Field(default_factory=list)

    @classmethod
    def from_claim(cls, c) -> "ClaimV1":
        """从 domain Claim（模型对象或 dict）构造."""
        src = c if isinstance(c, dict) else c.model_dump()
        return cls(
            claim_id=src.get("claim_id", ""),
            text=src.get("text", ""),
            claim_type=src.get("claim_type", ""),
            severity=src.get("severity", "unknown"),
            confidence=src.get("confidence"),
            rule_id=src.get("rule_id"),
            rule_version=src.get("rule_version"),
            evidence_ids=src.get("evidence_ids") or [],
            verification_status=src.get("verification_status", "pending"),
            limitations=src.get("limitations") or [],
        )


# 模块状态合法值（模块级常量：pydantic 会私有化下划线前缀类属性，不能用类属性）
_MODULE_STATUS_STATES = frozenset(
    {"pending", "running", "success", "partial", "failed", "skipped", "cancelled"}
)


class ModuleStatusV1(BaseModel):
    """chat 响应模块状态 — typed（非字符串），与 Agent ModuleStatus 对齐.

    含 error_code/recoverable/duration_ms，供前端错误 UI 与评测指标
    （partial 比例 / 模块超时率）消费。
    """

    state: Literal[
        "pending", "running", "success", "partial", "failed", "skipped", "cancelled"
    ] = "pending"
    error_code: str | None = None
    recoverable: bool = False
    duration_ms: int | None = None

    @classmethod
    def from_status(cls, v) -> "ModuleStatusV1":
        """兼容 ModuleStatus 对象 / dict / 字符串 / None 四种输入.

        未知 state 值或未知对象一律回退 pending——响应组装绝不再失败。
        """
        if v is None:
            return cls()
        if isinstance(v, str):
            return cls(state=v if v in _MODULE_STATUS_STATES else "pending")
        if isinstance(v, BaseModel):
            return cls.from_status(v.model_dump())
        if isinstance(v, dict):
            raw = v.get("state", "pending")
            return cls(
                state=raw if raw in _MODULE_STATUS_STATES else "pending",
                error_code=v.get("error_code"),
                recoverable=bool(v.get("recoverable", False)),
                duration_ms=v.get("duration_ms"),
            )
        return cls()


class ChatDataV1(BaseModel):
    """对话响应核心数据 — V12."""

    answer: str = Field(..., description="Markdown 格式的主回答")
    session_id: str = Field(default="", description="本次实际使用的会话 ID")
    company_candidates: list[CompanyCandidateV1] = Field(
        default_factory=list, description="公司名称存在歧义时返回的候选列表"
    )
    # v3.1 P1-5：REST 最小只读契约——mention 分组（多 mention 场景旧字段
    # company_candidates 为空时，新字段提供完整分组；不提供 REST confirm）
    company_mentions: list[dict] = Field(
        default_factory=list, description="mention 分组（含各 mention 候选与状态）"
    )
    needs_confirmation: bool = Field(
        default=False, description="存在待确认 mention（需使用支持确认的 WS 客户端）"
    )
    # v3.3.1 §8.2：只读追加字段（旧客户端忽略，不得删除既有字段）
    segmentation_alternatives: list[dict] = Field(
        default_factory=list, description="分段歧义方案（按父 mention 分组，审计用）"
    )
    entity_resolution_issues: list[dict] = Field(
        default_factory=list,
        description="实体解析流程 issue（预算耗尽/实体超限/分段歧义）",
    )
    evidence: list[ChatEvidenceV1] = Field(default_factory=list, description="证据列表")
    graph: dict = Field(default_factory=dict, description="图谱数据")
    timeline: list[dict] = Field(default_factory=list, description="事件时间线")
    risk_score: dict = Field(default_factory=dict, description="风险评分")
    warnings: list[str] = Field(default_factory=list, description="财务预警点")
    missing_modules: list[str] = Field(default_factory=list, description="暂缺模块列表")
    trace_id: str = Field(..., description="追踪 ID")
    follow_ups: list[str] = Field(default_factory=list, description="追问建议")
    intent: str = Field(
        default="",
        description="回答意图：chitchat/guide/research/unsupported/simple_query/diagnose",
    )
    claims: list[ClaimV1] = Field(
        default_factory=list, description="结论声明列表（结构化问答）"
    )
    module_status: dict[str, ModuleStatusV1] = Field(
        default_factory=dict,
        description="各模块状态（typed：state/error_code/recoverable/duration_ms）",
    )
    risk_level: str = Field(
        default="unknown",
        description="风险等级：red/orange/yellow/green/unknown",
    )
    pattern_matches: list[dict] = Field(
        default_factory=list,
        description=(
            "造假模式匹配结果（含 phase/alternative_explanation/"
            "regulatory_hint 三要素，Phase D #16）"
        ),
    )
    equity_chains: list[dict] = Field(
        default_factory=list,
        description=(
            "正式股权链路载荷（含 risk_label/risk_level/evidence_ids/"
            "merge_explanation，Phase D #12）"
        ),
    )
    supporting_evidence: list[ChatEvidenceV1] = Field(
        default_factory=list,
        description=(
            "#13 可展示证据子集：叶子 Claim（排除综合 risk）引用证据的有序去重"
            "集合；前端默认展示，另保留 evidence 全量入口"
        ),
    )
    requested_period_text: str = Field(
        default="",
        description=(
            "用户请求中的期次原文（如 2025年报）；与 meta.data_as_of"
            "（实际数据截止日）分离，避免把请求期次当作实际数据期"
        ),
    )
    # v3.3.4 方案 §3.3/§6.1：轻量整体概览只读追加字段（旧客户端忽略）
    comparison_mode: str = Field(
        default="",
        description="轻量比较模式：indicator/overview/risk/company_fact；空=非比较",
    )
    overview_rows: list[dict] = Field(
        default_factory=list,
        description="overview 模式的逐指标概览行（metric_id/label/status/unit/period/values/difference/conclusion/warnings）",
    )
    # v3.3.4 Preview First（方案 §3.3/§6.1）：请求范围与结构化下一步
    requested_scope: str = Field(
        default="",
        description=(
            "比较请求的用户原始范围：indicator/overview/risk/company_fact/"
            "full/industry；空=非比较请求"
        ),
    )
    next_steps: list[dict] = Field(
        default_factory=list,
        description=(
            "结构化下一步导航（kind/label/target/participant_codes/params），"
            "如 open_full_comparison/open_industry_comparison/"
            "open_multi_company_comparison/choose_comparison_pair"
        ),
    )
    # B2 第二阶段（方案 §4.1）：舆情影响结论（与 REST /events 同构）；
    # 事件模块未执行/无结果 → 空列表。impact_warnings 为影响分析降级提示。
    impact_conclusions: list[ImpactConclusion] = Field(
        default_factory=list,
        description="舆情影响结论（B2 第二阶段，事件模块生成；无则空列表）",
    )
    impact_warnings: list[str] = Field(
        default_factory=list,
        description="舆情影响分析降级提示（LLM 失败/超时/无事实）",
    )
