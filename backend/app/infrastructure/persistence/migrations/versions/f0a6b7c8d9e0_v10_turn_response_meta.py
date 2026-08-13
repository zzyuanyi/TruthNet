"""v10: conversation_turns add response_meta JSON.

Revision ID: f0a6b7c8d9e0
Revises: e9f5a6b7c8d9
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f0a6b7c8d9e0"
down_revision: Union[str, None] = "e9f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversation_turns",
        sa.Column(
            "response_meta",
            sa.JSON(),
            nullable=True,
            comment=(
                "回答元数据 {intent, follow_ups, supporting_evidence_ids, "
                "requested_period_text}"
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("conversation_turns", "response_meta")
