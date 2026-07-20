"""TruthNet V12 核心 7 表建表

Revision ID: 001
Revises:
Create Date: 2026-07-19

严格按照 V12 §10 数据架构定义：
  §10.3  companies
  §10.4  balance_sheet / income_statement / cash_flow
  §10.5  top_shareholders
  §10.6  announcements
  §10.7  research_reports

每表附加 §10.2 公共系统字段（revision_no, is_latest, checksum 等）。
不使用 MySQL ENUM —— 统一 VARCHAR + CHECK 或字典表。
财务表唯一约束：(wind_code, report_period, statement_type, ann_dt, revision_no)
statement_type 说明：408001000=合并报表，408006000=母公司报表（V12 §1.4 当前数据主口径）
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ================================================================
    # 1. companies  — V12 §10.3
    # ================================================================
    op.create_table(
        "companies",
        # 业务主键
        sa.Column(
            "entity_id",
            sa.String(64),
            primary_key=True,
            comment="内部稳定实体 ID",
        ),
        sa.Column(
            "wind_code",
            sa.String(20),
            unique=True,
            nullable=False,
            comment="Wind 代码，如 600519.SH",
        ),
        sa.Column("sec_name", sa.String(128), nullable=False, comment="证券简称"),
        sa.Column(
            "aliases",
            mysql.JSON,
            nullable=True,
            comment="曾用名和别名列表",
        ),
        sa.Column(
            "exchange_code",
            sa.String(16),
            nullable=True,
            comment="交易所代码: XSHG / XSHE",
        ),
        sa.Column(
            "industry_l1",
            sa.String(64),
            nullable=True,
            comment="申万一级行业",
        ),
        sa.Column(
            "industry_l2",
            sa.String(64),
            nullable=True,
            comment="申万二级行业",
        ),
        sa.Column(
            "sw_indu_code",
            sa.String(16),
            nullable=True,
            comment="申万行业代码",
        ),
        sa.Column(
            "comp_type_code",
            sa.SmallInteger(),
            nullable=True,
            comment="公司类型: 1=非金融,2=银行,3=保险,4=证券",
        ),
        sa.Column("listing_date", sa.Date(), nullable=True, comment="上市日期"),
        sa.Column(
            "industry_source",
            sa.String(64),
            nullable=True,
            comment="行业分类来源（研报/akshare）",
        ),
        sa.Column(
            "industry_as_of",
            sa.Date(),
            nullable=True,
            comment="行业分类有效日期",
        ),
        # — 系统字段 §10.2 —
        sa.Column("source_record_id", sa.String(128), nullable=True),
        sa.Column("source_file", sa.String(256), nullable=True),
        sa.Column("source_row", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(48), nullable=True),
        sa.Column(
            "dataset_version",
            sa.String(32),
            nullable=False,
            server_default="official-2026-07",
        ),
        sa.Column(
            "revision_no",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "is_latest",
            sa.Boolean(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "ingested_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("quality_flags", mysql.JSON, nullable=True, comment="数据质量标记"),
        sa.Column("checksum", sa.String(64), nullable=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )
    op.create_index("ix_companies_wind_code", "companies", ["wind_code"])
    op.create_index("ix_companies_sec_name", "companies", ["sec_name"])
    op.create_index("ix_companies_industry_l1", "companies", ["industry_l1"])

    # ================================================================
    # 2. balance_sheet  — V12 §10.4
    # ================================================================
    op.create_table(
        "balance_sheet",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "wind_code",
            sa.String(20),
            nullable=False,
            comment="Wind 代码",
        ),
        sa.Column(
            "report_period",
            sa.String(10),
            nullable=False,
            comment="报告期，如 2024-12-31",
        ),
        sa.Column(
            "statement_type",
            sa.String(16),
            nullable=False,
            comment="报表类型: 408001000=合并报表, 408006000=母公司报表",
        ),
        sa.Column("ann_dt", sa.Date(), nullable=True, comment="公告日期"),
        # 资产
        sa.Column(
            "monetary_cap",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="货币资金",
        ),
        sa.Column(
            "acct_rcv",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="应收账款",
        ),
        sa.Column(
            "oth_rcv",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="其他应收款",
        ),
        sa.Column(
            "inventories",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="存货",
        ),
        sa.Column(
            "tot_cur_assets",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="流动资产合计",
        ),
        sa.Column(
            "fix_assets",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="固定资产",
        ),
        sa.Column(
            "goodwill",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="商誉",
        ),
        sa.Column(
            "tot_assets",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="资产总计",
        ),
        # 负债
        sa.Column(
            "st_borrow",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="短期借款",
        ),
        sa.Column(
            "lt_borrow",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="长期借款",
        ),
        sa.Column(
            "acct_payable",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="应付账款",
        ),
        sa.Column(
            "tot_cur_liab",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="流动负债合计",
        ),
        sa.Column(
            "tot_liab",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="负债合计",
        ),
        sa.Column(
            "tot_shrhldr_eqy_incl_min_int",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="股东权益（含少数股东）",
        ),
        # — 系统字段 —
        sa.Column("source_record_id", sa.String(128), nullable=True),
        sa.Column("source_file", sa.String(256), nullable=True),
        sa.Column("source_row", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(48), nullable=True),
        sa.Column(
            "dataset_version",
            sa.String(32),
            nullable=False,
            server_default="official-2026-07",
        ),
        sa.Column(
            "revision_no",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "is_latest",
            sa.Boolean(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "ingested_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("quality_flags", mysql.JSON, nullable=True),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.UniqueConstraint(
            "wind_code",
            "report_period",
            "statement_type",
            "ann_dt",
            "revision_no",
            name="uq_bs_period_rev",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )
    op.create_index("ix_bs_wind_code", "balance_sheet", ["wind_code"])
    op.create_index("ix_bs_report_period", "balance_sheet", ["report_period"])

    # ================================================================
    # 3. income_statement  — V12 §10.4
    # ================================================================
    op.create_table(
        "income_statement",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("wind_code", sa.String(20), nullable=False),
        sa.Column("report_period", sa.String(10), nullable=False),
        sa.Column(
            "statement_type",
            sa.String(16),
            nullable=False,
            comment="报表类型: 408001000=合并报表, 408006000=母公司报表",
        ),
        sa.Column("ann_dt", sa.Date(), nullable=True),
        sa.Column(
            "oper_rev",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="营业收入",
        ),
        sa.Column(
            "tot_oper_rev",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="营业总收入",
        ),
        sa.Column(
            "less_oper_cost",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="营业成本",
        ),
        sa.Column(
            "less_selling_dist_exp",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="销售费用",
        ),
        sa.Column(
            "less_gerl_admin_exp",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="管理费用",
        ),
        sa.Column(
            "less_fin_exp",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="财务费用",
        ),
        sa.Column(
            "oper_profit",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="营业利润",
        ),
        sa.Column(
            "tot_profit",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="利润总额",
        ),
        sa.Column(
            "net_profit_excl_min_int_inc",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="净利润（不含少数股东）",
        ),
        sa.Column(
            "net_profit_after_ded_nr_lp",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="扣非净利润",
        ),
        # — 系统字段 —
        sa.Column("source_record_id", sa.String(128), nullable=True),
        sa.Column("source_file", sa.String(256), nullable=True),
        sa.Column("source_row", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(48), nullable=True),
        sa.Column(
            "dataset_version",
            sa.String(32),
            nullable=False,
            server_default="official-2026-07",
        ),
        sa.Column(
            "revision_no",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "is_latest",
            sa.Boolean(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "ingested_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("quality_flags", mysql.JSON, nullable=True),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.UniqueConstraint(
            "wind_code",
            "report_period",
            "statement_type",
            "ann_dt",
            "revision_no",
            name="uq_is_period_rev",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )
    op.create_index("ix_is_wind_code", "income_statement", ["wind_code"])
    op.create_index("ix_is_report_period", "income_statement", ["report_period"])

    # ================================================================
    # 4. cash_flow  — V12 §10.4
    # ================================================================
    op.create_table(
        "cash_flow",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("wind_code", sa.String(20), nullable=False),
        sa.Column("report_period", sa.String(10), nullable=False),
        sa.Column(
            "statement_type",
            sa.String(16),
            nullable=False,
            comment="报表类型: 408001000=合并报表, 408006000=母公司报表",
        ),
        sa.Column("ann_dt", sa.Date(), nullable=True),
        sa.Column(
            "net_cash_flows_oper_act",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="经营活动现金流量净额",
        ),
        sa.Column(
            "net_cash_flows_inv_act",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="投资活动现金流量净额",
        ),
        sa.Column(
            "net_cash_flows_fnc_act",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="筹资活动现金流量净额",
        ),
        sa.Column(
            "net_incr_cash_cash_equ",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="现金及等价物净增加额",
        ),
        sa.Column(
            "free_cash_flow",
            sa.DECIMAL(25, 4),
            nullable=True,
            comment="企业自由现金流 FCFF",
        ),
        # — 系统字段 —
        sa.Column("source_record_id", sa.String(128), nullable=True),
        sa.Column("source_file", sa.String(256), nullable=True),
        sa.Column("source_row", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(48), nullable=True),
        sa.Column(
            "dataset_version",
            sa.String(32),
            nullable=False,
            server_default="official-2026-07",
        ),
        sa.Column(
            "revision_no",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "is_latest",
            sa.Boolean(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "ingested_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("quality_flags", mysql.JSON, nullable=True),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.UniqueConstraint(
            "wind_code",
            "report_period",
            "statement_type",
            "ann_dt",
            "revision_no",
            name="uq_cf_period_rev",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )
    op.create_index("ix_cf_wind_code", "cash_flow", ["wind_code"])
    op.create_index("ix_cf_report_period", "cash_flow", ["report_period"])

    # ================================================================
    # 5. top_shareholders  — V12 §10.5
    # ================================================================
    op.create_table(
        "top_shareholders",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("wind_code", sa.String(20), nullable=False, comment="Wind 代码"),
        sa.Column("ann_dt", sa.Date(), nullable=True, comment="公告日期"),
        sa.Column(
            "s_holder_enddate",
            sa.Date(),
            nullable=True,
            comment="股东数据截止日期",
        ),
        sa.Column(
            "s_holder_name",
            sa.String(256),
            nullable=False,
            comment="股东名称",
        ),
        sa.Column(
            "s_holder_aname",
            sa.String(256),
            nullable=True,
            comment="股东名称（别名）",
        ),
        sa.Column(
            "s_holder_pct",
            sa.DECIMAL(10, 4),
            nullable=True,
            comment="持股比例（%）",
        ),
        sa.Column(
            "s_holder_quantity",
            sa.DECIMAL(20, 0),
            nullable=True,
            comment="持股数量（股）",
        ),
        sa.Column(
            "s_holder_holdercategory",
            sa.SmallInteger(),
            nullable=True,
            comment="股东类别: 1=个人, 2=企业",
        ),
        sa.Column(
            "s_holder_sequence",
            sa.Integer(),
            nullable=True,
            comment="关联方序号",
        ),
        sa.Column(
            "report_period",
            sa.String(10),
            nullable=True,
            comment="报告期",
        ),
        sa.Column(
            "holder_entity_id",
            sa.String(64),
            nullable=True,
            comment="股东实体对齐后的 entity_id",
        ),
        sa.Column(
            "entity_match_confidence",
            sa.Float(),
            nullable=True,
            comment="实体对齐置信度 0-1",
        ),
        # — 系统字段 —
        sa.Column("source_record_id", sa.String(128), nullable=True),
        sa.Column("source_file", sa.String(256), nullable=True),
        sa.Column("source_row", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(48), nullable=True),
        sa.Column(
            "dataset_version",
            sa.String(32),
            nullable=False,
            server_default="official-2026-07",
        ),
        sa.Column(
            "revision_no",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "is_latest",
            sa.Boolean(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "ingested_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("quality_flags", mysql.JSON, nullable=True),
        sa.Column("checksum", sa.String(64), nullable=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )
    op.create_index("ix_ts_wind_code", "top_shareholders", ["wind_code"])
    op.create_index("ix_ts_holder_name", "top_shareholders", ["s_holder_name"])
    op.create_index("ix_ts_enddate", "top_shareholders", ["s_holder_enddate"])

    # ================================================================
    # 6. announcements  — V12 §10.6
    # ================================================================
    op.create_table(
        "announcements",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "object_id",
            sa.String(64),
            unique=True,
            nullable=False,
            comment="公告唯一 ID（UUID）",
        ),
        sa.Column("wind_code", sa.String(20), nullable=False, comment="Wind 代码"),
        sa.Column("ann_dt", sa.Date(), nullable=False, comment="公告日期"),
        sa.Column(
            "n_info_title",
            sa.Text(),
            nullable=False,
            comment="公告标题",
        ),
        sa.Column(
            "n_info_fcode",
            sa.String(256),
            nullable=True,
            comment="公告类型代码，多条用 | 分隔",
        ),
        sa.Column(
            "sentiment",
            sa.String(16),
            nullable=True,
            comment="情绪: positive/negative/neutral",
        ),
        sa.Column(
            "sentiment_method",
            sa.String(32),
            nullable=True,
            comment="情绪判定方法: rule / llm / manual",
        ),
        sa.Column(
            "source_uri",
            sa.String(1024),
            nullable=True,
            comment="公告原文链接",
        ),
        sa.Column(
            "content_hash",
            sa.String(64),
            nullable=True,
            comment="内容哈希",
        ),
        # — 系统字段 —
        sa.Column("source_record_id", sa.String(128), nullable=True),
        sa.Column("source_file", sa.String(256), nullable=True),
        sa.Column("source_row", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(48), nullable=True),
        sa.Column(
            "dataset_version",
            sa.String(32),
            nullable=False,
            server_default="official-2026-07",
        ),
        sa.Column(
            "revision_no",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "is_latest",
            sa.Boolean(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "ingested_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("quality_flags", mysql.JSON, nullable=True),
        sa.Column("checksum", sa.String(64), nullable=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )
    op.create_index("ix_ann_wind_code", "announcements", ["wind_code"])
    op.create_index("ix_ann_dt", "announcements", ["ann_dt"])
    op.create_index("ix_ann_fcode", "announcements", ["n_info_fcode"])

    # ================================================================
    # 7. research_reports  — V12 §10.7
    # ================================================================
    op.create_table(
        "research_reports",
        sa.Column(
            "id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "report_id",
            sa.Integer(),
            unique=True,
            nullable=False,
            comment="研报唯一 ID",
        ),
        sa.Column("wind_code", sa.String(20), nullable=True, comment="Wind 代码"),
        sa.Column(
            "sec_code",
            sa.String(16),
            nullable=True,
            comment="证券代码（数字）",
        ),
        sa.Column(
            "exchange_code",
            sa.String(16),
            nullable=True,
            comment="XSHG / XSHE",
        ),
        sa.Column(
            "sec_name",
            sa.String(128),
            nullable=True,
            comment="证券简称",
        ),
        sa.Column(
            "org_name",
            sa.String(256),
            nullable=True,
            comment="发布机构",
        ),
        sa.Column("title", sa.Text(), nullable=False, comment="研报标题"),
        sa.Column("publish_date", sa.Date(), nullable=True, comment="发布日期"),
        sa.Column(
            "abstract",
            sa.Text(),
            nullable=True,
            comment="摘要（入向量库核心字段）",
        ),
        sa.Column(
            "rating_org",
            sa.String(64),
            nullable=True,
            comment="原始评级",
        ),
        sa.Column(
            "rating_change",
            sa.String(16),
            nullable=True,
            comment="评级变动: 维持/上调/下调",
        ),
        sa.Column(
            "industry_l1",
            sa.String(64),
            nullable=True,
            comment="申万一级行业",
        ),
        sa.Column(
            "sw_indu_code",
            sa.String(16),
            nullable=True,
            comment="申万行业代码",
        ),
        sa.Column(
            "source_uri",
            sa.String(1024),
            nullable=True,
            comment="研报原文链接",
        ),
        sa.Column(
            "content_hash",
            sa.String(64),
            nullable=True,
            comment="内容哈希",
        ),
        # — 系统字段 —
        sa.Column("source_record_id", sa.String(128), nullable=True),
        sa.Column("source_file", sa.String(256), nullable=True),
        sa.Column("source_row", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(48), nullable=True),
        sa.Column(
            "dataset_version",
            sa.String(32),
            nullable=False,
            server_default="official-2026-07",
        ),
        sa.Column(
            "revision_no",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "is_latest",
            sa.Boolean(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "ingested_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("quality_flags", mysql.JSON, nullable=True),
        sa.Column("checksum", sa.String(64), nullable=True),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )
    op.create_index("ix_rr_wind_code", "research_reports", ["wind_code"])
    op.create_index("ix_rr_publish_date", "research_reports", ["publish_date"])
    op.create_index("ix_rr_org_name", "research_reports", ["org_name"])


def downgrade() -> None:
    """按依赖逆序删除。"""
    op.drop_table("research_reports")
    op.drop_table("announcements")
    op.drop_table("top_shareholders")
    op.drop_table("cash_flow")
    op.drop_table("income_statement")
    op.drop_table("balance_sheet")
    op.drop_table("companies")
