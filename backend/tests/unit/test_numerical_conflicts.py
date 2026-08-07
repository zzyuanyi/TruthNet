"""深度数值冲突检测单元测试 — Phase D #2.

覆盖 CV-NUM-01 / CV-NUM-02：
- 正例（冲突命中）
- 反例（无冲突）
- 边界值
- 数据不足
- 报告期不一致
- 口径/来源缺失
- Evidence 缺失保护
"""

from app.domain.conflicts.numerical import (
    detect_ownership_consistency_conflict,
    detect_profit_cashflow_conflict,
    run_numerical_conflicts,
)

# ── CV-NUM-01 工具 ───────────────────────────────────────────


def _c1(*, profit, cash, periods, evidence=None, **kw):
    return detect_profit_cashflow_conflict(
        company_code="600518.SH",
        profit_values=profit,
        profit_periods=periods,
        cashflow_values=cash,
        cashflow_periods=periods,
        evidence_ids=evidence,
        **kw,
    )


def test_cv_num_01_conflict():
    """正例：连续 3 期净利润为正、现金流为负 → conflict。"""
    periods = ["2025Q4", "2026Q1", "2026Q2"]
    r = _c1(
        profit=[100.0, 120.0, 130.0],
        cash=[-50.0, -60.0, -70.0],
        periods=periods,
        evidence=["ev_fin_1", "ev_fin_2", "ev_fin_3"],
    )
    assert r.status == "conflict"
    assert r.conflict_type == "CV-NUM-01"
    assert r.severity == "red"  # 全正利润 + 全负现金流
    assert r.periods == periods
    assert r.evidence_ids == ["ev_fin_1", "ev_fin_2", "ev_fin_3"]
    assert r.alternative_explanation  # 有非舞弊解释


def test_cv_num_01_pass():
    """反例：净利润为正且现金流同步为正 → pass。"""
    periods = ["2025Q4", "2026Q1", "2026Q2"]
    r = _c1(profit=[100.0, 110.0, 120.0], cash=[80.0, 90.0, 100.0], periods=periods)
    assert r.status == "pass"
    assert r.severity == "green"


def test_cv_num_01_boundary_ratio():
    """边界：比值恰为阈值（0.5）→ 不触发（< 阈值才触发）。"""
    periods = ["2025Q4", "2026Q1", "2026Q2"]
    r = _c1(
        profit=[100.0, 100.0, 100.0],
        cash=[50.0, 50.0, 50.0],  # 比值 = 0.5 == 阈值 → 不背离
        periods=periods,
    )
    assert r.status == "pass"


def test_cv_num_01_below_threshold_triggers():
    """边界：比值 0.49 < 0.5 → 触发。"""
    periods = ["2025Q4", "2026Q1", "2026Q2"]
    r = _c1(
        profit=[100.0, 100.0, 100.0],
        cash=[49.0, 49.0, 49.0],
        periods=periods,
    )
    assert r.status == "conflict"


def test_cv_num_01_insufficient_periods():
    """数据不足：有效期数 < min_periods。"""
    periods = ["2026Q2"]
    r = _c1(profit=[100.0], cash=[-50.0], periods=periods)
    assert r.status == "insufficient_data"
    assert r.severity == "green"


def test_cv_num_01_period_mismatch():
    """报告期不一致：两表无重叠期间 → insufficient_data。"""
    r = detect_profit_cashflow_conflict(
        company_code="600518.SH",
        profit_values=[100.0, 110.0],
        profit_periods=["2025Q4", "2026Q1"],
        cashflow_values=[-50.0, -60.0],
        cashflow_periods=["2025Q1", "2025Q2"],  # 无重叠
    )
    assert r.status == "insufficient_data"
    assert "无重叠报告期" in r.explanation


def test_cv_num_01_missing_values_not_zero():
    """缺失值不按 0 处理：缺失期间跳过，不伪造背离。"""
    periods = ["2025Q4", "2026Q1", "2026Q2"]
    # 2026Q1 缺失 → 有效 2 期 < min 3 → insufficient（非按 0 编造冲突）
    r = _c1(
        profit=[100.0, None, 130.0],
        cash=[-50.0, -60.0, -70.0],
        periods=periods,
    )
    assert r.status == "insufficient_data"


def test_cv_num_01_negative_profit_not_flagged():
    """净利润为负时比值无意义：不把亏损期当背离。"""
    periods = ["2025Q4", "2026Q1", "2026Q2", "2026Q3"]
    # 利润正→正→负→负，现金流全负；只有 2 期利润正+现金流负 < 3 → pass
    r = _c1(
        profit=[100.0, 120.0, -30.0, -40.0],
        cash=[-10.0, -20.0, -5.0, -8.0],
        periods=periods,
    )
    assert r.status == "pass"


def test_cv_num_01_scope_fixed_parent():
    """口径：模式声明固定母公司报表，不混用合并报表。"""
    r = _c1(
        profit=[100.0, 110.0, 120.0],
        cash=[-50.0, -60.0, -70.0],
        periods=["2025Q4", "2026Q1", "2026Q2"],
    )
    assert "母公司报表口径" in r.limitations[0]


def test_cv_num_01_no_evidence_protected():
    """Evidence 缺失保护：无证据也可检测，但 evidence_ids 为空。"""
    r = _c1(
        profit=[100.0, 110.0, 120.0],
        cash=[-50.0, -60.0, -70.0],
        periods=["2025Q4", "2026Q1", "2026Q2"],
        evidence=None,
    )
    assert r.evidence_ids == []
    assert r.status == "conflict"


# ── CV-NUM-02 工具 ───────────────────────────────────────────


def _edges(**overrides):
    base = [
        {
            "entity_id": "E1",
            "owner_name": "股东甲",
            "mysql_pct": 30.0,
            "neo4j_pct": 30.0,
            "report_period": "2026Q1",
            "relationship_id": "rel_1",
        },
        {
            "entity_id": "E2",
            "owner_name": "股东乙",
            "mysql_pct": 25.0,
            "neo4j_pct": 40.0,  # 差 15pp > 1pp
            "report_period": "2026Q1",
            "relationship_id": "rel_2",
        },
    ]
    for e in base:
        e.update(overrides.get(e["entity_id"], {}))
    return base


def test_cv_num_02_conflict():
    """正例：MySQL 与 Neo4j 比例差超允许误差 → conflict。"""
    r = detect_ownership_consistency_conflict(
        company_code="600518.SH",
        shareholder_edges=_edges(),
        evidence_ids=["ev_eq_1", "ev_eq_2"],
    )
    assert r.status == "conflict"
    assert r.conflict_type == "CV-NUM-02"
    assert r.severity == "orange"
    assert len(r.details["mismatches"]) == 1
    assert r.evidence_ids == ["ev_eq_1", "ev_eq_2"]


def test_cv_num_02_pass():
    """反例：全部边比例在允许误差内。"""
    edges = [
        {
            "entity_id": "E1",
            "mysql_pct": 30.0,
            "neo4j_pct": 30.5,
            "report_period": "2026Q1",
        }
    ]
    r = detect_ownership_consistency_conflict(
        company_code="600518.SH", shareholder_edges=edges
    )
    assert r.status == "pass"


def test_cv_num_02_boundary_tolerance():
    """边界：差值恰为允许误差 → 不触发。"""
    edges = [
        {
            "entity_id": "E1",
            "mysql_pct": 30.0,
            "neo4j_pct": 31.0,  # 差 1.0 == tolerance 1.0 → 不触发（> 才触发）
            "report_period": "2026Q1",
        }
    ]
    r = detect_ownership_consistency_conflict(
        company_code="600518.SH", shareholder_edges=edges
    )
    assert r.status == "pass"


def test_cv_num_02_no_comparable_edges():
    """数据不足：无双来源数值边 → insufficient_data。"""
    edges = [
        {
            "entity_id": "E1",
            "mysql_pct": 30.0,
            "neo4j_pct": None,  # 图数据缺失
            "report_period": "2026Q1",
        }
    ]
    r = detect_ownership_consistency_conflict(
        company_code="600518.SH", shareholder_edges=edges
    )
    assert r.status == "insufficient_data"


def test_cv_num_02_no_guess_from_title():
    """不得从标题猜测百分比：无可验证数值时输出 limitations 明确说明。"""
    r = detect_ownership_consistency_conflict(
        company_code="600518.SH",
        shareholder_edges=[],
        event_context=[{"category": "增减持", "title": "关于股东增持的公告"}],
    )
    assert r.status == "insufficient_data"
    assert any("未从公告标题猜测百分比" in lim for lim in r.limitations)


def test_cv_num_02_event_context_explains():
    """事件作为时间差解释：同期有增减持 → alternative_explanation 提及。"""
    r = detect_ownership_consistency_conflict(
        company_code="600518.SH",
        shareholder_edges=_edges(),
        event_context=[{"category": "增减持", "title": "股东甲减持公告"}],
    )
    assert (
        "增减持" in r.alternative_explanation or "权益变动" in r.alternative_explanation
    )


def test_run_numerical_conflicts_all():
    """run_numerical_conflicts 返回恰好 2 种冻结模式。"""
    results = run_numerical_conflicts(
        company_code="600518.SH",
        profit_values=[100.0, 110.0, 120.0],
        profit_periods=["2025Q4", "2026Q1", "2026Q2"],
        cashflow_values=[-50.0, -60.0, -70.0],
        cashflow_periods=["2025Q4", "2026Q1", "2026Q2"],
        shareholder_edges=_edges(),
    )
    assert len(results) == 2
    assert {r.conflict_type for r in results} == {"CV-NUM-01", "CV-NUM-02"}
