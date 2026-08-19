"""联网搜索守卫服务 — Phase E 会5 B1.

同步入口 `web_search(query)`：agent 节点是同步 def，本服务把 async
provider 调用桥接到同步语义（镜像 `llm_sync.py` 的常驻事件循环模式）。

职责（顺序，任一失败都 fail-closed 返回 []，调用方诚实降级）：
1. off 门：WEB_SEARCH_BACKEND=off → 立即返回 []（零开销、零副作用，
   保证「开关关闭时行为与现状完全一致」）；
2. 缓存：同一 query 进程内去重（同 turn 不重复联网）；
3. 限流：WEB_SEARCH_RATE_LIMIT_RPM 令牌桶，预算耗尽 fail-fast 返回 []；
4. 超时：WEB_SEARCH_TIMEOUT_SECONDS，超时取消底层任务（不残留请求）；
5. 异常：provider 异常/空 → []，不抛给调用方。

异步调用方（FastAPI router 等）请用 `asyncio.to_thread(web_search, query)`
或直接 `await` 本服务的 async 包装（见 web_search_async）。
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import threading
import time
from typing import Callable

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── 常驻事件循环（镜像 llm_sync）──────────────────────────
_loop: asyncio.AbstractEventLoop | None = None
_loop_lock = threading.Lock()

# ── 进程内缓存（query -> list[SearchResult]）───────────────
_cache: dict[str, list] = {}
_cache_lock = threading.Lock()

# ── 令牌桶（RPM 限流）──────────────────────────────────────
_rate_meta = {"tokens": 0.0, "last_refill": 0.0}
_rate_lock = threading.Lock()


def _ensure_loop() -> asyncio.AbstractEventLoop:
    """获取常驻事件循环（daemon 线程，随进程生命周期）。"""
    global _loop
    with _loop_lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            threading.Thread(
                target=_loop.run_forever,
                daemon=True,
                name="web-search-loop",
            ).start()
        return _loop


def _create_provider():
    """工厂创建 provider（独立函数便于测试 monkeypatch）。"""
    from app.infrastructure.web_search.factory import create_web_search_provider

    return create_web_search_provider()


def _rate_limited() -> bool:
    """令牌桶：返回 True=预算充足（放行）；False=限流（拒绝本次）。"""
    rpm = max(1, int(settings.WEB_SEARCH_RATE_LIMIT_RPM))
    now = time.monotonic()
    with _rate_lock:
        if _rate_meta["last_refill"] == 0.0:
            _rate_meta["tokens"] = float(rpm)
            _rate_meta["last_refill"] = now
        elapsed = now - _rate_meta["last_refill"]
        _rate_meta["tokens"] = min(
            float(rpm), _rate_meta["tokens"] + elapsed * rpm / 60.0
        )
        _rate_meta["last_refill"] = now
        if _rate_meta["tokens"] >= 1.0:
            _rate_meta["tokens"] -= 1.0
            return True
        return False


async def _search_async(provider, query: str, max_results: int | None) -> list:
    return await provider.search(query, max_results=max_results)


def _run_async(coro_factory: Callable[[], asyncio.Future], timeout: float) -> list:
    """提交协程到常驻 loop 并等待；超时取消底层任务并返回 []。"""
    loop = _ensure_loop()
    future = asyncio.run_coroutine_threadsafe(coro_factory(), loop)
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        future.cancel()
        logger.warning("web_search: 联网超时（>%ss），已取消", timeout)
        return []
    except Exception:  # noqa: BLE001 — 任意异常回退空列表
        logger.warning("web_search: 联网调用失败，回退空", exc_info=True)
        return []


def web_search(
    query: str,
    *,
    max_results: int | None = None,
    timeout: float | None = None,
) -> list:
    """联网搜索（同步入口）— off/超时/限流/异常/无结果一律返回 [].

    Args:
        query: 搜索词（如「康美药业 上市日期」）。
        max_results: 最多返回命中数，默认 WEB_SEARCH_MAX_RESULTS。
        timeout: 单次墙钟预算（秒），默认 WEB_SEARCH_TIMEOUT_SECONDS。

    Returns:
        list[SearchResult]；任何失败路径都不抛异常。
    """
    # 1. off 门（零副作用：不创建 provider、不写缓存、不耗限流）
    if (settings.WEB_SEARCH_BACKEND or "off").lower() == "off":
        return []

    key = query.strip()
    # 2. 缓存去重（命中不消耗限流令牌）
    with _cache_lock:
        if key in _cache:
            return list(_cache[key])

    # 3. 限流
    if not _rate_limited():
        logger.warning(
            "web_search: 触发限流（RPM=%s），本次跳过",
            settings.WEB_SEARCH_RATE_LIMIT_RPM,
        )
        return []

    # 4. 调用 provider
    provider = _create_provider()
    if provider is None:
        return []
    budget = (
        timeout if timeout is not None else float(settings.WEB_SEARCH_TIMEOUT_SECONDS)
    )
    max_n = (
        max_results if max_results is not None else int(settings.WEB_SEARCH_MAX_RESULTS)
    )
    hits = _run_async(lambda: _search_async(provider, key, max_n), budget)

    # 5. 缓存（含空结果——避免同 query 反复联网；off 路径不写缓存）
    with _cache_lock:
        _cache[key] = list(hits)
    return list(hits)


async def web_search_async(
    query: str,
    *,
    max_results: int | None = None,
    timeout: float | None = None,
) -> list:
    """async 包装（FastAPI router 等异步调用方用），语义与 web_search 一致。"""
    return await asyncio.to_thread(
        web_search, query, max_results=max_results, timeout=timeout
    )


def _reset_for_tests() -> None:
    """清空缓存与限流状态（仅测试用）。"""
    global _rate_meta
    with _cache_lock:
        _cache.clear()
    with _rate_lock:
        _rate_meta = {"tokens": 0.0, "last_refill": 0.0}
