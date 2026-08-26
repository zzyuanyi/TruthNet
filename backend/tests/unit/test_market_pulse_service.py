"""市场脉搏服务的网络环境边界测试。"""

from __future__ import annotations

import asyncio

from app.application.services import market_pulse_service as service


class _FakeClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def test_crawl_does_not_inherit_process_certificate_or_proxy(monkeypatch):
    """公共 RSS 不受 SSL_CERT_FILE 等本机环境变量影响。"""

    client: _FakeClient | None = None

    def make_client(**kwargs):
        nonlocal client
        client = _FakeClient(**kwargs)
        return client
    source = service.PulseSource(
        key="test",
        name="测试源",
        url="https://example.test/rss.xml",
        region_code="CN",
        country="中国",
        lat=0,
        lng=0,
    )

    async def fake_fetch(_client, _source):
        assert _client is client
        return []

    monkeypatch.setattr(service, "_SOURCES", (source,))
    monkeypatch.setattr(service.httpx, "AsyncClient", make_client)
    monkeypatch.setattr(service, "_fetch_one", fake_fetch)

    asyncio.run(service.crawl_once())

    assert client is not None
    assert client.kwargs["follow_redirects"] is True
    assert client.kwargs["trust_env"] is False
