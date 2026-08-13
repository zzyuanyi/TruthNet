"""SQLAlchemy ORM 模型 — V12 baseline.

7 张核心表字段严格对齐 TruthNet_综合设计方案_V12.md §10.3–10.7。
7 张派生表对齐 §10.8（表名），字段定义基于设计上下文。
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类."""

    pass


# ============================================================================
# Mixin: 公共系统字段 (§10.2)
# ============================================================================


class SystemFieldsMixin:
    """业务表公共系统字段（含自增 id 主键）.

    适用于 balance_sheet / income_statement / cash_flow /
    top_shareholders / announcements / research_reports。
    """

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_record_id: Mapped[str | None] = mapped_column(
        String(256), nullable=True, comment="原始记录 ID"
    )
    source_file: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="来源文件名"
    )
    source_row: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="来源行号"
    )
    source_type: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="来源类型"
    )
    dataset_version: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="数据集版本"
    )
    revision_no: Mapped[int] = mapped_column(Integer, default=1, comment="修订版本号")
    is_latest: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否最新修订"
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, comment="入库时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        comment="最后更新时间",
    )
    quality_flags: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="数据质量标记"
    )
    checksum: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="记录校验和 (SHA-256)"
    )


# ============================================================================
# 核心表 1: companies (§10.3)
# ============================================================================


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"}

    # ――― 业务字段 ―――
    entity_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: f"ent_{uuid.uuid4().hex[:12]}",
        comment="内部稳定实体 ID（主键）",
    )
    wind_code: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        nullable=False,
        index=True,
        comment="Wind 代码，如 600519.SH",
    )
    sec_name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="证券简称"
    )
    aliases: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="曾用名和别名"
    )
    exchange_code: Mapped[str | None] = mapped_column(
        String(16), nullable=True, comment="交易所代码: XSHG/XSHE"
    )
    industry_l1: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="申万一级行业"
    )
    industry_l2: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="申万二级行业"
    )
    sw_indu_code: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="申万行业代码"
    )
    comp_type_code: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="公司类型"
    )
    listing_date: Mapped[datetime | None] = mapped_column(
        Date, nullable=True, comment="上市日期"
    )
    industry_source: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="行业分类来源"
    )
    industry_as_of: Mapped[datetime | None] = mapped_column(
        Date, nullable=True, comment="行业分类有效日期"
    )

    # ――― 系统字段（不使用 Mixin，因为 entity_id 替代了 id 作为主键）―――
    source_record_id: Mapped[str | None] = mapped_column(
        String(256), nullable=True, comment="原始记录 ID"
    )
    source_file: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="来源文件名"
    )
    source_row: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="来源行号"
    )
    source_type: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="来源类型"
    )
    dataset_version: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="数据集版本"
    )
    revision_no: Mapped[int] = mapped_column(Integer, default=1, comment="修订版本号")
    is_latest: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否最新修订"
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, comment="入库时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        comment="最后更新时间",
    )
    quality_flags: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="数据质量标记"
    )
    checksum: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="记录校验和 (SHA-256)"
    )

    def __repr__(self) -> str:
        return f"<Company {self.wind_code} {self.sec_name}>"


# ============================================================================
# 核心表 2: balance_sheet (§10.4)
# ============================================================================


class BalanceSheet(Base, SystemFieldsMixin):
    __tablename__ = "balance_sheet"
    __table_args__ = (
        UniqueConstraint(
            "wind_code",
            "report_period",
            "statement_type",
            "ann_dt",
            "revision_no",
            name="uq_bs_report",
        ),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    wind_code: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, comment="Wind 代码"
    )
    report_period: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True, comment="报告期 (YYYY-MM-DD)"
    )
    statement_type: Mapped[str] = mapped_column(
        String(32),
        default="408006000",
        comment="报表类型代码: 408006000=母公司报表(项目固定分析口径), 408001000=合并报表(数据字典保留, R1-R7 不使用) (详见 domain/finance/statement_type.py)",
    )
    ann_dt: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="公告日期 (YYYY-MM-DD)"
    )
    monetary_cap: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="货币资金"
    )
    acct_rcv: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="应收账款"
    )
    oth_rcv: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="其他应收款"
    )
    inventories: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="存货"
    )
    tot_cur_assets: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="流动资产合计"
    )
    fix_assets: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="固定资产"
    )
    goodwill: Mapped[float | None] = mapped_column(Float, nullable=True, comment="商誉")
    tot_assets: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="资产总计"
    )
    st_borrow: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="短期借款"
    )
    lt_borrow: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="长期借款"
    )
    acct_payable: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="应付账款"
    )
    tot_cur_liab: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="流动负债合计"
    )
    tot_liab: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="负债合计"
    )
    tot_shrhldr_eqy_incl_min_int: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="所有者权益合计（含少数股东权益）"
    )

    def __repr__(self) -> str:
        return f"<BS {self.wind_code} @ {self.report_period}>"


# ============================================================================
# 核心表 3: income_statement (§10.4)
# ============================================================================


class IncomeStatement(Base, SystemFieldsMixin):
    __tablename__ = "income_statement"
    __table_args__ = (
        UniqueConstraint(
            "wind_code",
            "report_period",
            "statement_type",
            "ann_dt",
            "revision_no",
            name="uq_is_report",
        ),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    wind_code: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, comment="Wind 代码"
    )
    report_period: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True, comment="报告期"
    )
    statement_type: Mapped[str] = mapped_column(
        String(32),
        default="408006000",
        comment="报表类型代码: 408006000=母公司报表(项目固定分析口径), 408001000=合并报表(数据字典保留, R1-R7 不使用)",
    )
    ann_dt: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="公告日期"
    )
    oper_rev: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="营业收入"
    )
    tot_oper_rev: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="营业总收入"
    )
    less_oper_cost: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="营业成本"
    )
    less_selling_dist_exp: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="销售费用"
    )
    less_gerl_admin_exp: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="管理费用"
    )
    less_fin_exp: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="财务费用"
    )
    oper_profit: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="营业利润"
    )
    tot_profit: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="利润总额"
    )
    net_profit_excl_min_int_inc: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="归母净利润（归属于母公司股东的净利润）"
    )
    net_profit_after_ded_nr_lp: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="扣非净利润（扣除非经常性损益后的净利润）"
    )

    def __repr__(self) -> str:
        return f"<IS {self.wind_code} @ {self.report_period}>"


# ============================================================================
# 核心表 4: cash_flow (§10.4)
# ============================================================================


class CashFlow(Base, SystemFieldsMixin):
    __tablename__ = "cash_flow"
    __table_args__ = (
        UniqueConstraint(
            "wind_code",
            "report_period",
            "statement_type",
            "ann_dt",
            "revision_no",
            name="uq_cf_report",
        ),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    wind_code: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, comment="Wind 代码"
    )
    report_period: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True, comment="报告期"
    )
    statement_type: Mapped[str] = mapped_column(
        String(32),
        default="408006000",
        comment="报表类型代码: 408006000=母公司报表(项目固定分析口径), 408001000=合并报表(数据字典保留, R1-R7 不使用)",
    )
    ann_dt: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="公告日期"
    )
    net_cash_flows_oper_act: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="经营活动现金流量净额"
    )
    net_cash_flows_inv_act: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="投资活动现金流量净额"
    )
    net_cash_flows_fnc_act: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="筹资活动现金流量净额"
    )
    net_incr_cash_cash_equ: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="现金及等价物净增加额"
    )
    free_cash_flow: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="自由现金流"
    )

    def __repr__(self) -> str:
        return f"<CF {self.wind_code} @ {self.report_period}>"


# ============================================================================
# 核心表 5: top_shareholders (§10.5)
# ============================================================================


class TopShareholder(Base, SystemFieldsMixin):
    __tablename__ = "top_shareholders"
    __table_args__ = (
        UniqueConstraint(
            "source_record_id", name="uq_top_shareholders_source_record_id"
        ),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    wind_code: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, comment="Wind 代码"
    )
    ann_dt: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="公告日期"
    )
    s_holder_enddate: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="股东持股截止日期"
    )
    s_holder_name: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="股东名称"
    )
    s_holder_aname: Mapped[str | None] = mapped_column(
        String(256), nullable=True, comment="股东别名（用于实体对齐）"
    )
    s_holder_pct: Mapped[float | None] = mapped_column(
        Numeric(10, 4), nullable=True, comment="持股比例 (%) — 精度 10 位，4 位小数"
    )
    s_holder_quantity: Mapped[float | None] = mapped_column(
        Numeric(20, 2), nullable=True, comment="持股数量"
    )
    s_holder_holdercategory: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="股东类别"
    )
    s_holder_sequence: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="股东序号"
    )
    report_period: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="报告期"
    )
    holder_entity_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="股东实体 ID（与 companies.entity_id 对齐）",
    )
    entity_match_confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="实体对齐置信度 (0-1)"
    )

    def __repr__(self) -> str:
        return f"<TopSH {self.s_holder_name} → {self.wind_code}>"


# ============================================================================
# 核心表 6: announcements (§10.6)
# ============================================================================


class Announcement(Base, SystemFieldsMixin):
    __tablename__ = "announcements"
    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"}

    object_id: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, comment="公告源 ID"
    )
    wind_code: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, comment="Wind 代码"
    )
    ann_dt: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="公告日期"
    )
    n_info_title: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="公告标题"
    )
    n_info_fcode: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="公告类型代码（共 33 类）"
    )
    sentiment: Mapped[str | None] = mapped_column(
        String(16), nullable=True, comment="情感: positive/negative/neutral"
    )
    sentiment_method: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="情感分析方法"
    )
    source_uri: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, comment="来源 URI"
    )
    content_hash: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="内容哈希 (SHA-256)"
    )

    def __repr__(self) -> str:
        return f"<Announcement {self.ann_dt} {self.n_info_title[:40]}>"


# ============================================================================
# 核心表 7: research_reports (§10.7)
# ============================================================================


class ResearchReport(Base, SystemFieldsMixin):
    __tablename__ = "research_reports"
    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"}

    report_id: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, comment="研报唯一 ID"
    )
    wind_code: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, comment="Wind 代码"
    )
    sec_code: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="证券代码"
    )
    exchange_code: Mapped[str | None] = mapped_column(
        String(16), nullable=True, comment="交易所代码"
    )
    sec_name: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="证券简称"
    )
    org_name: Mapped[str | None] = mapped_column(
        String(256), nullable=True, comment="研究机构"
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False, comment="研报标题")
    publish_date: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="发布日期"
    )
    abstract: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="摘要/核心观点"
    )
    rating_org: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="原始评级"
    )
    rating_change: Mapped[str | None] = mapped_column(
        String(16), nullable=True, comment="评级变化: up/down/maintain"
    )
    industry_l1: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="申万一级行业"
    )
    sw_indu_code: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="申万行业代码"
    )
    source_uri: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, comment="来源 URI"
    )
    content_hash: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="内容哈希"
    )

    def __repr__(self) -> str:
        return f"<Report {self.report_id} {self.title[:40]}>"


# ============================================================================
# 派生表 8: conversation_sessions — 对话会话 (§10.8)
# ============================================================================


class ConversationSession(Base):
    __tablename__ = "conversation_sessions"
    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"}

    session_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: f"ses_{uuid.uuid4().hex[:12]}",
        comment="会话 ID",
    )
    user_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="用户 ID"
    )
    title: Mapped[str | None] = mapped_column(
        String(256), nullable=True, comment="会话标题"
    )
    status: Mapped[str] = mapped_column(
        String(16), default="active", comment="状态: active/archived/closed"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        comment="最后更新时间",
    )
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSON, nullable=True, comment="附加元数据"
    )

    def __repr__(self) -> str:
        return f"<Session {self.session_id}>"


# ============================================================================
# 派生表 9: conversation_turns — 对话轮次 (§10.8)
# ============================================================================


class ConversationTurn(Base):
    __tablename__ = "conversation_turns"
    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"}

    turn_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: f"turn_{uuid.uuid4().hex[:12]}",
        comment="轮次 ID",
    )
    session_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("conversation_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属会话 ID",
    )
    turn_index: Mapped[int] = mapped_column(Integer, default=0, comment="轮次序号")
    question: Mapped[str] = mapped_column(Text, nullable=False, comment="用户问题")
    answer: Mapped[str | None] = mapped_column(Text, nullable=True, comment="系统回答")
    company_code: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="关联公司代码"
    )
    summary: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="轮次摘要 (用于记忆)"
    )
    trace_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="追踪 ID"
    )
    module_status: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="各模块执行状态"
    )
    panel_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="面板摘要 {risk_level, triggered_rules, key_metrics, follow_ups}（v7）",
    )
    response_meta: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="回答元数据 {intent, follow_ups, supporting_evidence_ids, requested_period_text}",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, comment="创建时间"
    )

    def __repr__(self) -> str:
        return f"<Turn {self.turn_id} Q{self.turn_index}>"


# ============================================================================
# 派生表 10: rule_definitions — 规则定义 (§10.8)
# ============================================================================


class RuleDefinition(Base):
    __tablename__ = "rule_definitions"
    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"}

    rule_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="规则唯一 ID"
    )
    rule_name: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="规则名称"
    )
    category: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="规则类别 (如 revenue_quality)"
    )
    description: Mapped[str] = mapped_column(Text, nullable=False, comment="规则描述")
    formula: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="计算公式/逻辑描述"
    )
    threshold: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="阈值配置 (JSON)"
    )
    severity: Mapped[str] = mapped_column(
        String(16), default="medium", comment="默认严重程度: low/medium/high/critical"
    )
    version: Mapped[str] = mapped_column(
        String(32), default="1.0.0", comment="规则版本"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    def __repr__(self) -> str:
        return f"<Rule {self.rule_id} {self.rule_name}>"


# ============================================================================
# 派生表 11: rule_evaluations — 规则评估记录 (§10.8)
# ============================================================================


class RuleEvaluation(Base):
    __tablename__ = "rule_evaluations"
    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("rule_definitions.rule_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="规则 ID",
    )
    wind_code: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, comment="评估目标公司"
    )
    report_period: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="评估报告期"
    )
    result: Mapped[str | None] = mapped_column(
        String(16), nullable=True, comment="结果: triggered/normal/insufficient_data"
    )
    score: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="评分 (0-1)"
    )
    detail: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="评估详情 (JSON)"
    )
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, comment="评估时间"
    )
    rule_version: Mapped[str] = mapped_column(String(32), comment="使用的规则版本")

    def __repr__(self) -> str:
        return f"<RuleEval {self.rule_id} → {self.wind_code} @ {self.report_period}>"


# ============================================================================
# 派生表 12: evidence_refs — 证据引用 (§10.8)
# ============================================================================


class EvidenceRef(Base):
    __tablename__ = "evidence_refs"
    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"}

    evidence_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="证据唯一 ID"
    )
    source_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="证据类型: financial_statement/ownership_record/news_article/regulation",
    )
    source_record_id: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="来源记录 ID"
    )
    company_code: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="公司代码"
    )
    field_path: Mapped[str | None] = mapped_column(
        String(256), nullable=True, comment="字段路径"
    )
    period: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="数据期间"
    )
    value: Mapped[str | None] = mapped_column(
        String(256), nullable=True, comment="字段值"
    )
    unit: Mapped[str | None] = mapped_column(String(16), nullable=True, comment="单位")
    statement_scope: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="报表口径: parent_company/consolidated"
    )
    source_title: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="来源标题"
    )
    source_uri: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, comment="来源 URI"
    )
    source_excerpt: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="来源摘录"
    )
    retrieval_score: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="检索相关性分数"
    )
    dataset_version: Mapped[str] = mapped_column(
        String(64), default="mock-v12", comment="数据集版本"
    )
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, comment="检索时间"
    )
    # Phase C: 全局追溯字段
    turn_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True, comment="关联轮次 ID"
    )
    trace_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True, comment="追踪 ID"
    )
    module: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="来源模块: finance/equity/events"
    )
    source_table: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="来源表名"
    )

    def __repr__(self) -> str:
        return f"<Evidence {self.evidence_id} [{self.source_type}]>"


# ============================================================================
# 派生表 13: claims — 结论声明 (§10.8)
# ============================================================================


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"}

    claim_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="声明唯一 ID"
    )
    turn_id: Mapped[str | None] = mapped_column(
        String(64), index=True, comment="关联轮次 ID"
    )
    text: Mapped[str] = mapped_column(Text, nullable=False, comment="声明内容")
    claim_type: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="声明类型: financial/equity/event/fact/analysis",
    )
    severity: Mapped[str] = mapped_column(
        String(16), default="low", comment="严重程度: none/low/medium/high/critical"
    )
    confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="置信度 (0-1)"
    )
    rule_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="关联规则 ID"
    )
    rule_version: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="规则版本"
    )
    verification_status: Mapped[str] = mapped_column(
        String(16), default="pending", comment="验证状态: pending/verified/refuted"
    )
    limitations: Mapped[list | None] = mapped_column(
        JSON, nullable=True, comment="局限性说明"
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, comment="生成时间"
    )
    # Phase C: 全局追溯字段
    trace_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True, comment="追踪 ID"
    )
    company_code: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="公司代码"
    )
    module: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="来源模块: finance/equity/events"
    )

    def __repr__(self) -> str:
        return f"<Claim {self.claim_id} [{self.confidence}]>"


# ============================================================================
# Phase C 派生表 15: claim_evidence_links — Claim↔Evidence 关联 (§6.4)
# ============================================================================


class ClaimEvidenceLink(Base):
    __tablename__ = "claim_evidence_links"
    __table_args__ = (
        UniqueConstraint(
            "claim_id",
            "evidence_id",
            "relation_type",
            name="uq_claim_evidence_link",
        ),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("claims.claim_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Claim ID",
    )
    evidence_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("evidence_refs.evidence_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Evidence ID",
    )
    relation_type: Mapped[str] = mapped_column(
        String(16),
        default="supports",
        comment="关系类型: supports/contradicts/context",
    )
    sequence_no: Mapped[int] = mapped_column(Integer, default=0, comment="顺序号")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, comment="创建时间"
    )

    def __repr__(self) -> str:
        return f"<Link {self.claim_id} → {self.evidence_id}>"


# ============================================================================
# Phase C 派生表 16: event_clusters — 事件簇交接 (§5.5)
# ============================================================================


class EventCluster(Base):
    __tablename__ = "event_clusters"
    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"}

    event_cluster_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="事件簇唯一 ID"
    )
    entity_id: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="公司 entity_id"
    )
    wind_code: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, comment="Wind 代码"
    )
    topic: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="事件簇主题"
    )
    summary: Mapped[str] = mapped_column(Text, default="", comment="摘要")
    start_date: Mapped[date] = mapped_column(Date, nullable=False, comment="起始日期")
    end_date: Mapped[date] = mapped_column(Date, nullable=False, comment="结束日期")
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, comment="事件数")
    sentiment: Mapped[str] = mapped_column(String(16), nullable=False, comment="情感")
    sentiment_score: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="情感得分 [-1,1]"
    )
    cluster_method: Mapped[str] = mapped_column(
        String(64), default="", comment="聚类方法"
    )
    cluster_version: Mapped[str] = mapped_column(
        String(32), default="", comment="聚类版本"
    )
    dataset_version: Mapped[str] = mapped_column(
        String(64), default="", comment="数据集版本"
    )
    quality_flags: Mapped[list | None] = mapped_column(
        JSON, nullable=True, comment="质量标记"
    )
    evidence_ids: Mapped[list | None] = mapped_column(
        JSON, nullable=True, comment="关联 Evidence ID 列表"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, comment="创建时间"
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="更新时间"
    )

    def __repr__(self) -> str:
        return f"<EventCluster {self.event_cluster_id} [{self.topic[:20]}]>"


class EventClusterSource(Base):
    __tablename__ = "event_cluster_sources"
    __table_args__ = (
        UniqueConstraint(
            "event_cluster_id",
            "source_record_id",
            name="uq_event_cluster_source",
        ),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_cluster_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("event_clusters.event_cluster_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="事件簇 ID",
    )
    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="来源类型"
    )
    source_record_id: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="来源记录 ID"
    )
    evidence_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True, comment="关联 Evidence ID"
    )
    source_title: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="来源标题"
    )
    source_uri: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, comment="来源 URI"
    )
    published_at: Mapped[date | None] = mapped_column(
        Date, nullable=True, comment="发布日期"
    )
    content_hash: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="内容哈希"
    )
    sequence_no: Mapped[int] = mapped_column(Integer, default=0, comment="顺序号")

    def __repr__(self) -> str:
        return f"<ClusterSource {self.event_cluster_id} {self.source_record_id}>"


# ============================================================================
# 派生表 14: risk_assessments — 风险评估 (§10.8)
# ============================================================================


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"
    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        default=lambda: f"risk_{uuid.uuid4().hex[:12]}",
        comment="评估唯一 ID",
    )
    wind_code: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, comment="Wind 代码"
    )
    overall_score: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="综合风险 0-1"
    )
    financial_score: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="财务风险 0-1"
    )
    ownership_score: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="股权风险 0-1"
    )
    sentiment_score: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="舆情风险 0-1"
    )
    level: Mapped[str] = mapped_column(
        String(16), default="low", comment="风险等级: none/low/medium/high/critical"
    )
    risk_factors: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="风险因子详情 (JSON)"
    )
    rule_version: Mapped[str] = mapped_column(String(32), comment="使用的规则版本")
    dataset_version: Mapped[str] = mapped_column(String(64), comment="使用的数据版本")
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, comment="评估时间"
    )

    def __repr__(self) -> str:
        return f"<RiskAssessment {self.wind_code} [{self.level}]>"


# ============================================================================
# Phase C 派生表 17: industry_benchmarks — 行业分位基准（数据任务 3）
# ============================================================================


class IndustryBenchmark(Base):
    __tablename__ = "industry_benchmarks"
    __table_args__ = (
        UniqueConstraint(
            "industry_l1",
            "metric_id",
            "period",
            "statement_scope",
            "dataset_version",
            name="uq_industry_benchmark_key",
        ),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    benchmark_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="基准唯一 ID"
    )
    industry_l1: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="申万一级行业"
    )
    industry_l2: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="申万二级行业"
    )
    metric_id: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, comment="指标 ID"
    )
    rule_id: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="关联规则 R1-R7"
    )
    period: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True, comment="报告期 YYYYMMDD"
    )
    statement_scope: Mapped[str] = mapped_column(
        String(32), nullable=False, default="parent_company", comment="报表口径"
    )
    company_type: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, comment="公司类型代码 (1=非金融)"
    )
    sample_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="有效样本数"
    )
    mean_value: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="均值"
    )
    std_value: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="标准差"
    )
    min_value: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="最小值"
    )
    p05: Mapped[float | None] = mapped_column(Float, nullable=True, comment="5 分位")
    p25: Mapped[float | None] = mapped_column(Float, nullable=True, comment="25 分位")
    p50: Mapped[float | None] = mapped_column(Float, nullable=True, comment="中位数")
    p75: Mapped[float | None] = mapped_column(Float, nullable=True, comment="75 分位")
    p95: Mapped[float | None] = mapped_column(Float, nullable=True, comment="95 分位")
    max_value: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="最大值"
    )
    dataset_version: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="数据集版本"
    )
    rule_set_version: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="规则集版本"
    )
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, comment="计算时间"
    )

    def __repr__(self) -> str:
        return f"<IndustryBenchmark {self.industry_l1}/{self.metric_id}@{self.period}>"


# ============================================================================
# Phase C 派生表 18: rating_changes — 研报评级拐点（数据任务 5）
# ============================================================================


class RatingChange(Base):
    __tablename__ = "rating_changes"
    __table_args__ = (
        UniqueConstraint(
            "wind_code",
            "quarter",
            "institution",
            "report_id",
            name="uq_rating_change_key",
        ),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"},
    )

    rating_change_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="拐点唯一 ID"
    )
    wind_code: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, comment="Wind 代码"
    )
    quarter: Mapped[str] = mapped_column(
        String(8), nullable=False, index=True, comment="季度 YYYYQn"
    )
    institution: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="研究机构"
    )
    previous_rating: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="上次评级（原始）"
    )
    current_rating: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="本次评级（原始）"
    )
    direction: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="方向: down/up/keep"
    )
    report_id: Mapped[str] = mapped_column(
        String(128), nullable=True, comment="研报 ID"
    )
    published_at: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="发布日期 YYYY-MM-DD"
    )
    confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="解析置信度 [0,1]"
    )
    evidence_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="关联 Evidence ID"
    )
    dataset_version: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="数据集版本"
    )

    def __repr__(self) -> str:
        return f"<RatingChange {self.wind_code}/{self.quarter} {self.direction}>"


# ============================================================================
# Phase C 派生表 19: analysis_runs — 直接 REST 分析溯源（任务 16）
# ============================================================================


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"}

    run_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="分析运行唯一 ID"
    )
    trace_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="追踪 ID"
    )
    endpoint: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="端点标识"
    )
    company_codes: Mapped[list | None] = mapped_column(
        JSON, nullable=True, comment="分析公司列表"
    )
    period: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="报告期"
    )
    statement_scope: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="报表口径"
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="completed", comment="状态"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, comment="创建时间"
    )

    def __repr__(self) -> str:
        return f"<AnalysisRun {self.run_id} {self.endpoint}>"


# ============================================================================
# 派生表 16: report_jobs — PDF 报告任务（Phase D #8）
# ============================================================================


class ReportJob(Base):
    """PDF 报告长任务（Phase D #8，V12 §10.8：analysis_runs 不可复用）.

    状态机：queued → running → succeeded | failed | cancelled。
    幂等：idempotency_key 唯一约束，同一请求重试不重复建任务。
    """

    __tablename__ = "report_jobs"
    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"}

    report_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"report_{uuid.uuid4().hex[:12]}"
    )
    session_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True, comment="关联会话 ID"
    )
    company_code: Mapped[str | None] = mapped_column(
        String(32), nullable=True, index=True, comment="公司代码"
    )
    status: Mapped[str] = mapped_column(
        String(16),
        default="queued",
        index=True,
        comment="queued/running/succeeded/failed/cancelled",
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, comment="进度 0-100")
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True, unique=True, comment="幂等键（唯一约束）"
    )
    request_payload: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="创建请求载荷"
    )
    file_path: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="报告文件相对路径"
    )
    file_sha256: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="文件 SHA-256"
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0, comment="重试次数")
    error_code: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="错误码"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="错误信息"
    )
    trace_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="追踪 ID"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, comment="创建时间"
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="开始时间"
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="完成时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        comment="更新时间",
    )

    def __repr__(self) -> str:
        return f"<ReportJob {self.report_id} status={self.status}>"
