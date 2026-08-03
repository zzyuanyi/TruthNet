"""Provenance 修复回归测试（2026-08-03）.

覆盖全量检查报告的 8 项断言：
  1. 无 rule_id 时 Evidence ID 与旧算法（基础六段）固定值一致
  2. 相同字段（oper_rev）不同规则（R1/R4）→ 不同 ID
  3. R1 Claim 不绑定 R4/R5 的证据（按规则归属绑定）
  4. R7 简化模式生成 Claim，且含净利润/营收/现金流证据
  5. Evidence value 是原始报表字段值（货币 unit=CNY），不含 explanation
  6. conflicting ID 令 ProvenanceValidationReport 为 issues 并产生 runtime warning
  7. demo 清理只删除无全局引用的 Evidence（保留其他会话引用）
  8. demo --url 远端模式禁止本地清理、--cleanup 必须带 --session-id
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "backend"))
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from app.agents.nodes.build_claims import build_claims_node  # noqa: E402
from app.agents.nodes.validate_evidence import validate_evidence_node  # noqa: E402
from app.agents.state import (  # noqa: E402
    AgentState,
    EvidenceRef,
    FinanceResult,
    ModuleResults,
)
from app.domain.provenance.id_factory import make_evidence_id  # noqa: E402

_SRC = "603180.SH|20260331|408006000"


def _mk_ev(
    eid: str,
    *,
    field: str = "oper_rev",
    value: str | None = None,
    rule_id: str | None = None,
    source_record_id: str = _SRC,
) -> EvidenceRef:
    return EvidenceRef(
        evidence_id=eid,
        source_type="financial_statement",
        source_record_id=source_record_id,
        field_path=field,
        period="20260331",
        value=value,
        module="finance",
        rule_id=rule_id,
    )


def _state_with_finance(finance: FinanceResult) -> AgentState:
    return AgentState(
        company=SimpleNamespace(sec_name="金牌家居", wind_code="603180.SH"),
        results=ModuleResults(finance=finance),
        runtime=SimpleNamespace(
            warnings=[], turn_id="t1", trace_id="tr1", session_id="s1"
        ),
    )


# ── 1. 无 rule_id 时 ID 与旧算法固定值一致 ──────────────
def test_no_rule_id_matches_legacy_fixed_value():
    eid = make_evidence_id(
        source_namespace="fin",
        source_type="financial_statement",
        source_record_id=_SRC,
        field_path="oper_rev",
        period="20260331",
        dataset_version="1.0.0",
        company_code="603180.SH",
    )
    # 基础六段固定值：一旦变化说明破坏了旧 ID 兼容（equity/events 依赖）
    assert eid == "ev_fin_6165430b84c54439"


# ── 2. 相同字段不同规则 → 不同 ID ────────────────────────
def test_same_field_different_rule_distinct_ids():
    kw = dict(
        source_namespace="fin",
        source_type="financial_statement",
        source_record_id=_SRC,
        field_path="oper_rev",
        period="20260331",
        dataset_version="1.0.0",
        company_code="603180.SH",
    )
    r1 = make_evidence_id(rule_id="R1", **kw)
    r4 = make_evidence_id(rule_id="R4", **kw)
    assert r1 != r4
    assert r1 == "ev_fin_7c6f1b9a9db3168a"
    assert r4 == "ev_fin_a8957f92a4b3f3bc"


# ── 3. R1 Claim 不绑定 R4/R5 证据 ────────────────────────
def test_r1_claim_binds_only_r1_evidence():
    finance = FinanceResult(
        rule_statuses={"R1": "triggered"},
        rule_details={
            "R1": {"evidence_ids": ["ev_r1_acct", "ev_r1_oper"]},
        },
        evidence=[
            _mk_ev("ev_r1_acct", field="acct_rcv", value="100", rule_id="R1"),
            _mk_ev("ev_r1_oper", field="oper_rev", value="200", rule_id="R1"),
            # R4/R5 同字段 oper_rev 的证据——不得混入 R1
            _mk_ev("ev_r4_oper", field="oper_rev", value="999", rule_id="R4"),
            _mk_ev("ev_r5_oper", field="oper_rev", value="888", rule_id="R5"),
        ],
    )
    claims = build_claims_node(_state_with_finance(finance))["claims"]
    assert len(claims) == 1
    assert claims[0].rule_id == "R1"
    assert set(claims[0].evidence_ids) == {"ev_r1_acct", "ev_r1_oper"}


# ── 4. R7 简化模式生成 Claim（含净利润/营收/现金流证据）──
def test_r7_simplified_mode_generates_claim():
    finance = FinanceResult(
        rule_statuses={"R7": "triggered"},
        rule_details={
            "R7": {"evidence_ids": ["ev_r7_np", "ev_r7_oper_rev", "ev_r7_oper_cf"]},
        },
        evidence=[
            _mk_ev("ev_r7_np", field="net_profit", value="100", rule_id="R7"),
            _mk_ev("ev_r7_oper_rev", field="oper_rev", value="200", rule_id="R7"),
            _mk_ev("ev_r7_oper_cf", field="oper", value="50", rule_id="R7"),
        ],
    )
    claims = build_claims_node(_state_with_finance(finance))["claims"]
    assert len(claims) == 1
    assert claims[0].rule_id == "R7"
    # 简化模式仅 3 个字段证据，不应因静态字段表（net_profit+core_profit）被跳过
    assert set(claims[0].evidence_ids) == {
        "ev_r7_np",
        "ev_r7_oper_rev",
        "ev_r7_oper_cf",
    }


# ── 5. Evidence value 是原始字段值（货币 unit=CNY）────────
def test_evidence_value_is_raw_field_value(monkeypatch):
    from app.agents.nodes import finance as finance_mod

    record = {"acct_rcv": 1234567890.5, "oper_rev": 987654321}
    monkeypatch.setattr(
        "app.application.services.source_resolver.resolve_source",
        lambda **kw: {"resolved": True, "record": record},
    )
    cache: dict = {}
    # 直接字段（acct_rcv）
    value, unit = finance_mod._field_value(cache, "balance_sheet", _SRC, "acct_rcv")
    assert value == "1234567890.5"
    assert unit == "CNY"
    # 别名字段（oper → net_cash_flows_oper_act）
    monkeypatch.setattr(
        "app.application.services.source_resolver.resolve_source",
        lambda **kw: {"resolved": True, "record": {"net_cash_flows_oper_act": -42}},
    )
    value, unit = finance_mod._field_value(cache, "cash_flow", _SRC, "oper")
    assert value == "-42"
    assert unit == "CNY"
    # 无法解析 → (None, None)，不回退 explanation
    monkeypatch.setattr(
        "app.application.services.source_resolver.resolve_source",
        lambda **kw: {"resolved": False, "record": {}},
    )
    value, unit = finance_mod._field_value({}, "balance_sheet", _SRC, "missing_field")
    assert value is None
    assert unit is None


# ── 6. conflicting ID → report issues + runtime warning ──
def test_conflicting_evidence_ids_yield_issues_warning():
    state = _state_with_finance(FinanceResult(rule_statuses={}))
    # validate_evidence_node 读 state["evidence"]（validate 在 build_claims 之后）
    state["evidence"] = [
        _mk_ev("ev_dup", field="acct_rcv", value="100"),
        _mk_ev("ev_dup", field="acct_rcv", value="200"),
    ]
    state["claims"] = []
    out = validate_evidence_node(state)
    report = out["provenance_report"]
    assert report.status == "issues"
    assert "ev_dup" in report.conflicting_ids
    assert any("冲突" in w for w in state["runtime"].warnings)


# ── 7. demo 清理只删无全局引用的 Evidence ────────────────
def test_demo_cleanup_keeps_externally_referenced_evidence():
    import demo_multi_turn

    # (evidence_id, 全局 link 引用数)：b 被其他会话引用 → 保留
    to_delete = demo_multi_turn._evids_to_delete(
        [("ev_a", 0), ("ev_b", 2), ("ev_c", 0)]
    )
    assert to_delete == ["ev_a", "ev_c"]


# ── 8. demo 清理参数校验 ─────────────────────────────────
def test_demo_cleanup_arg_validation():
    import demo_multi_turn

    # --url 远端模式禁止本地清理
    err = demo_multi_turn._validate_cleanup_args(
        SimpleNamespace(url="http://x", cleanup=True, session_id="s")
    )
    assert err and "远端模式禁止本地清理" in err
    # --cleanup 必须带 --session-id
    err = demo_multi_turn._validate_cleanup_args(
        SimpleNamespace(url="", cleanup=True, session_id="")
    )
    assert err and "需要指定 --session-id" in err
    # 合法组合 → None
    err = demo_multi_turn._validate_cleanup_args(
        SimpleNamespace(url="", cleanup=True, session_id="s")
    )
    assert err is None
