"""财务字段 → 数据库表映射 — Phase C 规则引擎."""

BALANCE_SHEET_FIELDS = {
    "acct_rcv", "oth_rcv", "inventories", "monetary_cap",
    "st_borrow", "lt_borrow", "bonds_payable", "tot_assets",
    "non_cur_liab_due_within_1y",
    "tot_cur_assets", "tot_cur_liab", "tot_liab",
    "tot_shrhldr_eqy_incl_min_int",
}

INCOME_STATEMENT_FIELDS = {
    "oper_rev", "tot_oper_rev", "less_oper_cost",
    "less_selling_dist_exp", "less_gerl_admin_exp", "less_fin_exp",
    "oper_profit", "tot_profit",
    "net_profit_excl_min_int_inc", "net_profit_after_ded_nr_lp",
}

CASH_FLOW_FIELDS = {
    "net_cash_flows_oper_act", "net_cash_flows_inv_act",
    "net_cash_flows_fnc_act", "free_cash_flow",
}

FIELD_TO_TABLE: dict[str, str] = {}
for f in BALANCE_SHEET_FIELDS:
    FIELD_TO_TABLE[f] = "balance_sheet"
for f in INCOME_STATEMENT_FIELDS:
    FIELD_TO_TABLE[f] = "income_statement"
for f in CASH_FLOW_FIELDS:
    FIELD_TO_TABLE[f] = "cash_flow"


def get_table(field_name: str) -> str:
    """返回字段所属的表名."""
    t = FIELD_TO_TABLE.get(field_name)
    if t is None:
        raise ValueError(f"未知字段: {field_name}")
    return t


def is_cumulative_field(field_name: str) -> bool:
    """判断是否为利润表/现金流表的累计值字段."""
    return field_name in INCOME_STATEMENT_FIELDS or field_name in CASH_FLOW_FIELDS
