"""v8: 检索性能索引（Phase D #7 优化）

Revision ID: d8e4f5a6b7c8
Revises: a1b2c3d4e5f7
Create Date: 2026-08-07 12:00:00.000000

性能 smoke 定位：research_reports 的 SQL 兜底 LIKE 检索
（Phase D #1 故障注入下 Chroma 语义路径不可用时的降级路径）
每次触发全表扫描 + filesort（~40K 行），P95 ~5s，远超 500ms 目标。

优化：
  - research_reports.is_latest 加索引：WHERE is_latest=1 快速收敛行数；
  - research_reports.(is_latest, publish_date) 复合索引：覆盖排序，消除 filesort。

纯索引 DDL，不修改任何数据。
"""

from typing import Sequence, Union

from alembic import op


revision: str = "d8e4f5a6b7c8"
down_revision: Union[str, None] = "a1b2c3d4e5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_research_reports_is_latest",
        "research_reports",
        ["is_latest"],
    )
    op.create_index(
        "ix_research_reports_is_latest_publish_date",
        "research_reports",
        ["is_latest", "publish_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_research_reports_is_latest_publish_date", "research_reports")
    op.drop_index("ix_research_reports_is_latest", "research_reports")
