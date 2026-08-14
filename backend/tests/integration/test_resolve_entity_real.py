"""真实数据库实体解析集成测试（v3.2.1 批次 6 迁移）。

原 _find_company 私有函数已随 legacy 删除；本文件改用公开
CompanyEntityResolver.resolve() 验证：全名 → 简称反向包含 → 单字不锁定。
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


def _resolve(query: str):
    """真库公开解析入口（替代已删除的 _find_company）。"""
    from app.application.services.company_entity_resolver import (
        CompanyEntityResolver,
    )
    from app.application.services.company_resolver import get_company_repository

    return CompanyEntityResolver(get_company_repository()).resolve(query)


def test_find_maotai():
    """贵州茅台 → 600519.SH（全名匹配，自动锁定）。"""
    r = _resolve("贵州茅台有风险吗")
    assert r.selected_companies, "贵州茅台应解析出公司"
    assert r.selected_companies[0].wind_code == "600519.SH"


def test_find_pingan():
    """平安银行 → 000001.SZ（全名匹配，自动锁定）。"""
    r = _resolve("平安银行")
    assert r.selected_companies, "平安银行应解析出公司"
    assert r.selected_companies[0].wind_code == "000001.SZ"


def test_find_kangmei():
    """康美 → 600518.SH（safe_reverse_contains 唯一反向包含锁定）。"""
    r = _resolve("康美的造假风险")
    assert r.selected_companies, "康美应解析出公司"
    assert r.selected_companies[0].wind_code == "600518.SH"


def test_single_char_not_locked():
    """单字"康"不触发候选（v3.2.1 批次 7：自动锁定长度 ≥2 保护；
    提取器不产单字 span → 无 mention，走隐式主体路径也不得解析公司）。"""
    r = _resolve("康")
    assert not r.selected_companies
    if r.mentions:
        assert r.mentions[0].status == "not_found"
