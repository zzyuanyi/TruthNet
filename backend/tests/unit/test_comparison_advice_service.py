"""8/23 会7 深化 — comparison_advice_service 测试（跨公司 LLM 综合分析）.

覆盖：
- 模板兜底：两家公司等级/评分对比 + 各自触发规则 + 分段建议；
- LLM 成功：overall + per-company suggestions（company_code 校验）；
- LLM 校验失败（新数字）→ 模板兜底；
- 单家公司失败 → partial warning，其余照常。
"""

from types import SimpleNamespace

import pytest

from app.application.services import comparison_advice_service as svc
from app.application.services.comparison_advice_service import (
    assemble_comparison_advice,
)
from app.core.config import settings


def _risk_output(code: str, name: str, level: str, score: float, rules: list[str]):
    return SimpleNamespace(
        wind_code=code,
        sec_name=name,
        risk_level=level,
        overall_score=score,
        as_of="20260331",
        pattern_matches=[],
        derivation_chains=[
            SimpleNamespace(
                conclusion_type="rule_trigger",
                conclusion=r,
                signals=[SimpleNamespace(explanation=f"{r} 信号")],
                evidence_ids=[f"ev_fin_{i}"],
            )
            for i, r in enumerate(rules)
        ],
    )


def _fake_score_map(companies: dict):
    async def fake(code, as_of=""):
        c = companies[code]
        return _risk_output(code, c["name"], c["level"], c["score"], c["rules"])

    return fake


def _patch_risk(monkeypatch, companies: dict):
    monkeypatch.setattr(
        "app.application.services.risk_scoring_service.assemble_and_score",
        _fake_score_map(companies),
    )


@pytest.mark.asyncio
async def test_template_fallback_two_companies(monkeypatch):
    """mock LLM → 模板兜底：等级对比 + 分段建议，不空洞。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "mock")
    _patch_risk(
        monkeypatch,
        {
            "600518.SH": {
                "name": "康美药业",
                "level": "red",
                "score": 0.85,
                "rules": ["R1 应收–营收背离", "R4 存货增速快于营收"],
            },
            "603693.SH": {
                "name": "江苏新能",
                "level": "yellow",
                "score": 0.42,
                "rules": ["R2 现金流–利润背离"],
            },
        },
    )
    result = await assemble_comparison_advice(["600518.SH", "603693.SH"])
    assert result.method == "template"
    assert "康美药业" in result.overall
    assert "江苏新能" in result.overall
    assert "跨公司对比结论" in result.overall
    assert "R1 应收–营收背离" in result.overall
    assert len(result.segments) == 2
    codes = {s.company_code for s in result.segments}
    assert codes == {"600518.SH", "603693.SH"}
    assert any("康美药业" in s.detail for s in result.segments)
    assert not result.warnings


@pytest.mark.asyncio
async def test_llm_success_uses_llm_method(monkeypatch):
    """LLM 成功：overall + per-company suggestions，method=llm。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    _patch_risk(
        monkeypatch,
        {
            "600518.SH": {
                "name": "康美药业",
                "level": "red",
                "score": 0.85,
                "rules": ["R1 应收–营收背离"],
            },
            "603693.SH": {
                "name": "江苏新能",
                "level": "yellow",
                "score": 0.42,
                "rules": ["R2 现金流–利润背离"],
            },
        },
    )
    output = svc._ComparisonOutput(
        overall="康美药业（red，0.85）风险显著高于江苏新能（yellow，0.42），"
        "两者均存在财务信号：康美侧重应收质量，江苏新能侧重现金流与利润匹配。",
        suggestions=[
            svc._CompanySuggestion(
                company_code="600518.SH",
                text="结合 R1 应收–营收背离复核应收账龄与回款。",
            ),
            svc._CompanySuggestion(
                company_code="603693.SH",
                text="结合 R2 现金流–利润背离核查经营现金流入构成。",
            ),
        ],
    )

    def fake_with_fallback(
        messages, schema, fallback=None, validate=None, timeout=None
    ):
        ok, _ = validate(output)
        return (output, True) if ok else (fallback(), False)

    monkeypatch.setattr("app.agents.llm_guard.llm_with_fallback", fake_with_fallback)
    result = await assemble_comparison_advice(["600518.SH", "603693.SH"])
    assert result.method == "llm"
    assert "康美药业" in result.overall
    assert "江苏新能" in result.overall
    seg_codes = {s.company_code for s in result.segments}
    assert seg_codes == {"600518.SH", "603693.SH"}


@pytest.mark.asyncio
async def test_llm_invented_number_falls_back(monkeypatch):
    """LLM 新增事实外数字（0.999）→ 模板兜底。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "deepseek")
    _patch_risk(
        monkeypatch,
        {
            "600518.SH": {
                "name": "康美药业",
                "level": "red",
                "score": 0.85,
                "rules": ["R1 应收–营收背离"],
            },
            "603693.SH": {
                "name": "江苏新能",
                "level": "yellow",
                "score": 0.42,
                "rules": ["R2 现金流–利润背离"],
            },
        },
    )
    output = svc._ComparisonOutput(
        overall="综合评分为0.999。",
        suggestions=[
            svc._CompanySuggestion(company_code="600518.SH", text="建议关注。")
        ],
    )

    def fake_with_fallback(
        messages, schema, fallback=None, validate=None, timeout=None
    ):
        ok, _ = validate(output)
        return (output, True) if ok else (fallback(), False)

    monkeypatch.setattr("app.agents.llm_guard.llm_with_fallback", fake_with_fallback)
    result = await assemble_comparison_advice(["600518.SH", "603693.SH"])
    assert result.method == "template"
    assert "0.999" not in result.overall


@pytest.mark.asyncio
async def test_single_company_failure_partial(monkeypatch):
    """单家公司分析失败 → partial warning，其余照常产出。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "mock")

    async def fake(code, as_of=""):
        if code == "600518.SH":
            raise ValueError("COMPANY_NOT_COVERED: 600518.SH")
        return _risk_output(code, "江苏新能", "yellow", 0.42, ["R2 现金流–利润背离"])

    monkeypatch.setattr(
        "app.application.services.risk_scoring_service.assemble_and_score", fake
    )
    result = await assemble_comparison_advice(["600518.SH", "603693.SH"])
    assert result.method == "template"
    assert any("600518.SH" in w for w in result.warnings)
    assert len(result.companies) == 1
    assert result.companies[0].wind_code == "603693.SH"


@pytest.mark.asyncio
async def test_all_failures_empty_result(monkeypatch):
    """全部失败 → 空结果 + 明确提示。"""
    monkeypatch.setattr(settings, "LLM_BACKEND", "mock")

    async def fake(code, as_of=""):
        raise ValueError(f"COMPANY_NOT_COVERED: {code}")

    monkeypatch.setattr(
        "app.application.services.risk_scoring_service.assemble_and_score", fake
    )
    result = await assemble_comparison_advice(["600518.SH", "603693.SH"])
    assert result.companies == []
    assert "无法完成" in result.overall
