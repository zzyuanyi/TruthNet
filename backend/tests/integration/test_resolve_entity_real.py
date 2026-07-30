"""真实数据库实体解析集成测试。

验证 _find_company() 四步匹配：Wind Code → 全名 → 别名 → 前缀兜底。
需要设置 TRUTHNET_RUN_EXTERNAL_TESTS=1 才运行。
"""

import os

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.external,
    pytest.mark.skipif(
        os.environ.get("TRUTHNET_RUN_EXTERNAL_TESTS") != "1",
        reason="TRUTHNET_RUN_EXTERNAL_TESTS=1 required for external tests",
    ),
]


def test_find_maotai():
    """贵州茅台 → 600519.SH（全名匹配）。"""
    from app.agents.nodes.resolve_entity import _find_company

    result = _find_company("贵州茅台有风险吗")
    assert result is not None
    assert result.wind_code == "600519.SH"


def test_find_pingan():
    """平安银行 → 000001.SZ（全名匹配）。"""
    from app.agents.nodes.resolve_entity import _find_company

    result = _find_company("平安银行")
    assert result is not None
    assert result.wind_code == "000001.SZ"


def test_find_kangmei():
    """康美 → 600518.SH（前缀兜底）。"""
    from app.agents.nodes.resolve_entity import _find_company

    result = _find_company("康美有造假风险吗")
    assert result is not None
    assert result.wind_code == "600518.SH"


def test_find_single_char_returns_none():
    """单字不触发前缀匹配。"""
    from app.agents.nodes.resolve_entity import _find_company

    assert _find_company("康") is None
