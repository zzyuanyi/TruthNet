"""v3.3.4 轻量整体概览对比测试 — 方案 §7.1 矩阵。

覆盖：服务端 profile 校验、共同期间/显式期、逐行 partial、期间不一致
不计算差值、difference 恒 primary-peer、claims/evidence 只为成功行
生成、三主体/单主体/外部 metric_ids 被 verifier 拒绝。
"""

from decimal import Decimal

from app.agents.state import ComparisonSpec, validate_comparison_spec
from app.application.services.indicator_query_service import (
    IndicatorQueryResult,
    supported_indicator_ids,
)
from app.application.services.light_comparison_service import (
    OVERVIEW_METRIC_IDS,
    OverviewMetricRow,
    compare_cross_company_overview,
)

_METRIC_VALUES = {
    "operating_revenue_growth": (12.5, 8.0, "percent"),
    "r5_gross_margin": (91.0, 75.0, "percent"),
    "r4_turnover_days": (1200.0, 900.0, "days"),
    "debt_to_assets": (30.0, 45.0, "percent"),
    "operating_cash_flow": (5.0e9, 3.0e9, "CNY"),
}


def _ok(
    metric_id,
    code,
    period="20250331",
    value=10.0,
    unit="percent",
    available=None,
    require_exact_period=False,
    as_of="",
):
    return IndicatorQueryResult(
        status="ok",
        indicator=metric_id,
        label=metric_id,
        period=period,
        value=value,
        unit=unit,
        observations=[],
        available_periods=available if available is not None else [period],
    )


def _ref(code, name):
    from app.agents.state import CompanyRef

    return CompanyRef(
        entity_id=f"company_{code.replace('.', '_')}",
        wind_code=code,
        sec_name=name,
        exchange="XSHG",
    )


def _spec(
    mode="overview",
    period_policy="latest_common_period",
    requested_scope="overview",
    **kw,
):
    return ComparisonSpec(
        scope="cross_company",
        mode=mode,
        requested_scope=requested_scope,
        period_policy=period_policy,
        **kw,
    )


def _two_refs():
    return [_ref("600519.SH", "贵州茅台"), _ref("600518.SH", "康美药业")]


def test_overview_profile_ids_all_supported():
    """方案 §3.2：固定 profile 每个 ID 都属于受支持集合，不复制新公式。"""
    supported = supported_indicator_ids()
    for metric_id in OVERVIEW_METRIC_IDS:
        assert metric_id in supported, f"{metric_id} 不在受支持集合"
    assert len(OVERVIEW_METRIC_IDS) == 5


def test_validate_overview_requires_two_distinct_codes():
    assert validate_comparison_spec(_spec(), ["600519.SH", "600518.SH"]) == []
    assert any(
        "恰好两家" in issue
        for issue in validate_comparison_spec(_spec(), ["600519.SH"])
    )
    assert any(
        "恰好两家" in issue
        for issue in validate_comparison_spec(
            _spec(), ["600519.SH", "600518.SH", "000858.SZ"]
        )
    )
    assert any(
        "恰好两家" in issue
        for issue in validate_comparison_spec(_spec(), ["600519.SH", "600519.SH"])
    )


def test_validate_overview_rejects_external_metric_ids_and_fact_key():
    assert any(
        "不得携带外部 metric_ids" in issue
        for issue in validate_comparison_spec(
            _spec(metric_ids=["r5_gross_margin"]), ["600519.SH", "600518.SH"]
        )
    )
    assert any(
        "不得携带 fact_key" in issue
        for issue in validate_comparison_spec(
            _spec(fact_key="listing_date"), ["600519.SH", "600518.SH"]
        )
    )


def test_validate_overview_rejects_same_company_scope():
    issues = validate_comparison_spec(
        ComparisonSpec(scope="same_company_cross_indicator", mode="overview"),
        ["600519.SH"],
    )
    assert issues


def _fake_query_all_ok(require_shift_period=None):
    def fake(code, mid, as_of="", require_exact_period=False):
        value, unit = _METRIC_VALUES[mid][0], _METRIC_VALUES[mid][2]
        if code == "600518.SH":
            value = _METRIC_VALUES[mid][1]
        period = "20250331"
        if (
            require_shift_period
            and require_exact_period
            and code in require_shift_period
        ):
            period = "20241231"
        return _ok(
            mid,
            code,
            period=period,
            value=value,
            unit=unit,
            available=["20241231", "20250331"],
        )

    return fake


def test_overview_happy_path_all_five_rows(monkeypatch):
    monkeypatch.setattr(
        "app.application.services.light_comparison_service.query_metric",
        _fake_query_all_ok(),
    )
    result = compare_cross_company_overview(_two_refs(), _spec())
    assert result.status == "ok"
    assert result.comparison_mode == "overview"
    assert len(result.overview_rows) == 5
    ok_rows = [r for r in result.overview_rows if r.status == "ok"]
    assert len(ok_rows) == 5
    # difference 恒 primary(茅台) - peer(康美)
    margin = next(r for r in ok_rows if r.metric_id == "r5_gross_margin")
    assert margin.difference == Decimal("16.0")  # 91.0 - 75.0
    assert margin.period == "20250331"
    assert "已成功比较 5/5 个维度" in result.conclusion


def test_overview_one_metric_missing_others_unaffected(monkeypatch):
    def fake(code, mid, as_of="", require_exact_period=False):
        if mid == "r4_turnover_days":
            return IndicatorQueryResult(
                status="insufficient_data",
                indicator=mid,
                label="存货周转天数",
                available_periods=[],
            )
        value, unit = _METRIC_VALUES[mid][0], _METRIC_VALUES[mid][2]
        if code == "600518.SH":
            value = _METRIC_VALUES[mid][1]
        return _ok(
            mid,
            code,
            value=value,
            unit=unit,
            available=["20241231", "20250331"],
        )

    monkeypatch.setattr(
        "app.application.services.light_comparison_service.query_metric", fake
    )
    result = compare_cross_company_overview(_two_refs(), _spec())
    assert result.status == "ok"
    ok_rows = [r for r in result.overview_rows if r.status == "ok"]
    missing = [r for r in result.overview_rows if r.status == "insufficient_data"]
    assert len(ok_rows) == 4
    assert [r.metric_id for r in missing] == ["r4_turnover_days"]
    assert missing[0].difference is None
    assert "已成功比较 4/5 个维度" in result.conclusion
    assert "存货周转天数" in result.conclusion  # 缺失维度如实披露


def test_overview_period_mismatch_no_difference(monkeypatch):
    """方案 §5.2：exact 重查期间不一致 → 该行 insufficient，不算差值。"""
    monkeypatch.setattr(
        "app.application.services.light_comparison_service.query_metric",
        _fake_query_all_ok(require_shift_period={"600518.SH"}),
    )
    result = compare_cross_company_overview(_two_refs(), _spec())
    bad = [r for r in result.overview_rows if r.status != "ok"]
    # 康美 exact 重查期间偏移 → 每行都只有一侧可对齐 → 全部 insufficient
    assert all(r.difference is None for r in result.overview_rows)
    assert result.status == "insufficient_data"
    assert bad


def test_overview_no_common_period_structured_insufficient(monkeypatch):
    def fake(code, mid, as_of="", require_exact_period=False):
        available = ["20250331"] if code == "600519.SH" else ["20241231"]
        value, unit = _METRIC_VALUES[mid][0], _METRIC_VALUES[mid][2]
        return _ok(mid, code, value=value, unit=unit, available=available)

    monkeypatch.setattr(
        "app.application.services.light_comparison_service.query_metric", fake
    )
    result = compare_cross_company_overview(_two_refs(), _spec())
    assert result.status == "insufficient_data"
    assert len(result.overview_rows) == 5
    assert all(r.status == "insufficient_data" for r in result.overview_rows)
    assert all("无共同可计算期间" in r.warnings[0] for r in result.overview_rows)


def test_overview_explicit_period_exact_only(monkeypatch):
    """显式期必须双方交集内精确命中，不 fallback 其他期间。"""

    def fake(code, mid, as_of="", require_exact_period=False):
        value, unit = _METRIC_VALUES[mid][0], _METRIC_VALUES[mid][2]
        if code == "600518.SH":
            value = _METRIC_VALUES[mid][1]
        if mid == "r5_gross_margin":
            available = ["20240630", "20250331"]
        else:
            available = ["20241231", "20250331"]
        if require_exact_period:
            period = as_of if as_of in available else "20250331"
        else:
            period = "20250331"
        return _ok(
            mid, code, period=period, value=value, unit=unit, available=available
        )

    monkeypatch.setattr(
        "app.application.services.light_comparison_service.query_metric", fake
    )
    spec = _spec(period_policy="explicit_period")
    result = compare_cross_company_overview(_two_refs(), spec, as_of="20240630")
    ok_rows = [r for r in result.overview_rows if r.status == "ok"]
    assert ok_rows  # 双方都有 20240630 的维度成功
    assert all(r.period == "20240630" for r in ok_rows)
    assert len(ok_rows) < 5  # 其他维度双方交集为 20250331，显式期不 fallback


def test_overview_unsupported_metric_id_row_marked(monkeypatch):
    """profile 校验：不在受支持集合的 ID → 该行 unsupported，不查询。"""
    from app.application.services.light_comparison_service import (
        _overview_row_for_metric,
    )

    def _boom(*a, **kw):
        raise AssertionError("unsupported ID 不得发起查询")

    monkeypatch.setattr(
        "app.application.services.light_comparison_service.query_metric", _boom
    )
    row = _overview_row_for_metric(_two_refs(), "bogus_metric", _spec(), as_of="")
    assert row.status == "unsupported"
    assert any("不在受支持集合" in w for w in row.warnings)


def test_generate_answer_overview_claims_only_for_ok_rows(monkeypatch):
    """方案 §5.3/§7.1-13：claims/evidence 只为成功行生成，缺失行不伪造。"""
    from app.application.services.light_comparison_service import (
        ComparisonValue,
        LightComparisonResult,
    )
    from app.agents.nodes import generate_answer as ga

    rows = [
        OverviewMetricRow(
            metric_id="r5_gross_margin",
            metric_label="毛利率",
            status="ok",
            unit="percent",
            period="20250331",
            values=[
                ComparisonValue(
                    company_code="600519.SH",
                    sec_name="贵州茅台",
                    metric_id="r5_gross_margin",
                    metric_label="毛利率",
                    period="20250331",
                    value=Decimal("91.0"),
                    unit="percent",
                ),
                ComparisonValue(
                    company_code="600518.SH",
                    sec_name="康美药业",
                    metric_id="r5_gross_margin",
                    metric_label="毛利率",
                    period="20250331",
                    value=Decimal("75.0"),
                    unit="percent",
                ),
            ],
            difference=Decimal("16.0"),
            difference_unit="个百分点",
            conclusion="贵州茅台比康美药业高 16.00个百分点",
        ),
        OverviewMetricRow(
            metric_id="r4_turnover_days",
            metric_label="存货周转天数",
            status="insufficient_data",
            warnings=["双方无共同可计算期间"],
        ),
    ]
    fake_result = LightComparisonResult(
        status="partial",
        scope="cross_company",
        operation="difference",
        comparison_mode="overview",
        overview_rows=rows,
        conclusion="已成功比较 1/2 个维度。\n存货周转天数因数据不足无法比较。",
    )
    monkeypatch.setattr(
        "app.application.services.light_comparison_service."
        "compare_cross_company_overview",
        lambda participants, spec, as_of="": fake_result,
    )
    # values 为空 → evidence 为空；claims 只按 ok 行生成（1 条）
    state = {
        "comparison_targets": _two_refs(),
        "runtime": object(),
    }
    spec = _spec()
    out = ga._answer_cross_company_overview(state, _two_refs(), spec)
    assert len(out["claims"]) == 1
    assert out["claims"][0].claim_type == "overview_comparison"
    assert "存货周转天数" not in out["claims"][0].text
    assert out["light_comparison"]["comparison_mode"] == "overview"
    assert len(out["light_comparison"]["overview_rows"]) == 2
    assert "1/2" in out["final_response"].answer


# ── v3.3.4 Preview First 修订（方案 §3.1 第 8 条 / §3.3 / §6.1）───────────


def test_validate_requested_scope_full_industry_only_overview():
    """方案 §3.1 第 8 条：requested_scope=full/industry 只能由 overview
    预览承载；overview 的 requested_scope 必须属于 overview/full/industry。"""
    two = ["600519.SH", "600518.SH"]
    assert validate_comparison_spec(_spec(requested_scope="full"), two) == []
    assert validate_comparison_spec(_spec(requested_scope="industry"), two) == []
    issues = validate_comparison_spec(
        _spec(
            mode="indicator",
            requested_scope="full",
            metric_ids=["r5_gross_margin"],
        ),
        two,
    )
    assert any("只能由双主体 cross_company+overview 承载" in i for i in issues)
    issues = validate_comparison_spec(_spec(requested_scope="indicator"), two)
    assert any("requested_scope 必须为" in i for i in issues)


def test_validate_requested_scope_global_fail_closed():
    """收口复核清单 §2.1/§3.2：full/industry 在任意非
    cross_company+overview×2 组合下都必须拒绝（入口全局校验）。"""
    two = ["600519.SH", "600518.SH"]
    three = two + ["000858.SZ"]
    # 1/2. same_company_cross_indicator + indicator + full/industry → issue
    for scope_name in ("full", "industry"):
        issues = validate_comparison_spec(
            ComparisonSpec(
                scope="same_company_cross_indicator",
                mode="indicator",
                requested_scope=scope_name,
                metric_ids=["a", "b"],
            ),
            ["600519.SH"],
        )
        assert any(
            "只能由双主体 cross_company+overview 承载" in i for i in issues
        ), f"{scope_name} 未被全局拒绝: {issues}"
    # 3. cross_company + indicator + full → issue
    issues = validate_comparison_spec(
        ComparisonSpec(
            scope="cross_company",
            mode="indicator",
            requested_scope="full",
            metric_ids=["r5_gross_margin"],
        ),
        two,
    )
    assert any("只能由双主体 cross_company+overview 承载" in i for i in issues)
    # 4. cross_company + overview + full + 两家 → 合法
    assert validate_comparison_spec(_spec(requested_scope="full"), two) == []
    # 5. cross_company + overview + industry + 三家 → 非法
    issues = validate_comparison_spec(_spec(requested_scope="industry"), three)
    assert any("只能由双主体 cross_company+overview 承载" in i for i in issues)


def test_invalid_spec_never_triggers_metric_query(monkeypatch):
    """清单 §3.2-6：非法 spec 在服务入口被拒绝，不触发任何指标查询。"""
    from app.application.services.light_comparison_service import (
        compare_same_company_indicators,
    )

    def _boom(*a, **k):
        raise AssertionError("非法 spec 不得触发指标查询")

    monkeypatch.setattr(
        "app.application.services.light_comparison_service.query_metric", _boom
    )
    spec = ComparisonSpec(
        scope="same_company_cross_indicator",
        mode="indicator",
        requested_scope="full",
        metric_ids=["a", "b"],
    )
    result = compare_same_company_indicators("600519.SH", "贵州茅台", spec)
    assert result.status == "insufficient_data"
    assert any("只能由双主体 cross_company+overview 承载" in w for w in result.warnings)


def test_build_preview_next_steps_by_scope():
    """方案 §6.1：普通/全面/单指标/风险/公司事实 → open_full_comparison；
    industry → open_industry_comparison（target 统一真实路由 /compare）。"""
    from app.application.services.light_comparison_service import (
        build_preview_next_steps,
    )

    codes = ["600519.SH", "600518.SH"]
    for scope in ("overview", "full", "indicator", "risk", "company_fact"):
        steps = build_preview_next_steps(scope, codes)
        assert len(steps) == 1
        assert steps[0].kind == "open_full_comparison"
        assert steps[0].target == "/compare"
        assert steps[0].participant_codes == codes
    industry = build_preview_next_steps("industry", codes)
    assert len(industry) == 1
    assert industry[0].kind == "open_industry_comparison"
    assert industry[0].params == {"scope": "industry"}
    assert build_preview_next_steps("full", []) == []
    dedup = build_preview_next_steps("full", ["a", "b", "a"])
    assert dedup[0].participant_codes == ["a", "b"]


def test_build_multi_company_next_steps_branches_and_cap():
    """方案 §2.4/§7.1-21/22/23：3..cap 家按页面能力分两分支（全代码）；
    超过 cap → 空列表（不截断、不携带代码）。"""
    from app.application.services.light_comparison_service import (
        build_multi_company_next_steps,
    )

    codes = ["600519.SH", "600518.SH", "000858.SZ"]
    steps = build_multi_company_next_steps(codes, multi_page_enabled=False)
    assert len(steps) == 1
    assert steps[0].kind == "choose_comparison_pair"
    assert steps[0].participant_codes == codes
    steps = build_multi_company_next_steps(codes, multi_page_enabled=True)
    assert len(steps) == 1
    assert steps[0].kind == "open_multi_company_comparison"
    assert steps[0].participant_codes == codes
    over = codes + ["600887.SH", "000895.SZ", "601857.SH"]
    assert build_multi_company_next_steps(over, multi_page_enabled=True) == []
    assert build_multi_company_next_steps(over, multi_page_enabled=False) == []
    assert build_multi_company_next_steps([], multi_page_enabled=True) == []


def test_generate_answer_overview_payload_json_serializable(monkeypatch):
    """WS 回归守卫：light_comparison 载荷必须可 json.dumps（Decimal 已转
    float/str，_ws_sender 不接受 Decimal），并携带 requested_scope 与
    程序生成的 next_steps。"""
    import json

    from app.application.services.light_comparison_service import (
        ComparisonValue,
        LightComparisonResult,
    )
    from app.agents.nodes import generate_answer as ga

    row = OverviewMetricRow(
        metric_id="r5_gross_margin",
        metric_label="毛利率",
        status="ok",
        unit="percent",
        period="20250331",
        values=[
            ComparisonValue(
                company_code="600519.SH",
                sec_name="贵州茅台",
                metric_id="r5_gross_margin",
                metric_label="毛利率",
                period="20250331",
                value=Decimal("91.0"),
                unit="percent",
            ),
            ComparisonValue(
                company_code="600518.SH",
                sec_name="康美药业",
                metric_id="r5_gross_margin",
                metric_label="毛利率",
                period="20250331",
                value=Decimal("75.0"),
                unit="percent",
            ),
        ],
        difference=Decimal("16.0"),
        difference_unit="个百分点",
        conclusion="贵州茅台比康美药业高 16.00个百分点",
    )
    fake_result = LightComparisonResult(
        status="partial",
        scope="cross_company",
        operation="difference",
        comparison_mode="overview",
        requested_scope="full",
        overview_rows=[row],
        conclusion="已成功比较 1/1 个维度。",
    )
    monkeypatch.setattr(
        "app.application.services.light_comparison_service."
        "compare_cross_company_overview",
        lambda participants, spec, as_of="": fake_result,
    )
    state = {"comparison_targets": _two_refs(), "runtime": object()}
    spec = _spec(requested_scope="full")
    out = ga._answer_cross_company_overview(state, _two_refs(), spec)
    payload = out["light_comparison"]
    assert payload["comparison_mode"] == "overview"
    assert payload["requested_scope"] == "full"
    assert payload["next_steps"][0]["kind"] == "open_full_comparison"
    assert payload["next_steps"][0]["participant_codes"] == [
        "600519.SH",
        "600518.SH",
    ]
    json.dumps(payload)  # 不抛 TypeError 即通过（Decimal 已 JSON 安全）
    assert "有限预览" in out["final_response"].answer
    assert "不代表完整画像" in out["final_response"].answer


def test_generate_answer_overview_industry_scope_disclaimer(monkeypatch):
    """方案 §6.1：requested_scope=industry 的回答必须明确未执行行业分位计算。"""
    from app.application.services.light_comparison_service import (
        LightComparisonResult,
    )
    from app.agents.nodes import generate_answer as ga

    fake_result = LightComparisonResult(
        status="insufficient_data",
        scope="cross_company",
        operation="difference",
        comparison_mode="overview",
        requested_scope="industry",
        overview_rows=[],
        warnings=["全部维度均无可比较数据"],
    )
    monkeypatch.setattr(
        "app.application.services.light_comparison_service."
        "compare_cross_company_overview",
        lambda participants, spec, as_of="": fake_result,
    )
    state = {"comparison_targets": _two_refs(), "runtime": object()}
    spec = _spec(requested_scope="industry")
    out = ga._answer_cross_company_overview(state, _two_refs(), spec)
    answer = out["final_response"].answer
    assert "未执行行业分位" in answer
    assert out["light_comparison"]["requested_scope"] == "industry"
    assert out["light_comparison"]["next_steps"][0]["kind"] == (
        "open_industry_comparison"
    )
