"""v11: 金融企业专属字段（任务⑤ · 41 列增量）

Revision ID: f1a2b3c4d5e6
Revises: f0a6b7c8d9e0
Create Date: 2026-08-15 00:00:00.000000

数据组任务⑤ 交付：为 balance_sheet / income_statement / cash_flow 三表
新增金融企业专属字段（银行/保险/证券），列名与
scripts/import_finance_fields.py::FIN_FIELDS 一一对应。

- 字段类型 FLOAT NULL（原始 CSV 对齐 upsert 用，缺失置 NULL）；
- 采用 Alembic 表达 schema 变更，导入脚本只负责数据写入，
  不再承担 ALTER TABLE DDL（scripts/import_finance_fields.py 会
  fail-fast 校验列存在并提示先执行本迁移）；
- 纯 DDL，不修改任何数据。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "f0a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 与 scripts/import_finance_fields.py::FIN_FIELDS 保持一致（41 列）
_FIN_FIELDS: dict[str, list[str]] = {
    "balance_sheet": [
        # 银行
        "loans_and_adv_granted",
        "cash_deposits_central_bank",
        "asset_dep_oth_banks_fin_inst",
        "borrow_central_bank",
        "liab_dep_oth_banks_fin_inst",
        "cust_bank_dep",
        "precious_metals",
        # 保险
        "prem_rcv",
        "rsrv_insur_cont",
        "unearned_prem_rsrv",
        "out_loss_rsrv",
        "life_insur_rsrv",
        "claims_payable",
        # 证券
        "clients_cap_deposit",
        "clients_rsrv_settle",
        "acting_trading_sec",
        "mrgn_paid",
        "lending_funds",
        "settle_rsrv",
    ],
    "income_statement": [
        # 银行
        "int_inc",
        "net_int_inc",
        "less_int_exp",
        # 保险
        "prem_inc",
        "insur_prem_unearned",
        "tot_claim_exp",
        "prepay_surr",
        "chg_insur_cont_rsrv",
        # 证券
        "handling_chrg_comm_inc",
        "net_handling_chrg_comm_inc",
        "net_inc_sec_trading_brok_bus",
        "net_inc_sec_uw_bus",
        "net_inc_ec_asset_mgmt_bus",
    ],
    "cash_flow": [
        # 银行
        "net_incr_dep_cob",
        "net_incr_int_handling_chrg",
        "net_incr_loans_central_bank",
        "net_incr_dep_cbob",
        # 保险
        "cash_recp_prem_orig_inco",
        "cash_pay_claims_orig_inco",
        # 证券
        "handling_chrg_paid",
        "securitie_netcash_received",
        "melt_money_net_increase",
    ],
}


def upgrade() -> None:
    for table, fields in _FIN_FIELDS.items():
        for name in fields:
            op.add_column(
                table,
                sa.Column(
                    name,
                    sa.Float(),
                    nullable=True,
                    comment="金融企业专属字段",
                ),
            )


def downgrade() -> None:
    for table, fields in _FIN_FIELDS.items():
        for name in fields:
            op.drop_column(table, name)
