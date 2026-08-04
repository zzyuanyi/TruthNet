"""同步节点内调用 async LLM 的公共工具 — Phase D.

LangGraph 节点是同步 def（agents/graph.py 全同步 add_node），而
LLM Provider 接口（chat/structured_chat）是 async。两条调用路径：

- REST：chat.py 用 asyncio.to_thread(graph.invoke) → 节点运行在线程池
  线程（无事件循环）；
- WS：chat.py 在事件循环线程内同步 _compiled_graph.invoke() → 节点运行
  在事件循环线程，直接 asyncio.run 抛 RuntimeError。

统一方案：常驻事件循环线程 + asyncio.run_coroutine_threadsafe：
- 任意线程（REST/WS）提交协程到常驻 loop，安全；
- future.result(timeout) 超时 → future.cancel() 真正取消底层 asyncio
  task（中断 httpx 请求），不残留后台线程/请求；
- 客户端在协程 finally 中 close（连接释放，不泄漏）。
超时/异常 → 返回空（调用方回退模板）。
"""

import asyncio
import concurrent.futures
import logging
import threading

logger = logging.getLogger(__name__)

_loop: asyncio.AbstractEventLoop | None = None
_loop_lock = threading.Lock()


def _ensure_loop() -> asyncio.AbstractEventLoop:
    """获取常驻事件循环（daemon 线程，随进程生命周期）。"""
    global _loop
    with _loop_lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            threading.Thread(
                target=_loop.run_forever,
                daemon=True,
                name="llm-sync-loop",
            ).start()
        return _loop


def _run_coro(coro_factory, timeout: float, empty_value):
    """提交协程到常驻 loop 并等待；超时 → 真正取消并返回空值。"""
    loop = _ensure_loop()
    future = asyncio.run_coroutine_threadsafe(coro_factory(), loop)
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        # 真正取消底层 asyncio task（中断 httpx 请求），不残留后台请求
        future.cancel()
        logger.warning("llm_sync: LLM 调用超时（>%ss），已取消，回退", timeout)
        return empty_value
    except Exception:  # noqa: BLE001 — LLM 任意异常回退
        logger.warning("llm_sync: LLM 调用失败，回退", exc_info=True)
        return empty_value


def _get_providers() -> tuple:
    """创建主 provider + 备选（LLM_FALLBACK_BACKEND 配置时）。

    主、备分别 try：备用创建异常不连带丢弃可用的主 Provider。
    返回 (primary, fallback)，主创建失败 → (None, None)（调用方回退）。
    """
    from app.core.config import settings
    from app.infrastructure.llm.factory import create_llm_provider

    try:
        primary = create_llm_provider()
    except Exception:  # noqa: BLE001 — 主创建失败回退
        logger.warning("llm_sync: 主 LLM provider 创建失败，回退模板", exc_info=True)
        return None, None

    fallback = None
    fallback_backend = settings.LLM_FALLBACK_BACKEND
    if fallback_backend and fallback_backend != settings.LLM_BACKEND:
        try:
            fallback = create_llm_provider(fallback_backend)
        except Exception:  # noqa: BLE001 — 备用创建失败不丢主
            logger.warning(
                "llm_sync: 备用 LLM provider（%s）创建失败，仅用主",
                fallback_backend,
                exc_info=True,
            )
            fallback = None
    return primary, fallback


async def _call_with_fallback(primary, fallback, coro_factory):
    """主 provider → 失败（空/异常）→ 备选 → 全败返回 None；关闭全部客户端。

    背景：asyncio.run 结束后 AsyncOpenAI 客户端不关闭会泄漏连接
    （每个客户端独立连接池），连续调用 → SYN_SENT 堆积 → 连接耗尽。
    每次调用后必须 aclose 所有客户端。
    """
    providers = [p for p in (primary, fallback) if p is not None]
    try:
        for p in providers:
            try:
                result = await coro_factory(p)
                if result:
                    return result
                logger.warning("llm_sync: %s 返回空，视为失败", p.provider_name)
            except Exception:  # noqa: BLE001 — 单个 provider 失败尝试下一个
                logger.warning(
                    "llm_sync: %s 调用失败，尝试下一个", p.provider_name, exc_info=True
                )
        return None
    finally:
        for p in providers:
            client = getattr(p, "_client", None)
            if client is not None:
                try:
                    await client.close()
                except Exception:  # noqa: BLE001 — 关闭失败不影响结果
                    pass


def run_llm_chat(messages: list[dict], timeout: float | None = None) -> str:
    """同步调用 async LLM chat，返回文本；超时/异常 → ""。

    Args:
        messages: OpenAI 兼容 messages 列表。
        timeout: 秒，默认取 settings.LLM_REQUEST_TIMEOUT——真实 LLM
        生成响应通常 5-15s，过短会让所有真实调用超时回退；降级语义是
        "异常/超时才回退"，异常（连接失败/401）即时返回。
    """
    if timeout is None:
        from app.core.config import settings

        timeout = float(settings.LLM_REQUEST_TIMEOUT)
    primary, fallback = _get_providers()
    if primary is None:
        return ""

    return (
        _run_coro(
            lambda: _call_with_fallback(primary, fallback, lambda p: p.chat(messages)),
            timeout,
            "",
        )
        or ""
    )


def run_llm_structured(
    messages: list[dict],
    output_schema,
    timeout: float | None = None,
):
    """同步调用 async LLM structured_chat，返回 Pydantic 模型；失败 → None。

    用于意图识别等需要结构化输出的同步节点场景（REST/WS 双路径安全）。
    """
    if timeout is None:
        from app.core.config import settings

        timeout = float(settings.LLM_REQUEST_TIMEOUT)
    primary, fallback = _get_providers()
    if primary is None:
        return None

    return _run_coro(
        lambda: _call_with_fallback(
            primary,
            fallback,
            lambda p: p.structured_chat(messages, output_schema),
        ),
        timeout,
        None,
    )
