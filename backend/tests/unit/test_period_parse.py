"""报告期解析单元测试 — Phase C 后端任务 13.

重点: 2026Q2 必须转 20260630（季末日期），不得形成 2026Q201。
"""

from app.domain.finance.period import is_valid_period, normalize_period


def test_yyyymmdd_passthrough():
    assert normalize_period("20260331") == "20260331"


def test_dash_format():
    assert normalize_period("2026-03-31") == "20260331"


def test_quarter_end_mapping():
    assert normalize_period("2026Q1") == "20260331"
    assert normalize_period("2026Q2") == "20260630"
    assert normalize_period("2026Q3") == "20260930"
    assert normalize_period("2026Q4") == "20261231"


def test_quarter_lowercase_q():
    assert normalize_period("2026q2") == "20260630"


def test_quarter_no_invalid_concat():
    # 绝不产生 2026Q201
    out = normalize_period("2026Q2")
    assert out is not None
    assert "Q" not in out
    assert len(out) == 8
    assert out == "20260630"


def test_quarter_with_space():
    assert normalize_period("2026 Q2") == "20260630"


def test_invalid_returns_none():
    assert normalize_period("abc") is None
    assert normalize_period("2026Q5") is None
    assert normalize_period("") is None
    assert normalize_period(None) is None
    assert normalize_period("20250231") is None
    assert normalize_period("2026-02-29") is None


def test_is_valid_period():
    assert is_valid_period("20260630")
    assert not is_valid_period("20261301")
    assert not is_valid_period("20250231")
    assert not is_valid_period("2026")
