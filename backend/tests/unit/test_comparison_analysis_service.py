"""Phase E 会6 — comparison_analysis_service 测试.

覆盖：
- LLM mock/失败/校验失败 → 确定性模板兜底（不空洞）；
- LLM 成功 → 段落包含整体判断与分维度分析；
- 程序校验：段落引用的 metric_ids 必须属于结构化事实（防伪造指标）；
- 结构化数据不被覆盖：LLM 输出与 result 分离（只读）；
- 无可比较事实 → 诚实兜底，不调用 LLM。
"""

from decimal import Decimal


from app.application.services.comparison_analysis_service import (
    ComparisonAnalysisOutput,
    ComparisonAnalysisParagraph,
    build_comparison_analysis,
)
from app.application.services.light_comparison_service import (
    ComparisonValue,
    LightComparisonResult,
    OverviewMetricRow,
)
from app.core.config import settings


def _row(
    metric_id: str,
    label: str,
    a: Decimal,
    b: Decimal,
    unit: str = "percent",
    period: str = "20251231",
    status: str = "ok",
) -> OverviewMetricRow:
    return OverviewMetricRow(
        metric_id=metric_id,
        metric_label=label,
        status=status,  # type: ignore[arg-type]
        unit=unit,
        period=period,
        values=[
            ComparisonValue(
                company_code="600519.SH",
                sec_name="贵州茅台",
                metric_id=metric_id,
                metric_label=label,
                period=period,
                value=a,
                unit=unit,
            ),
            ComparisonValue(
                company_code="600518.SH",
                sec_name="康美药业",
                metric_id=metric_id,
                metric_label=label,
                period=period,
                value=b,
                unit=unit,
            ),
        ],
        difference=a - b,
        difference_unit=unit,
        conclusion=f"{label}差异结论",
    )


def _result(rows: list[OverviewMetricRow]) -> LightComparisonResult:
    return LightComparisonResult(
        status="ok",
        scope="cross_company",
        operation="difference",
        comparison_mode="overview",
        overview_rows=rows,
        requested_scope="overview",
    )


def test_mock_backend_uses_template(monkeypatch):
    """LLM mock 环境 → 确定性模板兜底（不空洞、可读）。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "mock")
    result = _result(
        [
            _row("r5_gross_margin", "毛利率", Decimal("83.68"), Decimal("17.54")),
            _row("debt_to_assets", "资产负债率", Decimal("8.37"), Decimal("28.78")),
        ]
    )
    text, warnings = build_comparison_analysis(
        result=result, company_names=["贵州茅台", "康美药业"]
    )
    assert warnings
    assert "贵州茅台" in text
    assert "高于" in text or "低于" in text
    assert "毛利率" in text


def test_llm_success_returns_paragraphs(monkeypatch):
    """LLM 成功 → 整体判断 + 分维度段落（引用真实指标）。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    output = ComparisonAnalysisOutput(
        overall="贵州茅台盈利质量明显优于康美药业。",
        paragraphs=[
            ComparisonAnalysisParagraph(
                text="毛利率维度贵州茅台显著更高，反映产品定价能力强。",
                metric_ids=["r5_gross_margin"],
            ),
            ComparisonAnalysisParagraph(
                text="杠杆水平贵州茅台更低，财务结构更稳健。",
                metric_ids=["debt_to_assets"],
            ),
        ],
    )
    monkeypatch.setattr(
        "app.agents.llm_sync.run_llm_structured", lambda *a, **kw: output
    )
    result = _result(
        [
            _row("r5_gross_margin", "毛利率", Decimal("83.68"), Decimal("17.54")),
            _row("debt_to_assets", "资产负债率", Decimal("8.37"), Decimal("28.78")),
        ]
    )
    text, warnings = build_comparison_analysis(
        result=result, company_names=["贵州茅台", "康美药业"]
    )
    assert warnings == []
    assert "盈利质量明显优于" in text
    assert "毛利率维度" in text
    # 结构化数据未被覆盖：LLM 输出与 result 分离（只读）
    assert len(result.overview_rows) == 2
    assert float(result.overview_rows[0].values[0].value) == 83.68


def test_llm_unknown_metric_id_falls_back(monkeypatch):
    """校验失败：段落引用事实之外的指标 → 整体降级模板兜底。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    output = ComparisonAnalysisOutput(
        overall="分析。",
        paragraphs=[
            ComparisonAnalysisParagraph(
                text="提到了不存在的指标。", metric_ids=["fake_metric_xyz"]
            )
        ],
    )
    monkeypatch.setattr(
        "app.agents.llm_sync.run_llm_structured", lambda *a, **kw: output
    )
    result = _result(
        [_row("r5_gross_margin", "毛利率", Decimal("83.68"), Decimal("17.54"))]
    )
    text, warnings = build_comparison_analysis(
        result=result, company_names=["贵州茅台", "康美药业"]
    )
    assert warnings
    assert "fake_metric_xyz" not in text  # 模板兜底不含伪造指标


def test_llm_exception_falls_back(monkeypatch):
    """LLM 异常 → 确定性模板兜底，不阻塞结构化比较。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")

    def boom(*a, **kw):
        raise RuntimeError("llm down")

    monkeypatch.setattr("app.agents.llm_sync.run_llm_structured", boom)
    result = _result(
        [_row("r5_gross_margin", "毛利率", Decimal("83.68"), Decimal("17.54"))]
    )
    text, warnings = build_comparison_analysis(
        result=result, company_names=["贵州茅台", "康美药业"]
    )
    assert warnings
    assert "毛利率" in text


def test_no_facts_honest_fallback(monkeypatch):
    """无可比较指标 → 诚实兜底且不调用 LLM（零调用）。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    calls: list = []

    def fake(messages, schema, timeout=None):
        calls.append(messages)
        return None

    monkeypatch.setattr("app.agents.llm_sync.run_llm_structured", fake)
    result = _result(
        [
            _row(
                "r4_turnover_days",
                "存货周转天数",
                Decimal("1"),
                Decimal("2"),
                unit="days",
                status="insufficient_data",
            )
        ]
    )
    text, warnings = build_comparison_analysis(
        result=result, company_names=["贵州茅台", "康美药业"]
    )
    assert "数据不足" in text or "无法" in text
    assert calls == []  # 零调用


def test_indicator_mode_uses_participants(monkeypatch):
    """单指标比较（indicator）：participants 驱动 facts 与模板。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "mock")
    result = LightComparisonResult(
        status="ok",
        scope="cross_company",
        operation="difference",
        comparison_mode="indicator",
        participants=[
            ComparisonValue(
                company_code="600519.SH",
                sec_name="贵州茅台",
                metric_id="r5_gross_margin",
                metric_label="毛利率",
                period="20251231",
                value=Decimal("83.68"),
                unit="percent",
            ),
            ComparisonValue(
                company_code="600518.SH",
                sec_name="康美药业",
                metric_id="r5_gross_margin",
                metric_label="毛利率",
                period="20251231",
                value=Decimal("17.54"),
                unit="percent",
            ),
        ],
        difference=Decimal("66.14"),
        difference_unit="percent",
        conclusion="茅台毛利率高于康美",
    )
    text, warnings = build_comparison_analysis(
        result=result, company_names=["贵州茅台", "康美药业"]
    )
    assert warnings
    assert "毛利率" in text
    assert "贵州茅台" in text
