"""metric_evaluator 单元测试 — v3.3.3 收口批次 A（方案 §2.1/§3.1）。

覆盖：多字段错期不拼接、R4 四季度报告期语义、缺相邻季度、负单季成本、
explicit 期不 fallback 的查询层行为在 test_indicator_answer.py。
"""

from app.domain.benchmarks.metric_evaluator import evaluate_metric_per_period
from app.domain.benchmarks.metric_registry import MetricSpec, get_metric


def _metric(fields, periods, compute):
    return MetricSpec(
        metric_id="t",
        rule_id="R0",
        name="t",
        unit="ratio",
        description="",
        fields=fields,
        periods=periods,
        compute_from_series=compute,
    )


def test_misaligned_fields_not_concatenated():
    """方案 §2.1 最小反例：Q2 营收 + Q3 成本不得拼成 60%。

    oper_rev 有 Q1/Q2，less_oper_cost 有 Q1/Q3——只有 Q1 两字段完整，
    结果只能有 20240331 一期，不得产出「period=Q3、Q2 营收 + Q3 成本」。
    """

    def compute(series):
        rev = (series.get("oper_rev") or [None])[-1]
        cost = (series.get("less_oper_cost") or [None])[-1]
        if rev is None or cost is None or rev <= 0:
            return None
        return round((rev - cost) / rev, 4)

    sequences = {
        "oper_rev": [("20240331", 100.0), ("20240630", 200.0)],
        "less_oper_cost": [("20240331", 40.0), ("20240930", 80.0)],
    }
    results = evaluate_metric_per_period(
        _metric(("oper_rev", "less_oper_cost"), 1, compute), sequences
    )
    assert [p for p, _ in results] == ["20240331"]
    assert results[0][1] == round((100 - 40) / 100, 4)


def test_r4_aligned_quarterly_semantics():
    """方案 §3.1 R4 Q1 边界：Q1=当期累计；Q2=当期-同年度Q1。"""
    r4 = get_metric("r4_turnover_days")
    assert r4.compute_from_aligned is not None
    sequences = {
        "inventories": [
            ("20241231", 90.0),
            ("20250331", 100.0),
            ("20250630", 120.0),
        ],
        "less_oper_cost": [
            ("20241231", 260.0),
            ("20250331", 300.0),
            ("20250630", 320.0),
        ],
    }
    results = evaluate_metric_per_period(r4, sequences)
    periods = [p for p, _ in results]
    assert "20250331" in periods  # Q1：当期累计 300，avg_inv=95
    assert "20250630" in periods  # Q2：320-300=20，avg_inv=110
    q1 = next(v for p, v in results if p == "20250331")
    assert q1 == round(95 / (300 * 4) * 365, 4)
    q2 = next(v for p, v in results if p == "20250630")
    assert q2 == round(110 / (20 * 4) * 365, 4)


def test_r4_aligned_missing_adjacent_quarter_returns_none():
    """缺同年度相邻季度（Q2 缺 Q1）→ 该期不可计算。"""
    r4 = get_metric("r4_turnover_days")
    sequences = {
        "inventories": [("20241231", 90.0), ("20250630", 120.0)],
        "less_oper_cost": [("20241231", 260.0), ("20250630", 320.0)],
    }
    results = evaluate_metric_per_period(r4, sequences)
    assert results == []


def test_r4_aligned_negative_single_q_cost_none():
    """单季成本 <= 0（异常）→ 该期不可计算，不猜测。"""
    r4 = get_metric("r4_turnover_days")
    sequences = {
        "inventories": [
            ("20241231", 90.0),
            ("20250331", 100.0),
            ("20250630", 120.0),
        ],
        "less_oper_cost": [
            ("20241231", 260.0),
            ("20250331", 300.0),
            ("20250630", 280.0),  # 低于 Q1 累计 → 负差
        ],
    }
    results = evaluate_metric_per_period(r4, sequences)
    assert all(p != "20250630" for p, _ in results)
    assert "20250331" in [p for p, _ in results]


def test_r4_aligned_inventory_missing_adjacent_quarter_none():
    """方案 §3.2 反例：Q2 库存缺 20250331，成本齐全 → 不得用 20241231 拼平均。

    inventories: 20241231, 20250630；cost: 20241231, 20250331, 20250630。
    当前实现若把「排序后上一条」当相邻季度，会用 20241231 与 20250630
    做平均库存——必须返回 None/insufficient_data。
    """
    r4 = get_metric("r4_turnover_days")
    sequences = {
        "inventories": [("20241231", 90.0), ("20250630", 120.0)],
        "less_oper_cost": [
            ("20241231", 260.0),
            ("20250331", 300.0),
            ("20250630", 320.0),
        ],
    }
    results = evaluate_metric_per_period(r4, sequences)
    assert results == []


def test_r1_gap_exact_prior_year_base_required():
    """方案 §3.1 反例：20251231 营收缺精确 20241231 → 该期 None，不按位置猜。

    acct_rcv 有 20241231 基期，oper_rev 没有——两字段 [-5] 位置相同但
    同比基期不同，结果不得产出 20251231。
    """
    r1 = get_metric("r1_gap")
    assert r1.compute_from_aligned is not None
    sequences = {
        "acct_rcv": [
            ("20240331", 40.0),
            ("20240630", 45.0),
            ("20240930", 50.0),
            ("20241231", 55.0),
            ("20250331", 60.0),
            ("20250630", 66.0),
            ("20250930", 72.0),
            ("20251231", 80.0),
        ],
        "oper_rev": [
            ("20240331", 400.0),
            ("20240630", 440.0),
            ("20240930", 480.0),
            ("20250331", 520.0),
            ("20250630", 560.0),
            ("20250930", 600.0),
            ("20251231", 640.0),  # 缺 20241231
        ],
    }
    results = evaluate_metric_per_period(r1, sequences)
    by_period = dict(results)
    assert "20251231" not in by_period  # 营收缺精确去年同期 → insufficient
    # 20250930 两字段基期齐全：acct (72-50)/50=0.44，rev (600-480)/480=0.25
    assert "20250930" in by_period
    assert by_period["20250930"] == round((0.44 - 0.25) * 100, 4)


def test_r4_growth_gap_exact_prior_year_ok():
    """两字段都具备精确去年同期 → 结果正确（不依赖位置）。"""
    r4g = get_metric("r4_growth_gap")
    assert r4g.compute_from_aligned is not None
    sequences = {
        "inventories": [("20241231", 100.0), ("20251231", 140.0)],
        "oper_rev": [("20241231", 500.0), ("20251231", 600.0)],
    }
    results = evaluate_metric_per_period(r4g, sequences)
    # inv_yoy=(140-100)/100=0.4；rev_yoy=(600-500)/500=0.2 → 20pp
    assert results == [("20251231", 20.0)]
    # 20241231 缺 20231231 基期 → 不计入
    assert all(p != "20241231" for p, _ in results)


def test_r4_growth_gap_missing_inventory_base_none():
    """方案 §3.1 反例：20251231 库存缺精确 20241231 → 该期 None。"""
    r4g = get_metric("r4_growth_gap")
    sequences = {
        "inventories": [
            ("20241231", 90.0),
            ("20250331", 95.0),
            ("20250630", 100.0),
            ("20250930", 105.0),
            ("20251231", 110.0),
        ],
        "oper_rev": [
            ("20241231", 500.0),
            ("20250331", 520.0),
            ("20250630", 540.0),
            ("20250930", 560.0),
            ("20251231", 580.0),
        ],
    }
    results = evaluate_metric_per_period(r4g, sequences)
    by_period = dict(results)
    assert "20251231" in by_period  # 基期齐全（位置 [-1]/[-5] 也恰好一致）
    # 去掉库存的 20241231 后，同目标期两字段同比基期不同 → 必须 None
    sequences["inventories"] = [
        ("20250331", 95.0),
        ("20250630", 100.0),
        ("20250930", 105.0),
        ("20251231", 110.0),
    ]
    results = evaluate_metric_per_period(r4g, sequences)
    assert all(p != "20251231" for p, _ in results)


def test_r4_aligned_q3_q4_semantics():
    """Q3=当期-同年度Q2；Q4=当期-同年度Q3。"""
    r4 = get_metric("r4_turnover_days")
    sequences = {
        "inventories": [
            ("20250331", 100.0),
            ("20250630", 120.0),
            ("20250930", 130.0),
            ("20251231", 140.0),
        ],
        "less_oper_cost": [
            ("20250331", 300.0),
            ("20250630", 320.0),
            ("20250930", 330.0),
            ("20251231", 360.0),
        ],
    }
    results = evaluate_metric_per_period(r4, sequences)
    periods = [p for p, _ in results]
    assert "20250930" in periods  # 330-320=10
    assert "20251231" in periods  # 360-330=30
    q3 = next(v for p, v in results if p == "20250930")
    assert q3 == round(((130 + 120) / 2) / (10 * 4) * 365, 4)
    q4 = next(v for p, v in results if p == "20251231")
    assert q4 == round(((140 + 130) / 2) / (30 * 4) * 365, 4)


def test_r5_gross_margin_per_period_alignment():
    """r5 无 aligned 公式 → 走 compute_from_series 兼容路径，逐期对齐。"""
    r5 = get_metric("r5_gross_margin")
    assert r5.compute_from_aligned is None
    sequences = {
        "oper_rev": [("20240930", 500.0), ("20241231", 520.0)],
        "less_oper_cost": [("20240930", 300.0), ("20241231", 320.0)],
    }
    results = evaluate_metric_per_period(r5, sequences)
    assert [p for p, _ in results] == ["20240930", "20241231"]
    assert results[1][1] == round((520 - 320) / 520, 4)
