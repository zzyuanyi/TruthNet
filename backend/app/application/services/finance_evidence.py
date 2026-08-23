"""财务规则证据共享构建 — ⑥/③ canonical Evidence（v3.4 方向 A）.

/finance 与 /comparisons 共用同一套证据 ID 生成与落库语义：

- **Evidence ID 与落库 field_path 都使用真实财务字段**（legacy evidence id
  解析出的字段名，如 ev_bs_acct_rcv_growth_20260331 → acct_rcv_growth）；
  canonical 身份六字段（source_type/source_record_id/field_path/period/
  dataset_version/company_code）自洽，可经 GET /evidence/{id} 回查；
- **builder 返回**：
    unique_drafts: dict[evidence_id, draft]   —— 同 ID 只落库一次；
    rule_evidence_map: dict[rule_id, list[evidence_id]] —— 规则 → 证据，
      同一 Evidence 可出现在多条规则（如营业收入被 R1/R4/R5/R7 共用），
      但只落库一次。调用方（/finance、/comparisons）通过 map 关联规则，
      **不再通过 field_path=rule_Rx 反查**；
- 历史缺陷记录（field_path=rule_Rx 的 ev_fin_*）由受控迁移脚本处理
  （scripts/migrate_finance_evidence.py，dry-run → 确认 → 修正）。
"""

from __future__ import annotations

from app.core.config import settings
from app.domain.provenance.id_factory import NS_FINANCE, make_evidence_id


def normalize_rule_evidence_id(
    legacy: str, wind_code: str, as_of: str, period: str | None = None
) -> str:
    """legacy evidence id（ev_bs_<field>_<period>）→ 统一 ID（finance 语义）。

    field_path = legacy 解析出的真实财务字段（方向 A）。

    8/23 双轨 ID 统一：/finance 路由与 agent 节点（/risk 链路）必须生成
    同一 ID——canonical 六段参数（无 rule_id 段：同一字段被多条规则
    引用时共享同一 Evidence，只落库一次）。period 显式传入时以实际
    报告期为准（agent 侧请求期可能晚于最新已披露报表），否则用请求期。
    """
    field = legacy
    if legacy.startswith("ev_"):
        parts = legacy.split("_")
        if len(parts) >= 3:
            field = "_".join(parts[2:]).removesuffix(f"_{as_of}")
    p = period or as_of
    return make_evidence_id(
        source_namespace=NS_FINANCE,
        source_type="financial_statement",
        source_record_id=f"{wind_code}|{p}",
        field_path=field or legacy,
        period=p,
        dataset_version=settings.DATASET_VERSION,
        company_code=wind_code,
    )


def legacy_field(legacy: str, as_of: str) -> str:
    """legacy evidence id → 真实财务字段名（与 ID 生成同解析）。"""
    field = legacy
    if legacy.startswith("ev_"):
        parts = legacy.split("_")
        if len(parts) >= 3:
            field = "_".join(parts[2:]).removesuffix(f"_{as_of}")
    return field or legacy


def display_period(period: str) -> str:
    """YYYYMMDD → YYYY-MM-DD（其余原样），用于人类可读的证据标题。"""
    p = str(period or "")
    if len(p) == 8 and p.isdigit():
        return f"{p[:4]}-{p[4:6]}-{p[6:]}"
    return p


def build_finance_rule_evidence_drafts(*, rules, wind_code: str, as_of: str) -> dict:
    """规则结果 → (unique_drafts, rule_evidence_map)。

    rules 为 evaluate_all_rules 输出（dict[R1..R7, RuleResult]）。
    - unique_drafts：evidence_id → draft（同 ID 只保留一份，跨规则共用
      legacy 只落库一次）；
    - rule_evidence_map：rule_id → [evidence_id, ...]（含共享 ID，
      每条规则详情可引用同一 Evidence）。
    """
    unique_drafts: dict[str, dict] = {}
    rule_evidence_map: dict[str, list[str]] = {}
    for rid, r in rules.items():
        if r is None:
            continue
        ev_ids: list[str] = []
        for legacy_ev in r.evidence_ids:
            eid = normalize_rule_evidence_id(legacy_ev, wind_code, as_of)
            ev_ids.append(eid)
            if eid in unique_drafts:
                continue  # 跨规则共用 legacy → 只落库一次
            unique_drafts[eid] = {
                "evidence_id": eid,
                "source_type": "financial_statement",
                "source_record_id": f"{wind_code}|{as_of}",
                "company_code": wind_code,
                "field_path": legacy_field(legacy_ev, as_of),
                "period": as_of,
                "statement_scope": "parent_company",
                # 来源标题可读性（演示整改）：规则中文名 + 期次 + 口径，
                # 避免"母公司报表 · 财务反欺诈规则 R1"整列同质化；
                # 必须保留"母公司报表"（test_parent_scope_consistency 断言）
                "source_title": (
                    f"{r.rule_name or rid} · {display_period(as_of)} · 母公司报表"
                ),
                "module": "finance",
                "source_table": "financial_statement",
            }
        rule_evidence_map[rid] = ev_ids
    return {"unique_drafts": unique_drafts, "rule_evidence_map": rule_evidence_map}
