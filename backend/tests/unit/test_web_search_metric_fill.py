"""extract_metric_from_hits 单测（会5 财务指标联网回填）。

覆盖：相关性 Gate、LLM 提取、数字锁定（值必须原样在 snippet 中）、
quote 逐字校验、无命中/失败 fail-closed。
"""

from __future__ import annotations

import re

import pytest

from app.application.ports.web_search_provider import SearchResult
from app.application.services.web_search_fact_fill import (
    _MetricExtraction,
    extract_metric_from_hits,
)


def _hit(title: str, snippet: str, url: str = "https://example.test/x") -> SearchResult:
    return SearchResult(
        title=title,
        url=url,
        snippet=snippet,
        source="test",
        published_at=None,
        extra={},
    )


@pytest.fixture(autouse=True)
def _fake_llm(monkeypatch):
    """假结构化 LLM：从 prompt 中的结果文本提取 value/period/quote。"""

    def fake_structured(messages, output_schema):
        user = messages[-1]["content"]
        # 兼容「毛利率为 77.54%」与「79.07% 77.87%」两类文本
        m = re.search(r"毛利率为\s*([0-9]+(?:\.[0-9]+)?%)|([0-9]+(?:\.[0-9]+)?%)", user)
        if not m:
            return _MetricExtraction(value="")
        value = m.group(1) or m.group(2)
        quote = ""
        for line in user.splitlines():
            stripped = line.strip()
            if value in stripped and not stripped.startswith("- ["):
                quote = stripped
                break
        period = "2025H1" if "2025H1" in user else "最新"
        return _MetricExtraction(
            value=value,
            period=period,
            quote=quote[:120],
            source_title="测试来源",
            source_url="https://example.test/x",
        )

    monkeypatch.setattr(
        "app.agents.llm_sync.run_llm_structured",
        fake_structured,
    )


def test_extract_ok_with_locked_number():
    hits = [
        _hit(
            "五粮液2025年报净利89.54亿",
            "五粮液最新毛利率为77.54%，较去年同期增加0.49个百分点，实现5年连续上涨。",
        )
    ]
    out = extract_metric_from_hits(hits, "毛利率")
    assert out is not None
    assert out["value"] == "77.54%"
    assert out["period"] == "最新"
    assert "77.54%" in out["quote"]


def test_extract_ok_with_period():
    hits = [
        _hit(
            "000858 毛利率",
            "2025/Q1 79.07% 2025/H1 77.87% 2025/Q3 75.72%",
        )
    ]
    out = extract_metric_from_hits(hits, "毛利率")
    assert out is not None
    assert out["value"] == "79.07%"
    assert out["period"] == "最新"


def test_extract_rejects_unlocked_number(monkeypatch):
    """数字锁定：LLM 返回不在 snippet 中的数字 → None。"""

    def fake_bad(messages, output_schema):
        return _MetricExtraction(
            value="99.99%", period="最新", quote="", source_title="t", source_url="u"
        )

    monkeypatch.setattr("app.agents.llm_sync.run_llm_structured", fake_bad)
    hits = [_hit("五粮液", "五粮液毛利率为77.54%")]
    assert extract_metric_from_hits(hits, "毛利率") is None


def test_extract_irrelevant_hits_gate():
    """相关性 Gate：无指标标签的 snippet → None（不搜无关内容）。"""
    hits = [_hit("五粮液股价", "今日收盘价 120.5 元，上涨 2.3%")]
    assert extract_metric_from_hits(hits, "毛利率") is None


def test_extract_empty_hits_fail_closed():
    assert extract_metric_from_hits([], "毛利率") is None


def test_extract_llm_none_fail_closed(monkeypatch):
    """LLM 失败（None）→ None，不阻断主链路。"""
    monkeypatch.setattr(
        "app.agents.llm_sync.run_llm_structured",
        lambda messages, schema: None,
    )
    hits = [_hit("五粮液", "五粮液毛利率为77.54%")]
    assert extract_metric_from_hits(hits, "毛利率") is None
