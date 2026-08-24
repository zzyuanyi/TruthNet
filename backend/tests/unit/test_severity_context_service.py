# -*- coding: utf-8 -*-
"""L1 严重程度量化服务（severity_context_service）单元测试。

8/23 叙事落地：L1「多严重」量化参考（行业分位 / 历史趋势 / 距触发线）。
边界：纯客观数据并列，不做定性/预测；数据缺失逐句跳过。
"""

from app.application.services.severity_context_service import (
    build_severity_context,
    percentiles_for_rule,
    render_quantified_line,
)


def _detail(current: dict, history: list | None = None) -> dict:
    return {"current": current, "history": history or []}


def test_percentile_sentence():
    """分位句：行业分位第 X 百分位（metric 名）。"""
    sentences = build_severity_context("R1", _detail({}), {"r1_gap": 87.2}, "red")
    assert "行业分位：应收-营收背离幅度第 87 百分位" in sentences


def test_percentile_skipped_when_missing():
    """无对应分位数据（R5/R7 引擎不计算分位）→ 无分位句。"""
    assert build_severity_context("R1", _detail({}), {}, "red") == []
    # percentiles 里有其他规则的分位，但 R5 自身无 metric 分位 → 不输出
    sentences = build_severity_context(
        "R5", _detail({}), {"r1_gap": 87, "r6_oth_rcv_to_assets": 60}, "red"
    )
    assert not any("行业分位" in s for s in sentences)


def test_percentiles_for_rule_rebuilds_rule_metric_mapping():
    assert percentiles_for_rule("R1", 87.2) == {"r1_gap": 87.2}
    assert percentiles_for_rule("R5", 87.2) == {}


def test_trend_sentence_rising():
    """趋势句：最新 vs 上期 + 连续期数（单位从 current 同名键取）。"""
    history = [
        {"period": "20240630", "gap": 10.0},
        {"period": "20240930", "gap": 20.0},
        {"period": "20241231", "gap": 30.0},
        {"period": "20250331", "gap": 41.1},
    ]
    sentences = build_severity_context(
        "R1", _detail({"gap": {"value": 41.1, "unit": "percentage_point"}}, history), {}
    )
    trend = [s for s in sentences if s.startswith("近")]
    assert len(trend) == 1
    assert "近 4 期最新 41.1pp（上期 30pp）" in trend[0]
    assert "连续 4 期上升" in trend[0]


def test_trend_sentence_flat_and_unit_fallback():
    """持平句；history 无主键时兜底首个数值键。"""
    sentences = build_severity_context(
        "R1",
        _detail({}, [{"period": "p1", "gap": 5.0}, {"period": "p2", "gap": 5.0}]),
        {},
    )
    assert "与上期持平" in sentences[0]
    # 无 unit 时趋势句不显示单位
    sentences = build_severity_context(
        "R4",
        _detail(
            {},
            [
                {"period": "p1", "growth_gap": 10.0},
                {"period": "p2", "growth_gap": 25.0},
            ],
        ),
        {},
    )
    assert "最新 25（上期 10）" in sentences[0]


def test_threshold_sentence_higher():
    """阈值句（higher 方向）：超出触发线。"""
    sentences = build_severity_context(
        "R1",
        _detail({"gap": {"value": 41.1, "unit": "percentage_point"}}),
        {},
        "orange",
    )
    threshold = [s for s in sentences if s.startswith("当前")]
    assert len(threshold) == 1
    assert "当前 应收-营收增速差 41.1pp，触发线 30pp（超出 11.1pp）" in threshold[0]


def test_threshold_sentence_lower_direction():
    """R2 为 lower 方向：比值越低越险——低于触发线 = 风险侧 =「超出」。"""
    sentences = build_severity_context(
        "R2",
        _detail({"cf_to_profit_ratio": {"value": 0.2, "unit": "ratio"}}),
        {},
        "orange",
    )
    threshold = [s for s in sentences if s.startswith("当前")]
    assert "超出" in threshold[0]
    assert "0.2比值" in threshold[0]


def test_extreme_r2_ratio_is_not_rendered_as_a_literal_value():
    line = render_quantified_line(
        "R2",
        _detail({"cf_to_profit_ratio": {"value": -3627.3, "unit": "ratio"}}),
        {"r2_cf_ratio": 0.3},
        "red",
    )
    assert "极端值（需核查）" in line
    assert "-3627.3" not in line and "触发线" not in line


def test_missing_data_returns_empty():
    """无 current/history/分位 → 全空（诚实降级，不硬凑）。"""
    assert build_severity_context("R1", _detail({}), {}, "red") == []
    assert render_quantified_line("R1", _detail({}), {}, "red") == ""


def test_render_quantified_line_format():
    """组合渲染：「量化参考：分位句；趋势句；阈值句。」"""
    line = render_quantified_line(
        "R1",
        _detail(
            {"gap": {"value": 41.1, "unit": "percentage_point"}},
            [{"period": "p1", "gap": 20.0}, {"period": "p2", "gap": 41.1}],
        ),
        {"r1_gap": 87},
        "red",
    )
    assert line.startswith("量化参考：")
    assert "行业分位" in line and "近 2 期" in line and "触发线" in line
    assert line.endswith("。")
