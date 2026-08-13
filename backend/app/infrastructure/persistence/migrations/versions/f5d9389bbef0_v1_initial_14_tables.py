"""v1_initial: 14 tables aligned with V12 §10.3–10.8

Revision ID: f5d9389bbef0
Revises:
Create Date: 2026-07-19 14:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f5d9389bbef0"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 核心表 1: companies (§10.3)
    # ------------------------------------------------------------------
    op.create_table(
        "companies",
        sa.Column(
            "entity_id", sa.String(64), nullable=False, comment="内部稳定实体 ID"
        ),
        sa.Column(
            "wind_code",
            sa.String(32),
            nullable=False,
            comment="Wind 代码，如 600519.SH",
        ),
        sa.Column("sec_name", sa.String(128), nullable=False, comment="证券简称"),
        sa.Column("aliases", sa.JSON(), nullable=True, comment="曾用名和别名"),
        sa.Column(
            "exchange_code",
            sa.String(16),
            nullable=True,
            comment="交易所代码: XSHG/XSHE",
        ),
        sa.Column("industry_l1", sa.String(64), nullable=True, comment="申万一级行业"),
        sa.Column("industry_l2", sa.String(64), nullable=True, comment="申万二级行业"),
        sa.Column("sw_indu_code", sa.String(32), nullable=True, comment="申万行业代码"),
        sa.Column(
            "comp_type_code", sa.SmallInteger(), nullable=True, comment="公司类型"
        ),
        sa.Column("listing_date", sa.Date(), nullable=True, comment="上市日期"),
        sa.Column(
            "industry_source", sa.String(64), nullable=True, comment="行业分类来源"
        ),
        sa.Column(
            "industry_as_of", sa.Date(), nullable=True, comment="行业分类有效日期"
        ),
        # 系统字段
        sa.Column(
            "source_record_id", sa.String(256), nullable=True, comment="原始记录 ID"
        ),
        sa.Column("source_file", sa.String(512), nullable=True, comment="来源文件名"),
        sa.Column("source_row", sa.Integer(), nullable=True, comment="来源行号"),
        sa.Column("source_type", sa.String(64), nullable=True, comment="来源类型"),
        sa.Column(
            "dataset_version", sa.String(64), nullable=True, comment="数据集版本"
        ),
        sa.Column("revision_no", sa.Integer(), nullable=False, comment="修订版本号"),
        sa.Column("is_latest", sa.Boolean(), nullable=False, comment="是否最新修订"),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="入库时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="最后更新时间",
        ),
        sa.Column("quality_flags", sa.JSON(), nullable=True, comment="数据质量标记"),
        sa.Column(
            "checksum", sa.String(128), nullable=True, comment="记录校验和 (SHA-256)"
        ),
        sa.PrimaryKeyConstraint("entity_id"),
    )
    op.create_index(
        op.f("ix_companies_wind_code"), "companies", ["wind_code"], unique=True
    )

    # ------------------------------------------------------------------
    # 核心表 2: balance_sheet (§10.4)
    # ------------------------------------------------------------------
    op.create_table(
        "balance_sheet",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("wind_code", sa.String(32), nullable=False, comment="Wind 代码"),
        sa.Column(
            "report_period",
            sa.String(10),
            nullable=False,
            comment="报告期 (YYYY-MM-DD)",
        ),
        sa.Column(
            "statement_type", sa.String(32), nullable=False, comment="报表类型代码"
        ),
        sa.Column(
            "ann_dt", sa.String(10), nullable=True, comment="公告日期 (YYYY-MM-DD)"
        ),
        sa.Column("monetary_cap", sa.Float(), nullable=True, comment="货币资金"),
        sa.Column("acct_rcv", sa.Float(), nullable=True, comment="应收账款"),
        sa.Column("oth_rcv", sa.Float(), nullable=True, comment="其他应收款"),
        sa.Column("inventories", sa.Float(), nullable=True, comment="存货"),
        sa.Column("tot_cur_assets", sa.Float(), nullable=True, comment="流动资产合计"),
        sa.Column("fix_assets", sa.Float(), nullable=True, comment="固定资产"),
        sa.Column("goodwill", sa.Float(), nullable=True, comment="商誉"),
        sa.Column("tot_assets", sa.Float(), nullable=True, comment="资产总计"),
        sa.Column("st_borrow", sa.Float(), nullable=True, comment="短期借款"),
        sa.Column("lt_borrow", sa.Float(), nullable=True, comment="长期借款"),
        sa.Column("acct_payable", sa.Float(), nullable=True, comment="应付账款"),
        sa.Column("tot_cur_liab", sa.Float(), nullable=True, comment="流动负债合计"),
        sa.Column("tot_liab", sa.Float(), nullable=True, comment="负债合计"),
        sa.Column(
            "tot_shrhldr_eqy_incl_min_int",
            sa.Float(),
            nullable=True,
            comment="所有者权益合计（含少数股东权益）",
        ),
        # 系统字段
        sa.Column(
            "source_record_id", sa.String(256), nullable=True, comment="原始记录 ID"
        ),
        sa.Column("source_file", sa.String(512), nullable=True, comment="来源文件名"),
        sa.Column("source_row", sa.Integer(), nullable=True, comment="来源行号"),
        sa.Column("source_type", sa.String(64), nullable=True, comment="来源类型"),
        sa.Column(
            "dataset_version", sa.String(64), nullable=True, comment="数据集版本"
        ),
        sa.Column("revision_no", sa.Integer(), nullable=False, comment="修订版本号"),
        sa.Column("is_latest", sa.Boolean(), nullable=False, comment="是否最新修订"),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="入库时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="最后更新时间",
        ),
        sa.Column("quality_flags", sa.JSON(), nullable=True, comment="数据质量标记"),
        sa.Column(
            "checksum", sa.String(128), nullable=True, comment="记录校验和 (SHA-256)"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "wind_code",
            "report_period",
            "statement_type",
            "ann_dt",
            "revision_no",
            name="uq_bs_report",
        ),
    )
    op.create_index(
        op.f("ix_balance_sheet_report_period"),
        "balance_sheet",
        ["report_period"],
        unique=False,
    )
    op.create_index(
        op.f("ix_balance_sheet_wind_code"), "balance_sheet", ["wind_code"], unique=False
    )

    # ------------------------------------------------------------------
    # 核心表 3: income_statement (§10.4)
    # ------------------------------------------------------------------
    op.create_table(
        "income_statement",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("wind_code", sa.String(32), nullable=False, comment="Wind 代码"),
        sa.Column("report_period", sa.String(10), nullable=False, comment="报告期"),
        sa.Column(
            "statement_type", sa.String(32), nullable=False, comment="报表类型代码"
        ),
        sa.Column("ann_dt", sa.String(10), nullable=True, comment="公告日期"),
        sa.Column("oper_rev", sa.Float(), nullable=True, comment="营业收入"),
        sa.Column("tot_oper_rev", sa.Float(), nullable=True, comment="营业总收入"),
        sa.Column("less_oper_cost", sa.Float(), nullable=True, comment="营业成本"),
        sa.Column(
            "less_selling_dist_exp", sa.Float(), nullable=True, comment="销售费用"
        ),
        sa.Column("less_gerl_admin_exp", sa.Float(), nullable=True, comment="管理费用"),
        sa.Column("less_fin_exp", sa.Float(), nullable=True, comment="财务费用"),
        sa.Column("oper_profit", sa.Float(), nullable=True, comment="营业利润"),
        sa.Column("tot_profit", sa.Float(), nullable=True, comment="利润总额"),
        sa.Column(
            "net_profit_excl_min_int_inc",
            sa.Float(),
            nullable=True,
            comment="净利润（不含少数股东损益）",
        ),
        sa.Column(
            "net_profit_after_ded_nr_lp",
            sa.Float(),
            nullable=True,
            comment="归母净利润",
        ),
        # 系统字段
        sa.Column(
            "source_record_id", sa.String(256), nullable=True, comment="原始记录 ID"
        ),
        sa.Column("source_file", sa.String(512), nullable=True, comment="来源文件名"),
        sa.Column("source_row", sa.Integer(), nullable=True, comment="来源行号"),
        sa.Column("source_type", sa.String(64), nullable=True, comment="来源类型"),
        sa.Column(
            "dataset_version", sa.String(64), nullable=True, comment="数据集版本"
        ),
        sa.Column("revision_no", sa.Integer(), nullable=False, comment="修订版本号"),
        sa.Column("is_latest", sa.Boolean(), nullable=False, comment="是否最新修订"),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="入库时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="最后更新时间",
        ),
        sa.Column("quality_flags", sa.JSON(), nullable=True, comment="数据质量标记"),
        sa.Column(
            "checksum", sa.String(128), nullable=True, comment="记录校验和 (SHA-256)"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "wind_code",
            "report_period",
            "statement_type",
            "ann_dt",
            "revision_no",
            name="uq_is_report",
        ),
    )
    op.create_index(
        op.f("ix_income_statement_report_period"),
        "income_statement",
        ["report_period"],
        unique=False,
    )
    op.create_index(
        op.f("ix_income_statement_wind_code"),
        "income_statement",
        ["wind_code"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # 核心表 4: cash_flow (§10.4)
    # ------------------------------------------------------------------
    op.create_table(
        "cash_flow",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("wind_code", sa.String(32), nullable=False, comment="Wind 代码"),
        sa.Column("report_period", sa.String(10), nullable=False, comment="报告期"),
        sa.Column(
            "statement_type", sa.String(32), nullable=False, comment="报表类型代码"
        ),
        sa.Column("ann_dt", sa.String(10), nullable=True, comment="公告日期"),
        sa.Column(
            "net_cash_flows_oper_act",
            sa.Float(),
            nullable=True,
            comment="经营活动现金流量净额",
        ),
        sa.Column(
            "net_cash_flows_inv_act",
            sa.Float(),
            nullable=True,
            comment="投资活动现金流量净额",
        ),
        sa.Column(
            "net_cash_flows_fnc_act",
            sa.Float(),
            nullable=True,
            comment="筹资活动现金流量净额",
        ),
        sa.Column(
            "net_incr_cash_cash_equ",
            sa.Float(),
            nullable=True,
            comment="现金及等价物净增加额",
        ),
        sa.Column("free_cash_flow", sa.Float(), nullable=True, comment="自由现金流"),
        # 系统字段
        sa.Column(
            "source_record_id", sa.String(256), nullable=True, comment="原始记录 ID"
        ),
        sa.Column("source_file", sa.String(512), nullable=True, comment="来源文件名"),
        sa.Column("source_row", sa.Integer(), nullable=True, comment="来源行号"),
        sa.Column("source_type", sa.String(64), nullable=True, comment="来源类型"),
        sa.Column(
            "dataset_version", sa.String(64), nullable=True, comment="数据集版本"
        ),
        sa.Column("revision_no", sa.Integer(), nullable=False, comment="修订版本号"),
        sa.Column("is_latest", sa.Boolean(), nullable=False, comment="是否最新修订"),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="入库时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="最后更新时间",
        ),
        sa.Column("quality_flags", sa.JSON(), nullable=True, comment="数据质量标记"),
        sa.Column(
            "checksum", sa.String(128), nullable=True, comment="记录校验和 (SHA-256)"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "wind_code",
            "report_period",
            "statement_type",
            "ann_dt",
            "revision_no",
            name="uq_cf_report",
        ),
    )
    op.create_index(
        op.f("ix_cash_flow_report_period"), "cash_flow", ["report_period"], unique=False
    )
    op.create_index(
        op.f("ix_cash_flow_wind_code"), "cash_flow", ["wind_code"], unique=False
    )

    # ------------------------------------------------------------------
    # 核心表 5: top_shareholders (§10.5)
    # ------------------------------------------------------------------
    op.create_table(
        "top_shareholders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("wind_code", sa.String(32), nullable=False, comment="Wind 代码"),
        sa.Column("ann_dt", sa.String(10), nullable=True, comment="公告日期"),
        sa.Column(
            "s_holder_enddate", sa.String(10), nullable=True, comment="股东持股截止日期"
        ),
        sa.Column("s_holder_name", sa.String(256), nullable=False, comment="股东名称"),
        sa.Column(
            "s_holder_aname",
            sa.String(256),
            nullable=True,
            comment="股东别名（用于实体对齐）",
        ),
        sa.Column("s_holder_pct", sa.Float(), nullable=True, comment="持股比例 (%)"),
        sa.Column("s_holder_quantity", sa.Float(), nullable=True, comment="持股数量"),
        sa.Column(
            "s_holder_holdercategory", sa.String(64), nullable=True, comment="股东类别"
        ),
        sa.Column("s_holder_sequence", sa.Integer(), nullable=True, comment="股东序号"),
        sa.Column("report_period", sa.String(10), nullable=True, comment="报告期"),
        sa.Column(
            "holder_entity_id",
            sa.String(64),
            nullable=True,
            comment="股东实体 ID（与 companies.entity_id 对齐）",
        ),
        sa.Column(
            "entity_match_confidence",
            sa.Float(),
            nullable=True,
            comment="实体对齐置信度 (0-1)",
        ),
        # 系统字段
        sa.Column(
            "source_record_id", sa.String(256), nullable=True, comment="原始记录 ID"
        ),
        sa.Column("source_file", sa.String(512), nullable=True, comment="来源文件名"),
        sa.Column("source_row", sa.Integer(), nullable=True, comment="来源行号"),
        sa.Column("source_type", sa.String(64), nullable=True, comment="来源类型"),
        sa.Column(
            "dataset_version", sa.String(64), nullable=True, comment="数据集版本"
        ),
        sa.Column("revision_no", sa.Integer(), nullable=False, comment="修订版本号"),
        sa.Column("is_latest", sa.Boolean(), nullable=False, comment="是否最新修订"),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="入库时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="最后更新时间",
        ),
        sa.Column("quality_flags", sa.JSON(), nullable=True, comment="数据质量标记"),
        sa.Column(
            "checksum", sa.String(128), nullable=True, comment="记录校验和 (SHA-256)"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_top_shareholders_holder_entity_id"),
        "top_shareholders",
        ["holder_entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_top_shareholders_wind_code"),
        "top_shareholders",
        ["wind_code"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # 核心表 6: announcements (§10.6)
    # ------------------------------------------------------------------
    op.create_table(
        "announcements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("object_id", sa.String(128), nullable=False, comment="公告源 ID"),
        sa.Column("wind_code", sa.String(32), nullable=False, comment="Wind 代码"),
        sa.Column("ann_dt", sa.String(10), nullable=True, comment="公告日期"),
        sa.Column("n_info_title", sa.String(512), nullable=False, comment="公告标题"),
        sa.Column(
            "n_info_fcode",
            sa.String(64),
            nullable=True,
            comment="公告类型代码（共 33 类）",
        ),
        sa.Column(
            "sentiment",
            sa.String(16),
            nullable=True,
            comment="情感: positive/negative/neutral",
        ),
        sa.Column(
            "sentiment_method", sa.String(32), nullable=True, comment="情感分析方法"
        ),
        sa.Column("source_uri", sa.String(1024), nullable=True, comment="来源 URI"),
        sa.Column(
            "content_hash", sa.String(128), nullable=True, comment="内容哈希 (SHA-256)"
        ),
        # 系统字段
        sa.Column(
            "source_record_id", sa.String(256), nullable=True, comment="原始记录 ID"
        ),
        sa.Column("source_file", sa.String(512), nullable=True, comment="来源文件名"),
        sa.Column("source_row", sa.Integer(), nullable=True, comment="来源行号"),
        sa.Column("source_type", sa.String(64), nullable=True, comment="来源类型"),
        sa.Column(
            "dataset_version", sa.String(64), nullable=True, comment="数据集版本"
        ),
        sa.Column("revision_no", sa.Integer(), nullable=False, comment="修订版本号"),
        sa.Column("is_latest", sa.Boolean(), nullable=False, comment="是否最新修订"),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="入库时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="最后更新时间",
        ),
        sa.Column("quality_flags", sa.JSON(), nullable=True, comment="数据质量标记"),
        sa.Column(
            "checksum", sa.String(128), nullable=True, comment="记录校验和 (SHA-256)"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_id"),
    )
    op.create_index(
        op.f("ix_announcements_wind_code"), "announcements", ["wind_code"], unique=False
    )

    # ------------------------------------------------------------------
    # 核心表 7: research_reports (§10.7)
    # ------------------------------------------------------------------
    op.create_table(
        "research_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_id", sa.String(128), nullable=False, comment="研报唯一 ID"),
        sa.Column("wind_code", sa.String(32), nullable=False, comment="Wind 代码"),
        sa.Column("sec_code", sa.String(32), nullable=True, comment="证券代码"),
        sa.Column("exchange_code", sa.String(16), nullable=True, comment="交易所代码"),
        sa.Column("sec_name", sa.String(128), nullable=True, comment="证券简称"),
        sa.Column("org_name", sa.String(256), nullable=True, comment="研究机构"),
        sa.Column("title", sa.String(512), nullable=False, comment="研报标题"),
        sa.Column("publish_date", sa.String(10), nullable=True, comment="发布日期"),
        sa.Column("abstract", sa.Text(), nullable=True, comment="摘要/核心观点"),
        sa.Column("rating_org", sa.String(32), nullable=True, comment="原始评级"),
        sa.Column(
            "rating_change",
            sa.String(16),
            nullable=True,
            comment="评级变化: up/down/maintain",
        ),
        sa.Column("industry_l1", sa.String(64), nullable=True, comment="申万一级行业"),
        sa.Column("sw_indu_code", sa.String(32), nullable=True, comment="申万行业代码"),
        sa.Column("source_uri", sa.String(1024), nullable=True, comment="来源 URI"),
        sa.Column("content_hash", sa.String(128), nullable=True, comment="内容哈希"),
        # 系统字段
        sa.Column(
            "source_record_id", sa.String(256), nullable=True, comment="原始记录 ID"
        ),
        sa.Column("source_file", sa.String(512), nullable=True, comment="来源文件名"),
        sa.Column("source_row", sa.Integer(), nullable=True, comment="来源行号"),
        sa.Column("source_type", sa.String(64), nullable=True, comment="来源类型"),
        sa.Column(
            "dataset_version", sa.String(64), nullable=True, comment="数据集版本"
        ),
        sa.Column("revision_no", sa.Integer(), nullable=False, comment="修订版本号"),
        sa.Column("is_latest", sa.Boolean(), nullable=False, comment="是否最新修订"),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="入库时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="最后更新时间",
        ),
        sa.Column("quality_flags", sa.JSON(), nullable=True, comment="数据质量标记"),
        sa.Column(
            "checksum", sa.String(128), nullable=True, comment="记录校验和 (SHA-256)"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_id"),
    )
    op.create_index(
        op.f("ix_research_reports_wind_code"),
        "research_reports",
        ["wind_code"],
        unique=False,
    )

    # ==================================================================
    # 派生表 8–14 (§10.8)
    # ==================================================================

    # ------------------------------------------------------------------
    # 派生表 8: conversation_sessions
    # ------------------------------------------------------------------
    op.create_table(
        "conversation_sessions",
        sa.Column("session_id", sa.String(64), nullable=False, comment="会话 ID"),
        sa.Column("user_id", sa.String(64), nullable=True, comment="用户 ID"),
        sa.Column("title", sa.String(256), nullable=True, comment="会话标题"),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            comment="状态: active/archived/closed",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, comment="创建时间"
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="最后更新时间",
        ),
        sa.Column("metadata", sa.JSON(), nullable=True, comment="附加元数据"),
        sa.PrimaryKeyConstraint("session_id"),
    )

    # ------------------------------------------------------------------
    # 派生表 9: conversation_turns
    # ------------------------------------------------------------------
    op.create_table(
        "conversation_turns",
        sa.Column("turn_id", sa.String(64), nullable=False, comment="轮次 ID"),
        sa.Column("session_id", sa.String(64), nullable=False, comment="所属会话 ID"),
        sa.Column("turn_index", sa.Integer(), nullable=False, comment="轮次序号"),
        sa.Column("question", sa.Text(), nullable=False, comment="用户问题"),
        sa.Column("answer", sa.Text(), nullable=True, comment="系统回答"),
        sa.Column("company_code", sa.String(32), nullable=True, comment="关联公司代码"),
        sa.Column("summary", sa.Text(), nullable=True, comment="轮次摘要 (用于记忆)"),
        sa.Column("trace_id", sa.String(64), nullable=True, comment="追踪 ID"),
        sa.Column("module_status", sa.JSON(), nullable=True, comment="各模块执行状态"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, comment="创建时间"
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["conversation_sessions.session_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("turn_id"),
    )
    op.create_index(
        op.f("ix_conversation_turns_session_id"),
        "conversation_turns",
        ["session_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # 派生表 10: rule_definitions
    # ------------------------------------------------------------------
    op.create_table(
        "rule_definitions",
        sa.Column("rule_id", sa.String(64), nullable=False, comment="规则唯一 ID"),
        sa.Column("rule_name", sa.String(256), nullable=False, comment="规则名称"),
        sa.Column(
            "category",
            sa.String(64),
            nullable=False,
            comment="规则类别 (如 revenue_quality)",
        ),
        sa.Column("description", sa.Text(), nullable=False, comment="规则描述"),
        sa.Column("formula", sa.Text(), nullable=True, comment="计算公式/逻辑描述"),
        sa.Column("threshold", sa.JSON(), nullable=True, comment="阈值配置 (JSON)"),
        sa.Column(
            "severity",
            sa.String(16),
            nullable=False,
            comment="默认严重程度: low/medium/high/critical",
        ),
        sa.Column("version", sa.String(32), nullable=False, comment="规则版本"),
        sa.Column("is_active", sa.Boolean(), nullable=False, comment="是否启用"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("rule_id"),
    )
    op.create_index(
        op.f("ix_rule_definitions_category"),
        "rule_definitions",
        ["category"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # 派生表 11: rule_evaluations
    # ------------------------------------------------------------------
    op.create_table(
        "rule_evaluations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rule_id", sa.String(64), nullable=False, comment="规则 ID"),
        sa.Column("wind_code", sa.String(32), nullable=False, comment="评估目标公司"),
        sa.Column("report_period", sa.String(10), nullable=False, comment="评估报告期"),
        sa.Column(
            "result",
            sa.String(16),
            nullable=True,
            comment="结果: triggered/normal/insufficient_data",
        ),
        sa.Column("score", sa.Float(), nullable=True, comment="评分 (0-1)"),
        sa.Column("detail", sa.JSON(), nullable=True, comment="评估详情 (JSON)"),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="评估时间",
        ),
        sa.Column(
            "rule_version", sa.String(32), nullable=False, comment="使用的规则版本"
        ),
        sa.ForeignKeyConstraint(
            ["rule_id"], ["rule_definitions.rule_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_rule_evaluations_rule_id"),
        "rule_evaluations",
        ["rule_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_rule_evaluations_wind_code"),
        "rule_evaluations",
        ["wind_code"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # 派生表 12: evidence_refs
    # ------------------------------------------------------------------
    op.create_table(
        "evidence_refs",
        sa.Column("evidence_id", sa.String(64), nullable=False, comment="证据唯一 ID"),
        sa.Column(
            "source_type",
            sa.String(32),
            nullable=False,
            comment="证据类型: financial_statement/ownership_record/news_article/regulation",
        ),
        sa.Column(
            "source_record_id", sa.String(256), nullable=False, comment="来源记录 ID"
        ),
        sa.Column("company_code", sa.String(32), nullable=True, comment="公司代码"),
        sa.Column("field_path", sa.String(256), nullable=True, comment="字段路径"),
        sa.Column("period", sa.String(10), nullable=True, comment="数据期间"),
        sa.Column("value", sa.String(256), nullable=True, comment="字段值"),
        sa.Column("unit", sa.String(16), nullable=True, comment="单位"),
        sa.Column(
            "statement_scope",
            sa.String(32),
            nullable=True,
            comment="报表口径: parent_company/consolidated",
        ),
        sa.Column("source_title", sa.String(512), nullable=True, comment="来源标题"),
        sa.Column("source_uri", sa.String(1024), nullable=True, comment="来源 URI"),
        sa.Column("source_excerpt", sa.Text(), nullable=True, comment="来源摘录"),
        sa.Column(
            "retrieval_score", sa.Float(), nullable=True, comment="检索相关性分数"
        ),
        sa.Column(
            "dataset_version", sa.String(64), nullable=False, comment="数据集版本"
        ),
        sa.Column(
            "retrieved_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="检索时间",
        ),
        sa.PrimaryKeyConstraint("evidence_id"),
    )

    # ------------------------------------------------------------------
    # 派生表 13: claims
    # ------------------------------------------------------------------
    op.create_table(
        "claims",
        sa.Column("claim_id", sa.String(64), nullable=False, comment="声明唯一 ID"),
        sa.Column("turn_id", sa.String(64), nullable=True, comment="关联轮次 ID"),
        sa.Column("text", sa.Text(), nullable=False, comment="声明内容"),
        sa.Column(
            "claim_type",
            sa.String(32),
            nullable=True,
            comment="声明类型: fact/analysis/suggestion",
        ),
        sa.Column(
            "severity",
            sa.String(16),
            nullable=False,
            comment="严重程度: none/low/medium/high/critical",
        ),
        sa.Column(
            "confidence",
            sa.String(16),
            nullable=True,
            comment="置信度: high/medium/low/unverified",
        ),
        sa.Column("rule_id", sa.String(64), nullable=True, comment="关联规则 ID"),
        sa.Column("rule_version", sa.String(32), nullable=True, comment="规则版本"),
        sa.Column(
            "verification_status",
            sa.String(16),
            nullable=False,
            comment="验证状态: pending/verified/refuted",
        ),
        sa.Column("limitations", sa.JSON(), nullable=True, comment="局限性说明"),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="生成时间",
        ),
        sa.PrimaryKeyConstraint("claim_id"),
    )
    op.create_index(op.f("ix_claims_turn_id"), "claims", ["turn_id"], unique=False)

    # ------------------------------------------------------------------
    # 派生表 14: risk_assessments
    # ------------------------------------------------------------------
    op.create_table(
        "risk_assessments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "assessment_id", sa.String(64), nullable=False, comment="评估唯一 ID"
        ),
        sa.Column("wind_code", sa.String(32), nullable=False, comment="Wind 代码"),
        sa.Column("overall_score", sa.Float(), nullable=True, comment="综合风险 0-1"),
        sa.Column("financial_score", sa.Float(), nullable=True, comment="财务风险 0-1"),
        sa.Column("ownership_score", sa.Float(), nullable=True, comment="股权风险 0-1"),
        sa.Column("sentiment_score", sa.Float(), nullable=True, comment="舆情风险 0-1"),
        sa.Column(
            "level",
            sa.String(16),
            nullable=False,
            comment="风险等级: none/low/medium/high/critical",
        ),
        sa.Column(
            "risk_factors", sa.JSON(), nullable=True, comment="风险因子详情 (JSON)"
        ),
        sa.Column(
            "rule_version", sa.String(32), nullable=False, comment="使用的规则版本"
        ),
        sa.Column(
            "dataset_version", sa.String(64), nullable=False, comment="使用的数据版本"
        ),
        sa.Column(
            "assessed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="评估时间",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_id"),
    )
    op.create_index(
        op.f("ix_risk_assessments_wind_code"),
        "risk_assessments",
        ["wind_code"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_risk_assessments_wind_code"), table_name="risk_assessments")
    op.drop_table("risk_assessments")
    op.drop_index(op.f("ix_claims_turn_id"), table_name="claims")
    op.drop_table("claims")
    op.drop_table("evidence_refs")
    op.drop_index(op.f("ix_rule_evaluations_wind_code"), table_name="rule_evaluations")
    op.drop_index(op.f("ix_rule_evaluations_rule_id"), table_name="rule_evaluations")
    op.drop_table("rule_evaluations")
    op.drop_index(op.f("ix_rule_definitions_category"), table_name="rule_definitions")
    op.drop_table("rule_definitions")
    op.drop_index(
        op.f("ix_conversation_turns_session_id"), table_name="conversation_turns"
    )
    op.drop_table("conversation_turns")
    op.drop_table("conversation_sessions")
    op.drop_index(op.f("ix_research_reports_wind_code"), table_name="research_reports")
    op.drop_table("research_reports")
    op.drop_index(op.f("ix_announcements_wind_code"), table_name="announcements")
    op.drop_table("announcements")
    op.drop_index(op.f("ix_top_shareholders_wind_code"), table_name="top_shareholders")
    op.drop_index(
        op.f("ix_top_shareholders_holder_entity_id"), table_name="top_shareholders"
    )
    op.drop_table("top_shareholders")
    op.drop_index(op.f("ix_cash_flow_wind_code"), table_name="cash_flow")
    op.drop_index(op.f("ix_cash_flow_report_period"), table_name="cash_flow")
    op.drop_table("cash_flow")
    op.drop_index(op.f("ix_income_statement_wind_code"), table_name="income_statement")
    op.drop_index(
        op.f("ix_income_statement_report_period"), table_name="income_statement"
    )
    op.drop_table("income_statement")
    op.drop_index(op.f("ix_balance_sheet_wind_code"), table_name="balance_sheet")
    op.drop_index(op.f("ix_balance_sheet_report_period"), table_name="balance_sheet")
    op.drop_table("balance_sheet")
    op.drop_index(op.f("ix_companies_wind_code"), table_name="companies")
    op.drop_table("companies")
