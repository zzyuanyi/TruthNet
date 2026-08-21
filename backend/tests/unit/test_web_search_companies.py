"""画像环节联网触发测试 — Phase E 会5（listing_date 库内空 → 联网回填 + 来源标注）.

覆盖：
- 命中日期 → 回填 profile.listing_date + WEB_SEARCH_SOURCE warning；
- 命中但无日期 → 不回填、无 warning；
- off 默认 → 不回填、无 warning（行为与现状一致）。
"""

import pytest

from app.api.v1.routers import companies
from app.api.v1.schemas.common import WarningItem
from app.application.ports.web_search_provider import SearchResult
from app.application.services import web_search_service
from app.domain.company.models import CompanyRecord


def _record() -> CompanyRecord:
    return CompanyRecord(entity_id="c1", wind_code="600518.SH", sec_name="康美药业")


def _hits() -> list[SearchResult]:
    return [
        SearchResult(
            title="康美药业_百度百科",
            url="https://baike.baidu.com/x",
            snippet="上市日期 2001-03-19",
            source="mock",
        )
    ]


@pytest.mark.asyncio
async def test_profile_fill_hit(monkeypatch):
    """命中日期 → 回填 + WEB_SEARCH_SOURCE warning（含来源 URL）。"""

    async def fake(query, **kwargs):
        return _hits()

    monkeypatch.setattr(web_search_service, "web_search_async", fake)
    profile = {"listing_date": None}
    warnings: list[WarningItem] = []
    ok = await companies._web_search_fill_profile_listing_date(
        _record(), profile, warnings
    )
    assert ok is True
    assert profile["listing_date"] == "2001-03-19"
    assert any(
        w.code == "WEB_SEARCH_SOURCE" and "baike.baidu.com/x" in w.message
        for w in warnings
    )


@pytest.mark.asyncio
async def test_profile_fill_hit_without_date(monkeypatch):
    """命中但解析不出日期 → 不回填、无 warning（不伪造）。"""

    async def fake(query, **kwargs):
        return [
            SearchResult(
                title="无日期",
                url="https://x.test/1",
                snippet="无日期内容",
                source="mock",
            )
        ]

    monkeypatch.setattr(web_search_service, "web_search_async", fake)
    profile = {"listing_date": None}
    warnings: list[WarningItem] = []
    ok = await companies._web_search_fill_profile_listing_date(
        _record(), profile, warnings
    )
    assert ok is False
    assert profile["listing_date"] is None
    assert not any(w.code == "WEB_SEARCH_SOURCE" for w in warnings)


@pytest.mark.asyncio
async def test_profile_fill_off_default(monkeypatch):
    """off 默认：真实 web_search_async → off 门返回 []，不回填。

    （8/19 环境解耦：显式置 off，避免 .env 配置 anysearch 时真实联网。）
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "WEB_SEARCH_BACKEND", "off")
    profile = {"listing_date": None}
    warnings: list[WarningItem] = []
    ok = await companies._web_search_fill_profile_listing_date(
        _record(), profile, warnings
    )
    assert ok is False
    assert profile["listing_date"] is None
    assert not any(w.code == "WEB_SEARCH_SOURCE" for w in warnings)
