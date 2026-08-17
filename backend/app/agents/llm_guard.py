"""受约束 LLM 调用公共守卫 — 8/17 收敛 C.

统一「LLM 结构化输出 → 程序校验 → 失败降级」模式，消除 6 处重复
实现（mentionness / indicator-fallback / comparison-analysis /
impact-advice / span-extractor / fraud-conclusion 各写了一套
try/except + timeout + 校验）。

设计：
- `structured_llm()`：一次受约束调用，超时/异常/空 → None（fail-closed）；
- `llm_with_fallback()`：LLM → 校验 → 失败自动回退 fallback 值；
- 所有服务保留各自的 prompt/schema/校验逻辑（helper 只统一"调用与
  失败语义"），不强制抽公共 prompt。
"""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


def structured_llm(
    messages: list[dict],
    schema: Any,
    timeout: float = 10.0,
) -> Any | None:
    """受约束 LLM 调用（统一超时/异常/空 → None，fail-closed）。

    Args:
        messages: chat messages（system + user）。
        schema: Pydantic 输出模型。
        timeout: 单次调用墙钟预算（秒）。

    Returns:
        校验由调用方负责；此处只保证"调用层失败返回 None"。
    """
    from app.agents.llm_sync import run_llm_structured

    try:
        return run_llm_structured(messages, schema, timeout=timeout)
    except Exception:  # noqa: BLE001 — LLM 任意异常统一 fail-closed
        logger.warning("llm_guard: LLM 调用异常（timeout=%ss），回退", timeout, exc_info=True)
        return None


def llm_with_fallback(
    messages: list[dict],
    schema: Any,
    fallback: Callable[[], Any],
    validate: Callable[[Any], tuple[bool, str]] | None = None,
    timeout: float = 10.0,
) -> tuple[Any, bool]:
    """受约束 LLM + 程序校验 + 失败自动回退。

    Returns:
        (value, used_llm)：used_llm=True 表示采用 LLM 输出（校验通过）；
        False 表示回退 fallback() 的结果（LLM 关闭/超时/异常/校验失败）。
    """
    out = structured_llm(messages, schema, timeout=timeout)
    if out is None:
        return fallback(), False
    if validate is not None:
        ok, reason = validate(out)
        if not ok:
            logger.warning(
                "llm_guard: LLM 输出校验失败（%s），回退确定性结果", reason
            )
            return fallback(), False
    return out, True
