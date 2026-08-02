"""v4: Phase C — provenance tables + event cluster tables

Revision ID: d1e2f3a4b5c6
Revises: e41995a518b0
Create Date: 2026-08-02 12:00:00.000000

新增:
  - event_clusters / event_cluster_sources（任务 15 交接表）
  - claim_evidence_links（任务 16 Claim↔Evidence 关系表）
  - evidence_refs 增加 turn_id/trace_id/module/source_table
  - claims 增加 trace_id/company_code/module
  - claims.confidence varchar(16) → FLOAT（与 Agent Pydantic float 对齐，表为空安全）
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "e41995a518b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _mysql_table_args() -> dict:
    return {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"}


def upgrade() -> None:
    # ── 1. event_clusters ────────────────────────────────
    op.create_table(
        "event_clusters",
        sa.Column("event_cluster_id", sa.String(length=64), primary_key=True),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("wind_code", sa.String(length=32), nullable=False),
        sa.Column("topic", sa.String(length=256), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("sentiment", sa.String(length=16), nullable=False),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("cluster_method", sa.String(length=64), nullable=True),
        sa.Column("cluster_version", sa.String(length=32), nullable=True),
        sa.Column("dataset_version", sa.String(length=64), nullable=True),
        sa.Column("quality_flags", sa.JSON(), nullable=True),
        sa.Column("evidence_ids", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        **_mysql_table_args(),
    )
    op.create_index("ix_event_clusters_wind_code", "event_clusters", ["wind_code"])

    # ── 2. event_cluster_sources ─────────────────────────
    op.create_table(
        "event_cluster_sources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "event_cluster_id",
            sa.String(length=64),
            sa.ForeignKey("event_clusters.event_cluster_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_record_id", sa.String(length=256), nullable=False),
        sa.Column("evidence_id", sa.String(length=64), nullable=True),
        sa.Column("source_title", sa.String(length=512), nullable=True),
        sa.Column("source_uri", sa.String(length=1024), nullable=True),
        sa.Column("published_at", sa.Date(), nullable=True),
        sa.Column("content_hash", sa.String(length=128), nullable=True),
        sa.Column("sequence_no", sa.Integer(), nullable=True),
        sa.UniqueConstraint(
            "event_cluster_id",
            "source_record_id",
            name="uq_event_cluster_source",
        ),
        **_mysql_table_args(),
    )
    op.create_index(
        "ix_event_cluster_sources_evidence_id",
        "event_cluster_sources",
        ["evidence_id"],
    )

    # ── 3. claim_evidence_links ──────────────────────────
    op.create_table(
        "claim_evidence_links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "claim_id",
            sa.String(length=64),
            sa.ForeignKey("claims.claim_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "evidence_id",
            sa.String(length=64),
            sa.ForeignKey("evidence_refs.evidence_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relation_type", sa.String(length=16), nullable=True),
        sa.Column("sequence_no", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "claim_id",
            "evidence_id",
            "relation_type",
            name="uq_claim_evidence_link",
        ),
        **_mysql_table_args(),
    )
    op.create_index(
        "ix_claim_evidence_links_claim_id", "claim_evidence_links", ["claim_id"]
    )
    op.create_index(
        "ix_claim_evidence_links_evidence_id", "claim_evidence_links", ["evidence_id"]
    )

    # ── 4. evidence_refs 新增列 ──────────────────────────
    op.add_column(
        "evidence_refs", sa.Column("turn_id", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "evidence_refs", sa.Column("trace_id", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "evidence_refs", sa.Column("module", sa.String(length=32), nullable=True)
    )
    op.add_column(
        "evidence_refs", sa.Column("source_table", sa.String(length=64), nullable=True)
    )
    op.create_index("ix_evidence_refs_turn_id", "evidence_refs", ["turn_id"])
    op.create_index("ix_evidence_refs_trace_id", "evidence_refs", ["trace_id"])

    # ── 5. claims 新增列 + confidence 类型对齐 ───────────
    op.add_column("claims", sa.Column("trace_id", sa.String(length=64), nullable=True))
    op.add_column(
        "claims", sa.Column("company_code", sa.String(length=32), nullable=True)
    )
    op.add_column("claims", sa.Column("module", sa.String(length=32), nullable=True))
    op.create_index("ix_claims_trace_id", "claims", ["trace_id"])

    op.alter_column(
        "claims",
        "confidence",
        existing_type=sa.String(length=16),
        type_=sa.Float(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "claims",
        "confidence",
        existing_type=sa.Float(),
        type_=sa.String(length=16),
        existing_nullable=True,
    )
    op.drop_index("ix_claims_trace_id", table_name="claims")
    op.drop_column("claims", "module")
    op.drop_column("claims", "company_code")
    op.drop_column("claims", "trace_id")

    op.drop_index("ix_evidence_refs_trace_id", table_name="evidence_refs")
    op.drop_index("ix_evidence_refs_turn_id", table_name="evidence_refs")
    op.drop_column("evidence_refs", "source_table")
    op.drop_column("evidence_refs", "module")
    op.drop_column("evidence_refs", "trace_id")
    op.drop_column("evidence_refs", "turn_id")

    op.drop_index(
        "ix_claim_evidence_links_evidence_id", table_name="claim_evidence_links"
    )
    op.drop_index("ix_claim_evidence_links_claim_id", table_name="claim_evidence_links")
    op.drop_table("claim_evidence_links")

    op.drop_index(
        "ix_event_cluster_sources_evidence_id", table_name="event_cluster_sources"
    )
    op.drop_table("event_cluster_sources")

    op.drop_index("ix_event_clusters_wind_code", table_name="event_clusters")
    op.drop_table("event_clusters")
