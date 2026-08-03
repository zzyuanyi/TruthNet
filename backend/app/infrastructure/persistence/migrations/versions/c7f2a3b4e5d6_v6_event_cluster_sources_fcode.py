"""v6: event_cluster_sources 增加 fcode 列

Revision ID: c7f2a3b4e5d6
Revises: b6e1f2a3d4c5
Create Date: 2026-08-03 12:00:00.000000

事件簇来源表缺少 fcode 列，导致幂等指纹（fingerprint 含 fcode）无法重建，
重复导入被误判为 conflicted。补列并对既有行回填 NULL。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c7f2a3b4e5d6"
down_revision: Union[str, None] = "b6e1f2a3d4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "event_cluster_sources",
        sa.Column("fcode", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("event_cluster_sources", "fcode")
