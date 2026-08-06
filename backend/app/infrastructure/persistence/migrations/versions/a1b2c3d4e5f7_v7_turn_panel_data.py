"""v7: conversation_turns 增加 panel_data 列

Revision ID: a1b2c3d4e5f7
Revises: c7f2a3b4e5d6
Create Date: 2026-08-06 22:00:00.000000

历史会话分析面板恢复（对齐审计 P1-3）：持久化每轮面板摘要
{risk_level, triggered_rules, key_metrics, follow_ups}，
刷新/切换历史会话后 AnalysisPanel 不再为空。
旧行 panel_data 为 NULL（前端按空态处理，不伪造风险等级）。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, None] = "c7f2a3b4e5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversation_turns",
        sa.Column("panel_data", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversation_turns", "panel_data")
