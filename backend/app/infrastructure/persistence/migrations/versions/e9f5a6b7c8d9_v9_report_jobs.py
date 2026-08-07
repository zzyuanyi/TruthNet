"""v9: 新增 report_jobs 表（Phase D #8 PDF 报告长任务）

Revision ID: e9f5a6b7c8d9
Revises: d8e4f5a6b7c8
Create Date: 2026-08-07 13:00:00.000000

V12 §10.8：report_jobs 为 PDF 报告任务专用派生表（analysis_runs 不可复用）。
状态机：queued → running → succeeded | failed | cancelled。
幂等：idempotency_key 唯一约束。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e9f5a6b7c8d9"
down_revision: Union[str, None] = "d8e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "report_jobs",
        sa.Column("report_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("company_code", sa.String(length=32), nullable=True),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="queued"
        ),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("request_payload", sa.JSON(), nullable=True),
        sa.Column("file_path", sa.String(length=512), nullable=True),
        sa.Column("file_sha256", sa.String(length=64), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("report_id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_report_jobs_session_id", "report_jobs", ["session_id"])
    op.create_index("ix_report_jobs_company_code", "report_jobs", ["company_code"])
    op.create_index("ix_report_jobs_status", "report_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_report_jobs_status", "report_jobs")
    op.drop_index("ix_report_jobs_company_code", "report_jobs")
    op.drop_index("ix_report_jobs_session_id", "report_jobs")
    op.drop_table("report_jobs")
