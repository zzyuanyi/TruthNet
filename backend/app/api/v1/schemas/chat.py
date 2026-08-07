"""API v1 对话 Schema — V12 baseline."""

from typing import Literal

from pydantic import BaseModel, Field


class ChatRequestV1(BaseModel):
    """POST /api/v1/chat 请求体 — V12."""

    question: str = Field(..., min_length=1, description="用户问题")
    session_id: str | None = Field(None, description="会话 ID，用于多轮对话")
    context: dict | None = Field(None, description="附加上下文信息")


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
    evidence: list[ChatEvidenceV1] = Field(default_factory=list, description="证据列表")
    graph: dict = Field(default_factory=dict, description="图谱数据")
    timeline: list[dict] = Field(default_factory=list, description="事件时间线")
    risk_score: dict = Field(default_factory=dict, description="风险评分")
    warnings: list[str] = Field(default_factory=list, description="财务预警点")
    missing_modules: list[str] = Field(default_factory=list, description="暂缺模块列表")
    trace_id: str = Field(..., description="追踪 ID")
    follow_ups: list[str] = Field(default_factory=list, description="追问建议")
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
