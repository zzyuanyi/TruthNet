"""v5: Phase C — 行业分位基准 + 评级拐点 + 直接 REST 溯源表

Revision ID: b6e1f2a3d4c5
Revises: d1e2f3a4b5c6
Create Date: 2026-08-03 00:00:00.000000

新增（数据任务 3/5、后端任务 16）:
  - industry_benchmarks（行业分位基准：p05-p95/mean/std/sample_count）
  - rating_changes（研报评级拐点）
  - analysis_runs（直接 REST 无 chat session 时的独立 provenance 载体）
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b6e1f2a3d4c5"
down_revision: Union[str, None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _mysql_table_args() -> dict:
    return {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"}


def upgrade() -> None:
    # ── 1. industry_benchmarks ────────────────────────────
    op.create_table(
        "industry_benchmarks",
        sa.Column("benchmark_id", sa.String(length=64), primary_key=True),
        sa.Column("industry_l1", sa.String(length=64), nullable=False),
        sa.Column("industry_l2", sa.String(length=64), nullable=True),
        sa.Column("metric_id", sa.String(length=32), nullable=False),
        sa.Column("rule_id", sa.String(length=16), nullable=False),
        sa.Column("period", sa.String(length=10), nullable=False),
        sa.Column("statement_scope", sa.String(length=32), nullable=False),
        sa.Column("company_type", sa.SmallInteger(), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("mean_value", sa.Float(), nullable=True),
        sa.Column("std_value", sa.Float(), nullable=True),
        sa.Column("min_value", sa.Float(), nullable=True),
        sa.Column("p05", sa.Float(), nullable=True),
        sa.Column("p25", sa.Float(), nullable=True),
        sa.Column("p50", sa.Float(), nullable=True),
        sa.Column("p75", sa.Float(), nullable=True),
        sa.Column("p95", sa.Float(), nullable=True),
        sa.Column("max_value", sa.Float(), nullable=True),
        sa.Column("dataset_version", sa.String(length=64), nullable=False),
        sa.Column("rule_set_version", sa.String(length=32), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "industry_l1",
            "metric_id",
            "period",
            "statement_scope",
            "dataset_version",
            name="uq_industry_benchmark_key",
        ),
        **_mysql_table_args(),
    )
    op.create_index("ix_industry_benchmarks_l1", "industry_benchmarks", ["industry_l1"])
    op.create_index("ix_industry_benchmarks_period", "industry_benchmarks", ["period"])
    op.create_index(
        "ix_industry_benchmarks_metric", "industry_benchmarks", ["metric_id"]
    )

    # ── 2. rating_changes ─────────────────────────────────
    op.create_table(
        "rating_changes",
        sa.Column("rating_change_id", sa.String(length=64), primary_key=True),
        sa.Column("wind_code", sa.String(length=32), nullable=False),
        sa.Column("quarter", sa.String(length=8), nullable=False),
        sa.Column("institution", sa.String(length=256), nullable=False),
        sa.Column("previous_rating", sa.String(length=32), nullable=True),
        sa.Column("current_rating", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("report_id", sa.String(length=128), nullable=True),
        sa.Column("published_at", sa.String(length=10), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence_id", sa.String(length=64), nullable=True),
        sa.Column("dataset_version", sa.String(length=64), nullable=False),
        sa.UniqueConstraint(
            "wind_code",
            "quarter",
            "institution",
            "report_id",
            name="uq_rating_change_key",
        ),
        **_mysql_table_args(),
    )
    op.create_index("ix_rating_changes_wind_code", "rating_changes", ["wind_code"])
    op.create_index("ix_rating_changes_quarter", "rating_changes", ["quarter"])

    # ── 3. analysis_runs ──────────────────────────────────
    op.create_table(
        "analysis_runs",
        sa.Column("run_id", sa.String(length=64), primary_key=True),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("endpoint", sa.String(length=64), nullable=False),
        sa.Column("company_codes", sa.JSON(), nullable=True),
        sa.Column("period", sa.String(length=10), nullable=True),
        sa.Column("statement_scope", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        **_mysql_table_args(),
    )
    op.create_index("ix_analysis_runs_trace_id", "analysis_runs", ["trace_id"])


def downgrade() -> None:
    op.drop_index("ix_analysis_runs_trace_id", table_name="analysis_runs")
    op.drop_table("analysis_runs")

    op.drop_index("ix_rating_changes_quarter", table_name="rating_changes")
    op.drop_index("ix_rating_changes_wind_code", table_name="rating_changes")
    op.drop_table("rating_changes")

    op.drop_index("ix_industry_benchmarks_metric", table_name="industry_benchmarks")
    op.drop_index("ix_industry_benchmarks_period", table_name="industry_benchmarks")
    op.drop_index("ix_industry_benchmarks_l1", table_name="industry_benchmarks")
    op.drop_table("industry_benchmarks")
