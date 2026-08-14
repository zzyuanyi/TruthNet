"""light_comparison_service 单元测试 — v3.3.3 收口批次 A/B。

覆盖（方案 §2.3/§2.4/§3.2/§3.3/§5.2）：
  - 共同期间交集（A Q1/Q2/Q3、B Q1/Q2 → Q2）；
  - explicit 期间不 fallback；
  - signed delta 恒 A-B，高/低前提不成立时纠正；
  - 三家/同码 fail closed（不抛异常、不截取前两家）；
  - 同主体两个相同 metric ID 拒绝；
  - 单位不兼容 / partial / insufficient。
"""

from decimal import Decimal

from app.agents.state import ComparisonSpec
from app.application.services.indicator_query_service import IndicatorQueryResult
from app.application.services.light_comparison_service import (
    compare_cross_company_facts,
    compare_cross_company_indicators,
    compare_same_company_indicators,
)

_LABELS = {
    "accounts_receivable_growth": "应收账款同比增速",
    "operating_revenue_growth": "营业收入同比增速",
    "r4_turnover_days": "存货周转天数",
    "inventories": "存货",
}


def _ok(metric_id, period="20250331", value=10.0, unit="percent", available=None):
    return IndicatorQueryResult(
        status="ok",
        indicator=metric_id,
        label=_LABELS.get(metric_id, metric_id),
        period=period,
        value=value,
        unit=unit,
        observations=[],
        available_periods=available if available is not None else [period],
    )


def _fail(metric_id):
    return IndicatorQueryResult(
        status="insufficient_data",
        indicator=metric_id,
        label=metric_id,
        available_periods=[],
    )


def _spec(ids, operation="difference", period_policy="latest_common_period"):
    return ComparisonSpec(
        scope="same_company_cross_indicator",
        mode="indicator",
        metric_ids=ids,
        operation=operation,
        period_policy=period_policy,
    )


# ── 同主体跨指标 ──────────────────────────────────────────────


def test_same_company_comparison_ok_higher(monkeypatch):
    """历史指标(12.5%) 比 当前指标(8.0%) 高 4.50 个百分点。"""
    monkeypatch.setattr(
        "app.application.services.light_comparison_service.query_metric",
        lambda code, mid, as_of="", require_exact_period=False: _ok(
            mid, value=12.5 if mid.endswith("receivable_growth") else 8.0
        ),
    )
    result = compare_same_company_indicators(
        "600518.SH",
        "康美药业",
        _spec(["accounts_receivable_growth", "operating_revenue_growth"]),
    )
    assert result.status == "ok"
    assert result.difference == Decimal("4.50")
    assert result.difference_unit == "个百分点"
    assert "高 4.50个百分点" in result.conclusion
    assert result.period == "20250331"
    assert len(result.participants) == 2


def test_same_company_comparison_ok_lower(monkeypatch):
    monkeypatch.setattr(
        "app.application.services.light_comparison_service.query_metric",
        lambda code, mid, as_of="", require_exact_period=False: _ok(
            mid, value=8.0 if mid.endswith("receivable_growth") else 12.5
        ),
    )
    result = compare_same_company_indicators(
        "600518.SH",
        "康美药业",
        _spec(["accounts_receivable_growth", "operating_revenue_growth"]),
    )
    assert result.status == "ok"
    assert result.difference == Decimal("-4.50")
    assert "低 4.50个百分点" in result.conclusion


def test_same_company_common_period_intersection(monkeypatch):
    """方案 §3.3 反例：A(metric1) 有 Q1/Q2/Q3，B(metric2) 有 Q1/Q2 → 选 Q2。"""

    def fake_query(code, mid, as_of="", require_exact_period=False):
        if mid.endswith("receivable_growth"):
            available = ["20240331", "20240630", "20240930"]
            period = as_of if require_exact_period else "20240930"
            return _ok(mid, period=period, value=12.5, available=available)
        available = ["20240331", "20240630"]
        period = as_of if require_exact_period else "20240630"
        return _ok(mid, period=period, value=8.0, available=available)

    monkeypatch.setattr(
        "app.application.services.light_comparison_service.query_metric",
        fake_query,
    )
    result = compare_same_company_indicators(
        "600518.SH",
        "康美药业",
        _spec(["accounts_receivable_growth", "operating_revenue_growth"]),
    )
    assert result.status == "ok"
    assert result.period == "20240630"  # 交集最新 = Q2，不是各算各的
    assert result.difference == Decimal("4.50")


def test_same_company_explicit_period_no_fallback(monkeypatch):
    """显式期不在交集 → insufficient（不 fallback 到其他期）。"""

    def fake_query(code, mid, as_of="", require_exact_period=False):
        if mid.endswith("receivable_growth"):
            return _ok(
                mid, period=as_of or "20240930", available=["20240630", "20240930"]
            )
        return _ok(mid, period=as_of or "20240630", available=["20240331", "20240630"])

    monkeypatch.setattr(
        "app.application.services.light_comparison_service.query_metric",
        fake_query,
    )
    result = compare_same_company_indicators(
        "600518.SH",
        "康美药业",
        _spec(
            ["accounts_receivable_growth", "operating_revenue_growth"],
            period_policy="explicit_period",
        ),
        as_of="20240930",
    )
    assert result.status == "insufficient_data"
    assert "无共同可计算期间" in result.warnings[0]


def test_same_company_duplicate_metric_ids_rejected():
    """方案 §3.2：两个相同 metric ID 不得构成跨指标比较。"""
    result = compare_same_company_indicators(
        "600518.SH",
        "康美药业",
        _spec(["r4_turnover_days", "r4_turnover_days"]),
    )
    assert result.status == "insufficient_data"
    assert any("两个不同指标" in w for w in result.warnings)


def test_unit_mismatch_returns_unsupported(monkeypatch):
    """金额 vs 比例不得计算差值。"""
    monkeypatch.setattr(
        "app.application.services.light_comparison_service.query_metric",
        lambda code, mid, as_of="", require_exact_period=False: _ok(
            mid,
            value=1.0e8 if mid == "inventories" else 12.5,
            unit="CNY" if mid == "inventories" else "percent",
        ),
    )
    result = compare_same_company_indicators(
        "600518.SH",
        "康美药业",
        _spec(["inventories", "accounts_receivable_growth"]),
    )
    assert result.status == "unsupported"
    assert "单位不兼容" in result.warnings[0]


def test_partial_one_side_missing(monkeypatch):
    """exact 重查一侧失败 → partial，不声称高低。"""
    monkeypatch.setattr(
        "app.application.services.light_comparison_service.query_metric",
        lambda code, mid, as_of="", require_exact_period=False: (
            _fail(mid)
            if require_exact_period and mid.endswith("receivable_growth")
            else _ok(mid, value=12.5)
        ),
    )
    result = compare_same_company_indicators(
        "600518.SH",
        "康美药业",
        _spec(["accounts_receivable_growth", "operating_revenue_growth"]),
    )
    assert result.status == "partial"
    assert result.difference is None


def test_both_sides_missing_returns_insufficient(monkeypatch):
    monkeypatch.setattr(
        "app.application.services.light_comparison_service.query_metric",
        lambda code, mid, as_of="", require_exact_period=False: _fail(mid),
    )
    result = compare_same_company_indicators(
        "600518.SH",
        "康美药业",
        _spec(["accounts_receivable_growth", "operating_revenue_growth"]),
    )
    assert result.status == "insufficient_data"
    assert result.participants == []


def test_wrong_scope_fails_closed():
    result = compare_same_company_indicators(
        "600518.SH",
        "康美药业",
        ComparisonSpec(scope="cross_company", mode="indicator", metric_ids=["a", "b"]),
    )
    assert result.status == "insufficient_data"
    assert any("恰好两家" in w for w in result.warnings)


# ── 跨公司轻量比较（方案 §2.3/§2.4）─────────────────────────


def _ref(code: str, name: str, listing: str | None = None):
    from app.agents.state import CompanyRef

    return CompanyRef(
        entity_id=f"company_{code.replace('.', '_')}",
        wind_code=code,
        sec_name=name,
        exchange="XSHG",
        listing_date=listing,
    )


def _cross_spec(mode="indicator", **kwargs):
    return ComparisonSpec(scope="cross_company", mode=mode, **kwargs)


def test_cross_company_indicator_less_than_fact_holds(monkeypatch):
    """官方原题：伊利(100天) 比 双汇(110天) → delta=-10，前提成立答「低」。"""
    monkeypatch.setattr(
        "app.application.services.light_comparison_service.query_metric",
        lambda code, mid, as_of="", require_exact_period=False: _ok(
            mid,
            period="20241231",
            value=100.0 if code == "600887.SH" else 110.0,
            unit="days",
        ),
    )
    result = compare_cross_company_indicators(
        [_ref("600887.SH", "伊利股份"), _ref("000895.SZ", "双汇发展")],
        _cross_spec(metric_ids=["r4_turnover_days"], operation="less_than"),
    )
    assert result.status == "ok"
    assert result.difference == Decimal("-10")  # 恒 A-B
    assert "低 10.00天" in result.conclusion


def test_cross_company_less_than_premise_false_corrects(monkeypatch):
    """方案 §2.3 反事实：问「A 比 B 低多少」但 A=120 > B=100 → 明确纠正。"""
    monkeypatch.setattr(
        "app.application.services.light_comparison_service.query_metric",
        lambda code, mid, as_of="", require_exact_period=False: _ok(
            mid, value=120.0 if code == "600887.SH" else 100.0, unit="days"
        ),
    )
    result = compare_cross_company_indicators(
        [_ref("600887.SH", "伊利股份"), _ref("000895.SZ", "双汇发展")],
        _cross_spec(metric_ids=["r4_turnover_days"], operation="less_than"),
    )
    assert result.status == "ok"
    assert result.difference == Decimal("20")
    assert "并不低，反而高 20.00天" in result.conclusion


def test_cross_company_greater_than_premise_false_corrects(monkeypatch):
    """问「A 比 B 高多少」但 A=60 < B=62 → 明确纠正。"""
    monkeypatch.setattr(
        "app.application.services.light_comparison_service.query_metric",
        lambda code, mid, as_of="", require_exact_period=False: _ok(
            mid, value=60.0 if code == "600519.SH" else 62.0
        ),
    )
    result = compare_cross_company_indicators(
        [_ref("600519.SH", "贵州茅台"), _ref("000858.SZ", "五粮液")],
        _cross_spec(metric_ids=["r5_gross_margin"], operation="greater_than"),
    )
    assert result.status == "ok"
    assert result.difference == Decimal("-2")
    assert "并不高，反而低 2.00个百分点" in result.conclusion


def test_cross_company_common_period_intersection(monkeypatch):
    """方案 §3.3：A 最新 Q3、B 最新 Q2、双方均有 Q2 → 选 Q2。"""

    def fake_query(code, mid, as_of="", require_exact_period=False):
        if code == "600887.SH":
            return _ok(
                mid,
                period=as_of or "20240930",
                value=100.0,
                unit="days",
                available=["20240331", "20240630", "20240930"],
            )
        return _ok(
            mid,
            period=as_of or "20240630",
            value=110.0,
            unit="days",
            available=["20240331", "20240630"],
        )

    monkeypatch.setattr(
        "app.application.services.light_comparison_service.query_metric",
        fake_query,
    )
    result = compare_cross_company_indicators(
        [_ref("600887.SH", "伊利股份"), _ref("000895.SZ", "双汇发展")],
        _cross_spec(metric_ids=["r4_turnover_days"], operation="difference"),
    )
    assert result.status == "ok"
    assert result.period == "20240630"


def test_cross_company_no_common_period(monkeypatch):
    monkeypatch.setattr(
        "app.application.services.light_comparison_service.query_metric",
        lambda code, mid, as_of="", require_exact_period=False: _ok(
            mid,
            period="20250331" if code == "600519.SH" else "20241231",
            available=["20250331"] if code == "600519.SH" else ["20241231"],
        ),
    )
    result = compare_cross_company_indicators(
        [_ref("600519.SH", "贵州茅台"), _ref("000858.SZ", "五粮液")],
        _cross_spec(metric_ids=["r5_gross_margin"]),
    )
    assert result.status == "insufficient_data"
    assert "无共同可计算期间" in result.warnings[0]


def test_cross_company_three_companies_fail_closed():
    """方案 §2.4：三家公司不抛异常、不静默截取前两家。"""
    result = compare_cross_company_indicators(
        [
            _ref("600519.SH", "贵州茅台"),
            _ref("000858.SZ", "五粮液"),
            _ref("600887.SH", "伊利股份"),
        ],
        _cross_spec(metric_ids=["r5_gross_margin"]),
    )
    assert result.status == "insufficient_data"
    assert result.participants == []
    assert any("恰好两家" in w for w in result.warnings)


def test_cross_company_duplicate_code_dedup_ok(monkeypatch):
    """同码重复先去重再比较（恰好两家后正常执行）。"""
    monkeypatch.setattr(
        "app.application.services.light_comparison_service.query_metric",
        lambda code, mid, as_of="", require_exact_period=False: _ok(
            mid, value=62.0 if code == "600519.SH" else 60.0
        ),
    )
    result = compare_cross_company_indicators(
        [
            _ref("600519.SH", "贵州茅台"),
            _ref("600519.SH", "贵州茅台"),
            _ref("000858.SZ", "五粮液"),
        ],
        _cross_spec(metric_ids=["r5_gross_margin"], operation="greater_than"),
    )
    assert result.status == "ok"
    assert result.difference == Decimal("2")


def test_cross_company_illegal_single_participant():
    result = compare_cross_company_indicators(
        [_ref("600519.SH", "贵州茅台")],
        _cross_spec(metric_ids=["r5_gross_margin"]),
    )
    assert result.status == "insufficient_data"
    assert any("恰好两家" in w for w in result.warnings)


# ── 公司事实比较 ──────────────────────────────────────────────


def test_cross_company_facts_listing_date_earlier():
    result = compare_cross_company_facts(
        [
            _ref("600028.SH", "中国石化", listing="2001-08-08"),
            _ref("601857.SH", "中国石油", listing="2007-11-05"),
        ],
        _cross_spec(
            mode="company_fact",
            fact_key="listing_date",
            operation="earlier_than",
            period_policy="not_applicable",
        ),
    )
    assert result.status == "ok"
    assert "早约" in result.conclusion
    assert "2001-08-08" in result.conclusion


def test_cross_company_facts_one_missing_partial():
    result = compare_cross_company_facts(
        [
            _ref("600028.SH", "中国石化", listing="2001-08-08"),
            _ref("601857.SH", "中国石油", listing=None),
        ],
        _cross_spec(
            mode="company_fact",
            fact_key="listing_date",
            operation="earlier_than",
            period_policy="not_applicable",
        ),
    )
    assert result.status == "partial"
    assert "中国石油" in result.warnings[0]


def test_cross_company_facts_three_companies_fail_closed():
    result = compare_cross_company_facts(
        [
            _ref("600028.SH", "中国石化", listing="2001-08-08"),
            _ref("601857.SH", "中国石油", listing="2007-11-05"),
            _ref("600519.SH", "贵州茅台", listing="2001-08-27"),
        ],
        _cross_spec(
            mode="company_fact",
            fact_key="listing_date",
            operation="earlier_than",
            period_policy="not_applicable",
        ),
    )
    assert result.status == "insufficient_data"
    assert any("恰好两家" in w for w in result.warnings)


# ── 窄风险比较（方案 §3.7）───────────────────────────────────


def _risk_spec():
    return ComparisonSpec(scope="cross_company", mode="risk")


def test_cross_company_risk_known_two_sides(monkeypatch):
    """两侧已知等级 → 按等级排序回答谁风险更高。"""
    from app.application.services.light_comparison_service import (
        compare_cross_company_risk,
    )

    monkeypatch.setattr(
        "app.application.services.indicator_query_service."
        "query_latest_risk_assessment",
        lambda code: {
            "level": "high" if code == "600518.SH" else "low",
            "overall_score": 0.8 if code == "600518.SH" else 0.2,
            "rule_version": "v3",
            "dataset_version": "competition-2026",
            "assessed_at": "2026-08-14T00:00:00",
        },
    )
    result = compare_cross_company_risk(
        [_ref("600518.SH", "康美药业"), _ref("600519.SH", "贵州茅台")],
        _risk_spec(),
    )
    assert result.status == "ok"
    assert "高于贵州茅台" in result.conclusion
    assert result.difference is None  # 等级不换算成分值差


def test_cross_company_risk_one_side_missing_partial(monkeypatch):
    from app.application.services.light_comparison_service import (
        compare_cross_company_risk,
    )

    monkeypatch.setattr(
        "app.application.services.indicator_query_service."
        "query_latest_risk_assessment",
        lambda code: (
            {
                "level": "high",
                "overall_score": 0.8,
                "rule_version": "v3",
                "dataset_version": "competition-2026",
                "assessed_at": "2026-08-14T00:00:00",
            }
            if code == "600518.SH"
            else None
        ),
    )
    result = compare_cross_company_risk(
        [_ref("600518.SH", "康美药业"), _ref("600519.SH", "贵州茅台")],
        _risk_spec(),
    )
    assert result.status == "partial"
    assert "贵州茅台" in result.warnings[0]


def test_cross_company_risk_version_mismatch_partial(monkeypatch):
    """两侧规则集/数据版本不一致 → partial，不比较。"""
    from app.application.services.light_comparison_service import (
        compare_cross_company_risk,
    )

    monkeypatch.setattr(
        "app.application.services.indicator_query_service."
        "query_latest_risk_assessment",
        lambda code: {
            "level": "high",
            "overall_score": 0.8,
            "rule_version": "v3" if code == "600518.SH" else "v2",
            "dataset_version": "competition-2026",
            "assessed_at": "2026-08-14T00:00:00",
        },
    )
    result = compare_cross_company_risk(
        [_ref("600518.SH", "康美药业"), _ref("600519.SH", "贵州茅台")],
        _risk_spec(),
    )
    assert result.status == "partial"
    assert "口径不一致" in result.warnings[0]


def test_cross_company_risk_unknown_level_partial(monkeypatch):
    from app.application.services.light_comparison_service import (
        compare_cross_company_risk,
    )

    monkeypatch.setattr(
        "app.application.services.indicator_query_service."
        "query_latest_risk_assessment",
        lambda code: {
            "level": "unknown",
            "overall_score": None,
            "rule_version": "v3",
            "dataset_version": "competition-2026",
            "assessed_at": "2026-08-14T00:00:00",
        },
    )
    result = compare_cross_company_risk(
        [_ref("600518.SH", "康美药业"), _ref("600519.SH", "贵州茅台")],
        _risk_spec(),
    )
    assert result.status == "partial"
    assert "等级未知" in result.warnings[0]


def test_cross_company_risk_level_order_from_domain_contract(monkeypatch):
    """方案 §5 D1：排序常量来自领域模块（测试与服务共用同一来源）。"""
    from app.application.services.light_comparison_service import (
        compare_cross_company_risk,
    )
    from app.domain.risk.assessment_levels import (
        RISK_LEVEL_LABELS,
        RISK_LEVEL_ORDER,
    )

    assert RISK_LEVEL_ORDER["critical"] > RISK_LEVEL_ORDER["none"]
    assert list(RISK_LEVEL_ORDER) == ["none", "low", "medium", "high", "critical"]
    assert set(RISK_LEVEL_LABELS) == set(RISK_LEVEL_ORDER)
    # critical vs none：A（严重）高于 B（无）
    monkeypatch.setattr(
        "app.application.services.indicator_query_service."
        "query_latest_risk_assessment",
        lambda code: {
            "level": "critical" if code == "600518.SH" else "none",
            "overall_score": 0.95 if code == "600518.SH" else 0.0,
            "rule_version": "v3",
            "dataset_version": "competition-2026",
            "assessed_at": "2026-08-14T00:00:00",
        },
    )
    result = compare_cross_company_risk(
        [_ref("600518.SH", "康美药业"), _ref("600519.SH", "贵州茅台")],
        _risk_spec(),
    )
    assert result.status == "ok"
    assert "严重" in result.conclusion
    assert "高于贵州茅台" in result.conclusion


def test_cross_company_risk_explicit_as_of_unsupported(monkeypatch):
    """方案 §5 D2：显式历史 as_of → unsupported，且不得查询数据库。"""
    from app.application.services.light_comparison_service import (
        compare_cross_company_risk,
    )

    def _fail_if_called(code):  # noqa: ANN202
        raise AssertionError("as_of 分支不得触发风险评估查询")

    monkeypatch.setattr(
        "app.application.services.indicator_query_service."
        "query_latest_risk_assessment",
        _fail_if_called,
    )
    result = compare_cross_company_risk(
        [_ref("600518.SH", "康美药业"), _ref("600519.SH", "贵州茅台")],
        _risk_spec(),
        as_of="20241231",
    )
    assert result.status == "unsupported"
    assert any("as_of=20241231" in w for w in result.warnings)
    assert any("仅支持最新风险评估" in w for w in result.warnings)


# ── v3.3.4 收口复核清单 §2.5/§4：成功 DTO 统一回填 requested_scope ──────


def test_same_company_ok_result_carries_requested_scope(monkeypatch):
    """清单 §4.1：同主体比较成功 DTO.requested_scope == spec.requested_scope。"""
    monkeypatch.setattr(
        "app.application.services.light_comparison_service.query_metric",
        lambda code, mid, as_of="", require_exact_period=False: _ok(
            mid, value=12.5 if mid.endswith("receivable_growth") else 8.0
        ),
    )
    spec = ComparisonSpec(
        scope="same_company_cross_indicator",
        mode="indicator",
        requested_scope="indicator",
        metric_ids=["accounts_receivable_growth", "operating_revenue_growth"],
        operation="difference",
    )
    result = compare_same_company_indicators("600518.SH", "康美药业", spec)
    assert result.status == "ok"
    assert result.requested_scope == "indicator"


def test_cross_indicator_ok_result_carries_requested_scope(monkeypatch):
    monkeypatch.setattr(
        "app.application.services.light_comparison_service.query_metric",
        lambda code, mid, as_of="", require_exact_period=False: _ok(
            mid, period="20241231", value=100.0 if code == "600887.SH" else 110.0
        ),
    )
    spec = _cross_spec(
        metric_ids=["r4_turnover_days"],
        operation="less_than",
        requested_scope="indicator",
    )
    result = compare_cross_company_indicators(
        [_ref("600887.SH", "伊利股份"), _ref("000895.SZ", "双汇发展")], spec
    )
    assert result.status == "ok"
    assert result.requested_scope == "indicator"


def test_overview_ok_result_carries_requested_scope(monkeypatch):
    from app.application.services.light_comparison_service import (
        compare_cross_company_overview,
    )

    def fake(code, mid, as_of="", require_exact_period=False):
        return _ok(mid, value=10.0, unit="percent", available=["20241231", "20250331"])

    monkeypatch.setattr(
        "app.application.services.light_comparison_service.query_metric", fake
    )
    spec = _cross_spec(mode="overview", requested_scope="full")
    result = compare_cross_company_overview(
        [_ref("600519.SH", "贵州茅台"), _ref("600518.SH", "康美药业")], spec
    )
    assert result.requested_scope == "full"
    assert result.comparison_mode == "overview"


def test_risk_ok_result_carries_requested_scope(monkeypatch):
    from app.application.services.light_comparison_service import (
        compare_cross_company_risk,
    )

    monkeypatch.setattr(
        "app.application.services.indicator_query_service."
        "query_latest_risk_assessment",
        lambda code: {
            "level": "high" if code == "600518.SH" else "low",
            "overall_score": 0.8 if code == "600518.SH" else 0.2,
            "rule_version": "v3",
            "dataset_version": "competition-2026",
            "assessed_at": "2026-08-14T00:00:00",
        },
    )
    spec = ComparisonSpec(scope="cross_company", mode="risk", requested_scope="risk")
    result = compare_cross_company_risk(
        [_ref("600518.SH", "康美药业"), _ref("600519.SH", "贵州茅台")], spec
    )
    assert result.status == "ok"
    assert result.requested_scope == "risk"


def test_facts_ok_result_carries_requested_scope():
    spec = ComparisonSpec(
        scope="cross_company",
        mode="company_fact",
        requested_scope="company_fact",
        fact_key="listing_date",
        operation="earlier_than",
        period_policy="not_applicable",
    )
    result = compare_cross_company_facts(
        [
            _ref("600028.SH", "中国石化", listing="2001-08-08"),
            _ref("601857.SH", "中国石油", listing="2007-11-05"),
        ],
        spec,
    )
    assert result.status == "ok"
    assert result.requested_scope == "company_fact"
    # 恒 A-B：石化比石油早 → 正天数
    from datetime import date as _date

    assert result.difference == Decimal(
        str((_date(2007, 11, 5) - _date(2001, 8, 8)).days)
    )
    assert result.difference > 0
