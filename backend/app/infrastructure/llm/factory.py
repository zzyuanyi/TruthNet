"""LLM Provider 工厂 — V12 §7.7.

根据 LLM_BACKEND 配置创建对应的 Provider 实例。
支持主 Provider + 备选 Provider 的降级包装。
"""

import logging

from app.application.ports.llm_provider import LLMProvider
from app.core.config import settings
from app.infrastructure.llm.degradation import create_degradation_response
from app.infrastructure.llm.deepseek.provider import DeepSeekProvider
from app.infrastructure.llm.mock.provider import MockLLMProvider
from app.infrastructure.llm.qwen.provider import QwenProvider

logger = logging.getLogger(__name__)

# ── Provider 注册表 ──────────────────────────────────────

_PROVIDER_CLASSES: dict[str, type] = {
    "deepseek": DeepSeekProvider,
    "qwen": QwenProvider,
    "mock": MockLLMProvider,
}


def create_llm_provider(backend: str | None = None) -> LLMProvider:
    """根据配置创建 LLM Provider 实例.

    Args:
        backend: 指定后端，None 则使用 settings.LLM_BACKEND

    Returns:
        LLMProvider 实例。
    """
    backend = backend or settings.LLM_BACKEND
    provider_cls = _PROVIDER_CLASSES.get(backend)
    if provider_cls is None:
        logger.warning(
            "未知 LLM_BACKEND=%s，回退到 MockLLMProvider", backend
        )
        return MockLLMProvider()
    logger.info("创建 LLM Provider: %s", backend)
    return provider_cls()


class FallbackLLMProvider:
    """带降级的 LLM Provider 包装.

    调用链：
    1. 主 Provider → 成功则返回
    2. 主 Provider 失败 → 备选 Provider（如已配置）
    3. 全部失败 → 模板降级
    """

    def __init__(
        self,
        primary: LLMProvider,
        fallback: LLMProvider | None = None,
        task_type: str = "general",
    ):
        self._primary = primary
        self._fallback = fallback
        self._task_type = task_type

    @property
    def provider_name(self) -> str:
        return self._primary.provider_name

    async def chat(self, messages: list[dict], **kwargs) -> str:
        """带降级的 chat."""
        try:
            return await self._primary.chat(messages, **kwargs)
        except Exception as e:
            logger.warning("主 Provider (%s) chat 失败: %s", self.provider_name, e)

        if self._fallback is not None:
            try:
                logger.info("尝试备选 Provider (%s)", self._fallback.provider_name)
                return await self._fallback.chat(messages, **kwargs)
            except Exception as e:
                logger.warning("备选 Provider chat 也失败: %s", e)

        return create_degradation_response(self._task_type)

    async def chat_stream(self, messages: list[dict], **kwargs):
        """带降级的流式 chat."""
        try:
            async for chunk in self._primary.chat_stream(messages, **kwargs):
                yield chunk
            return
        except Exception as e:
            logger.warning("主 Provider (%s) chat_stream 失败: %s", self.provider_name, e)

        if self._fallback is not None:
            try:
                async for chunk in self._fallback.chat_stream(messages, **kwargs):
                    yield chunk
                return
            except Exception as e:
                logger.warning("备选 Provider chat_stream 也失败: %s", e)

        yield create_degradation_response(self._task_type)

    async def structured_chat(
        self, messages: list[dict], output_schema, **kwargs
    ):
        """带降级的 structured_chat."""
        try:
            return await self._primary.structured_chat(
                messages, output_schema, **kwargs
            )
        except Exception as e:
            logger.warning(
                "主 Provider (%s) structured_chat 失败: %s", self.provider_name, e
            )

        if self._fallback is not None:
            try:
                return await self._fallback.structured_chat(
                    messages, output_schema, **kwargs
                )
            except Exception as e:
                logger.warning("备选 Provider structured_chat 也失败: %s", e)

        from app.infrastructure.llm.degradation import create_degradation_structured

        return create_degradation_structured(output_schema, "全部 Provider 不可用")

    async def check_connection(self) -> bool:
        """检查连接 — 优先检查主 Provider."""
        return await self._primary.check_connection()


def create_llm_provider_with_fallback(task_type: str = "general") -> FallbackLLMProvider:
    """创建带降级链的 Provider 包装.

    根据 LLM_FALLBACK_BACKEND 配置自动选择备选 Provider。
    """
    primary = create_llm_provider()

    fallback_backend = settings.LLM_FALLBACK_BACKEND
    fallback = None
    if fallback_backend and fallback_backend != settings.LLM_BACKEND:
        fallback = create_llm_provider(fallback_backend)
        logger.info(
            "已配置降级链: %s → %s",
            primary.provider_name,
            fallback.provider_name,
        )

    return FallbackLLMProvider(
        primary=primary,
        fallback=fallback,
        task_type=task_type,
    )
