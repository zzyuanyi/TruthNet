"""v2_corrective: charset/collation + Decimal types + statement_type docs

Revision ID: c2e7a8d9f001
Revises: f5d9389bbef0
Create Date: 2026-07-22 10:00:00.000000

矫正项:
1. 显式设置所有表 CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci
2. 改善 statement_type 列注释（含数据字典引用）
3. 将 top_shareholders.s_holder_pct 从 FLOAT 转为 DECIMAL(10,4)
4. 将 top_shareholders.s_holder_quantity 从 FLOAT 转为 DECIMAL(20,2)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = "c2e7a8d9f001"
down_revision: Union[str, None] = "f5d9389bbef0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """矫正字符集、排序规则、Decimal 类型和 statement_type 注释."""

    # ── 核心表 charset/collation ─────────────────────────

    # companies
    op.execute(
        "ALTER TABLE companies CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
    )

    # balance_sheet
    op.execute(
        "ALTER TABLE balance_sheet CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
    )
    op.alter_column(
        "balance_sheet",
        "statement_type",
        existing_type=sa.String(32),
        comment="报表类型代码: 408001000=合并报表(推荐主口径), 408006000=母公司报表(当前数据口径) (详见 domain/finance/statement_type.py)",
        existing_nullable=False,
    )

    # income_statement
    op.execute(
        "ALTER TABLE income_statement CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
    )
    op.alter_column(
        "income_statement",
        "statement_type",
        existing_type=sa.String(32),
        comment="报表类型代码: 408001000=合并报表(推荐主口径), 408006000=母公司报表(当前数据口径)",
        existing_nullable=False,
    )

    # cash_flow
    op.execute(
        "ALTER TABLE cash_flow CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
    )
    op.alter_column(
        "cash_flow",
        "statement_type",
        existing_type=sa.String(32),
        comment="报表类型代码: 408001000=合并报表(推荐主口径), 408006000=母公司报表(当前数据口径)",
        existing_nullable=False,
    )

    # top_shareholders — charset + Decimal 类型修复
    op.execute(
        "ALTER TABLE top_shareholders CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
    )
    op.alter_column(
        "top_shareholders",
        "s_holder_pct",
        existing_type=sa.Float(),
        type_=sa.Numeric(10, 4),
        existing_nullable=True,
        comment="持股比例 (%) — 精度 10 位，4 位小数",
    )
    op.alter_column(
        "top_shareholders",
        "s_holder_quantity",
        existing_type=sa.Float(),
        type_=sa.Numeric(20, 2),
        existing_nullable=True,
        comment="持股数量",
    )

    # announcements
    op.execute(
        "ALTER TABLE announcements CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
    )

    # research_reports
    op.execute(
        "ALTER TABLE research_reports CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
    )

    # ── 派生表 charset/collation ─────────────────────────

    op.execute(
        "ALTER TABLE conversation_sessions CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
    )
    op.execute(
        "ALTER TABLE conversation_turns CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
    )
    op.execute(
        "ALTER TABLE rule_definitions CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
    )
    op.execute(
        "ALTER TABLE rule_evaluations CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
    )
    op.execute(
        "ALTER TABLE evidence_refs CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
    )
    op.execute(
        "ALTER TABLE claims CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
    )
    op.execute(
        "ALTER TABLE risk_assessments CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
    )


def downgrade() -> None:
    """回退: 恢复为数据库默认 charset (不指定) 并回退 Decimal→Float."""

    # 字符集不强制回退（保持兼容，让数据库使用默认值）
    # 只回退类型变更

    op.alter_column(
        "top_shareholders",
        "s_holder_pct",
        existing_type=sa.Numeric(10, 4),
        type_=sa.Float(),
        existing_nullable=True,
        comment="持股比例 (%)",
    )
    op.alter_column(
        "top_shareholders",
        "s_holder_quantity",
        existing_type=sa.Numeric(20, 2),
        type_=sa.Float(),
        existing_nullable=True,
        comment="持股数量",
    )

    # 注释回退
    op.alter_column(
        "balance_sheet",
        "statement_type",
        existing_type=sa.String(32),
        comment="报表类型代码",
        existing_nullable=False,
    )
    op.alter_column(
        "income_statement",
        "statement_type",
        existing_type=sa.String(32),
        comment="报表类型代码",
        existing_nullable=False,
    )
    op.alter_column(
        "cash_flow",
        "statement_type",
        existing_type=sa.String(32),
        comment="报表类型代码",
        existing_nullable=False,
    )
