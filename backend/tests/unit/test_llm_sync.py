"""LLM synchronization bulkhead tests."""

import asyncio

import pytest

from app.agents import llm_sync
from app.core.config import settings


@pytest.mark.asyncio
async def test_bulkhead_queue_timeout_returns_fallback(monkeypatch, caplog):
    monkeypatch.setattr(settings, "LLM_MAX_CONCURRENCY", 1)
    monkeypatch.setattr(settings, "LLM_QUEUE_TIMEOUT_SECONDS", 0.02)
    monkeypatch.setattr(llm_sync, "_llm_semaphore", None)
    monkeypatch.setattr(llm_sync, "_llm_semaphore_limit", 0)

    entered = asyncio.Event()
    release = asyncio.Event()

    class Provider:
        provider_name = "test"
        _client = None

        async def chat(self):
            entered.set()
            await release.wait()
            return "ok"

    provider = Provider()
    first = asyncio.create_task(
        llm_sync._call_with_bulkhead(provider, None, lambda item: item.chat())
    )
    await entered.wait()
    second = await llm_sync._call_with_bulkhead(
        provider, None, lambda item: item.chat()
    )
    assert second is None
    assert "LLM_QUEUE_TIMEOUT" in caplog.text
    release.set()
    assert await first == "ok"
