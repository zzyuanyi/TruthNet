"""v3: top_shareholders source_record_id unique constraint

Revision ID: e41995a518b0
Revises: c2e7a8d9f001
Create Date: 2026-07-28 16:00:00.000000

为 top_shareholders.source_record_id 添加唯一约束，作为 upsert 键。
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e41995a518b0"
down_revision: str | None = "c2e7a8d9f001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_top_shareholders_source_record_id",
        "top_shareholders",
        ["source_record_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_top_shareholders_source_record_id",
        "top_shareholders",
        type_="unique",
    )
