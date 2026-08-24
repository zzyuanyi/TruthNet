"""Phase E 会3 — impact_advice_service 测试.

覆盖：
- 财务路（rule_trigger 推导链 → finance 段 + evidence 聚合）；
- LLM mock → 确定性模板兜底（分模块建议，不空洞）；
- LLM 成功 → overall + 分模块建议（source_module 枚举校验）；
- LLM 校验失败 → 模板兜底；
- equity/events 路失败 → 降级不阻断（其他模块照常产出）。
"""

from types import SimpleNamespace

import pytest

from app.application.services import impact_advice_service as svc
from app.application.services.impact_advice_service import (
    ImpactAdviceResult,
    ImpactAdviceSegment,
    assemble_impact_advice,
)
from app.core.config import settings


def _risk_output():
    """构造最小 RiskOutput 等价对象（risk_scoring_service 输出）。"""
    return SimpleNamespace(
        wind_code="600518.SH",
        sec_name="康美药业",
        risk_level="yellow",
        overall_score=0.42,
        as_of="20260331",
        pattern_matches=[],
        derivation_chains=[
            SimpleNamespace(
                conclusion_type="rule_trigger",
                conclusion="R4 存货增速快于营收增速",
                signals=[
                    SimpleNamespace(
                        signal_id="R4",
                        label="存货–营收背离",
                        severity="orange",
                        explanation="存货增速 12.3% vs 营收 5.1%",
                        current={
                            "growth_gap": {
                                "value": 41.1,
                                "unit": "percentage_point",
                            }
                        },
                        history=[
                            {"period": "20241231", "growth_gap": 20.0},
                            {"period": "20250331", "growth_gap": 41.1},
                        ],
                        industry_percentile=88.0,
                        evidence_ids=["ev_fin_1", "ev_fin_2"],
                    )
                ],
                evidence_ids=["ev_fin_1", "ev_fin_2"],
            )
        ],
    )


@pytest.mark.asyncio
async def test_finance_segment_and_evidence(monkeypatch):
    """财务路：rule_trigger 推导链 → finance 段 + 可回查证据。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "mock")

    async def fake_score(code, as_of=""):
        return _risk_output()

    monkeypatch.setattr(
        "app.application.services.risk_scoring_service.assemble_and_score",
        fake_score,
    )
    monkeypatch.setattr(svc, "_equity_signals", lambda *a, **kw: ([], []))

    async def fake_events(*a, **kw):
        return ([], [], [])

    monkeypatch.setattr(svc, "_events_signals", fake_events)
    result: ImpactAdviceResult = await assemble_impact_advice("600518.SH", "")
    finance = [s for s in result.segments if s.source_module == "finance"]
    assert finance
    assert "R4" in finance[0].detail
    assert "ev_fin_1" in finance[0].evidence_ids
    assert result.evidence_count >= 2
    assert result.method == "template"
    assert "财务规则信号 1 项" in result.overall_advice
    assert len(result.verification_navigation) == 1
    item = result.verification_navigation[0]
    assert item.rule_id == "R4" and len(item.actions) == 3
    assert "行业分位" in item.quantified_context


@pytest.mark.asyncio
async def test_llm_success_uses_llm_method(monkeypatch):
    """LLM 成功：overall + 分模块建议，method=llm。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")

    async def fake_score(code, as_of=""):
        return _risk_output()

    monkeypatch.setattr(
        "app.application.services.risk_scoring_service.assemble_and_score",
        fake_score,
    )
    monkeypatch.setattr(svc, "_equity_signals", lambda *a, **kw: ([], []))

    async def fake_events(*a, **kw):
        return ([], [], [])

    monkeypatch.setattr(svc, "_events_signals", fake_events)
    output = svc._ImpactAdviceOutput(
        overall="存货增速与营收背离，需关注去化压力。",
        suggestions=[
            svc._ImpactSuggestion(
                source_module="finance",
                text="结合 R4 信号复核存货明细与销售确认政策。",
            ),
            svc._ImpactSuggestion(
                source_module="overall",
                text="建议结合公告与审计意见进一步核验。",
            ),
        ],
    )

    async def fake_llm(messages, schema, timeout=None):
        return output

    # 8/17 收敛 C：mock llm_guard.llm_with_fallback（LLM 成功，used=True）
    captured_timeout = None

    def fake_with_fallback(*args, **kwargs):
        nonlocal captured_timeout
        captured_timeout = kwargs.get("timeout")
        return output, True

    monkeypatch.setattr(
        "app.agents.llm_guard.llm_with_fallback", fake_with_fallback
    )
    result = await assemble_impact_advice("600518.SH", "")
    assert result.method == "llm"
    assert captured_timeout == 30.0
    assert "去化压力" in result.overall_advice
    modules = {s.source_module for s in result.segments}
    assert "finance" in modules and "overall" in modules
    llm_finance = [
        s
        for s in result.segments
        if s.source_module == "finance" and s.detail.startswith("结合")
    ]
    assert llm_finance and "ev_fin_1" in llm_finance[0].evidence_ids


@pytest.mark.asyncio
async def test_llm_invalid_falls_back(monkeypatch):
    """LLM 校验失败（空 suggestions）→ 模板兜底。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")

    async def fake_score(code, as_of=""):
        return _risk_output()

    monkeypatch.setattr(
        "app.application.services.risk_scoring_service.assemble_and_score",
        fake_score,
    )
    monkeypatch.setattr(svc, "_equity_signals", lambda *a, **kw: ([], []))

    async def fake_events(*a, **kw):
        return ([], [], [])

    monkeypatch.setattr(svc, "_events_signals", fake_events)
    output = svc._ImpactAdviceOutput(overall="x", suggestions=[])

    async def fake_llm(messages, schema, timeout=None):
        return output

    # 8/17 收敛 C：mock llm_guard.llm_with_fallback（LLM 校验失败 → 回退）
    def fake_with_fallback(messages, schema, fallback, validate=None, timeout=None):
        ok, _ = validate(output)
        if ok:
            return output, True
        return fallback(), False

    monkeypatch.setattr("app.agents.llm_guard.llm_with_fallback", fake_with_fallback)
    result = await assemble_impact_advice("600518.SH", "")
    assert result.method == "template"
    assert "综合风险等级" in result.overall_advice


@pytest.mark.asyncio
async def test_llm_new_number_falls_back(monkeypatch):
    """LLM 新增事实外数字时，影响建议回退模板。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")

    async def fake_score(code, as_of=""):
        return _risk_output()

    monkeypatch.setattr(
        "app.application.services.risk_scoring_service.assemble_and_score",
        fake_score,
    )
    monkeypatch.setattr(svc, "_equity_signals", lambda *a, **kw: ([], []))

    async def fake_events(*a, **kw):
        return ([], [], [])

    monkeypatch.setattr(svc, "_events_signals", fake_events)
    output = svc._ImpactAdviceOutput(
        overall="综合评分为0.999。",
        suggestions=[
            svc._ImpactSuggestion(source_module="finance", text="建议关注2024年风险。")
        ],
    )

    def fake_with_fallback(messages, schema, fallback, validate=None, timeout=None):
        ok, _ = validate(output)
        return (output, True) if ok else (fallback(), False)

    monkeypatch.setattr("app.agents.llm_guard.llm_with_fallback", fake_with_fallback)
    result = await assemble_impact_advice("600518.SH", "")
    assert result.method == "template"
    assert "0.999" not in result.overall_advice


@pytest.mark.asyncio
async def test_equity_events_failure_does_not_block(monkeypatch):
    """equity/events 路抛异常 → 降级（warning），财务段仍产出。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "mock")

    async def fake_score(code, as_of=""):
        return _risk_output()

    monkeypatch.setattr(
        "app.application.services.risk_scoring_service.assemble_and_score",
        fake_score,
    )

    def boom_eq(*a, **kw):
        raise RuntimeError("neo4j down")

    async def boom_ev(*a, **kw):
        raise RuntimeError("events down")

    monkeypatch.setattr(svc, "_equity_signals", boom_eq)
    monkeypatch.setattr(svc, "_events_signals", boom_ev)
    result = await assemble_impact_advice("600518.SH", "")
    finance = [s for s in result.segments if s.source_module == "finance"]
    assert finance
    assert result.warnings  # 降级 warning 记录


def test_segment_model_schema():
    """段模型：source_module 枚举 + evidence_ids 可回查。"""
    seg = ImpactAdviceSegment(
        source_module="events",
        title="舆情影响",
        detail="结论",
        evidence_ids=["ev_ann_1"],
    )
    assert seg.source_module == "events"
    assert seg.evidence_ids == ["ev_ann_1"]
