"""同步节点内调用 async LLM 的公共工具 — Phase D.

LangGraph 节点是同步 def（agents/graph.py 全同步 add_node），而
LLM Provider 接口（chat/structured_chat）是 async。两条调用路径：

- REST：chat.py 用 asyncio.to_thread(graph.invoke) → 节点运行在线程池
  线程（无事件循环），asyncio.run 直接可用；
- WS：chat.py 在事件循环线程内同步 _compiled_graph.invoke() → 节点运行
  在事件循环线程，直接 asyncio.run 抛 RuntimeError。

统一方案：在独立线程中 asyncio.run + future.result(timeout)，两条路径
均安全，且天然满足"LLM 失败 3s 内降级"。超时/异常 → 返回 ""，
调用方回退模板。
"""

import asyncio
import concurrent.futures
import logging

logger = logging.getLogger(__name__)


def _get_providers() -> tuple:
    """创建主 provider + 备选（LLM_FALLBACK_BACKEND 配置时）。

    返回 (primary, fallback)，任一创建失败 → None（调用方回退）。
    """
    try:
        from app.core.config import settings
        from app.infrastructure.llm.factory import create_llm_provider

        primary = create_llm_provider()
        fallback_backend = settings.LLM_FALLBACK_BACKEND
        fallback = None
        if fallback_backend and fallback_backend != settings.LLM_BACKEND:
            fallback = create_llm_provider(fallback_backend)
        return primary, fallback
    except Exception:  # noqa: BLE001 — provider 创建失败回退
        logger.warning("llm_sync: LLM provider 创建失败，回退模板", exc_info=True)
        return None, None


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
        timeout: 秒，默认 settings.LLM_REQUEST_TIMEOUT（30s）——真实 LLM
        生成响应通常 5-15s，3s 会让所有真实调用超时回退；降级语义是
        "异常/超时才回退"，异常（连接失败/401）即时返回。
    """
    if timeout is None:
        from app.core.config import settings

        timeout = float(settings.LLM_REQUEST_TIMEOUT)
    primary, fallback = _get_providers()
    if primary is None:
        return ""

    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = ex.submit(
        asyncio.run,
        _call_with_fallback(primary, fallback, lambda p: p.chat(messages)),
    )
    try:
        return future.result(timeout=timeout) or ""
    except concurrent.futures.TimeoutError:
        logger.warning("llm_sync: LLM 调用超时（>%ss），回退模板", timeout)
        return ""
    except Exception:  # noqa: BLE001 — LLM 任意异常回退模板
        logger.warning("llm_sync: LLM 调用失败，回退模板", exc_info=True)
        return ""
    finally:
        # 不等待后台线程：超时后 LLM 线程可能仍挂起，wait=True 会阻塞到完成
        ex.shutdown(wait=False)


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

    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = ex.submit(
        asyncio.run,
        _call_with_fallback(
            primary,
            fallback,
            lambda p: p.structured_chat(messages, output_schema),
        ),
    )
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        logger.warning("llm_sync: structured 调用超时（>%ss），返回 None", timeout)
        return None
    except Exception:  # noqa: BLE001
        logger.warning("llm_sync: structured 调用失败，返回 None", exc_info=True)
        return None
    finally:
        ex.shutdown(wait=False)
