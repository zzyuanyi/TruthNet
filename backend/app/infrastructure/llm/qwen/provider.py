"""Qwen LLM Provider — full profile 备选 (骨架).

实现 LLMProvider Port 协议。
当前为空实现，不调用真实 Qwen API。
"""

import logging
from typing import AsyncIterator

from app.core.config import settings

logger = logging.getLogger(__name__)


class QwenProvider:
    """Qwen (通义千问) LLM Provider — full profile 备选.

    TODO: 接入 Qwen API (OpenAI 兼容接口)。
    """

    def __init__(self):
        self._available = False
        logger.info("QwenProvider: 骨架已加载，API 未激活")

    @property
    def provider_name(self) -> str:
        return "qwen"

    async def check_connection(self) -> bool:
        """检查 Qwen API 连接."""
        if not settings.QWEN_API_KEY:
            logger.warning("Qwen API key 未配置")
            return False
        return False

    async def chat(self, messages: list[dict], **kwargs) -> str:
        """对话 (空实现)."""
        logger.warning("QwenProvider.chat: 未实现")
        return "Qwen Provider 未激活，请在 full profile 下配置 QWEN_API_KEY。"

    async def chat_stream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        """流式对话 (空实现)."""
        logger.warning("QwenProvider.chat_stream: 未实现")
        yield "Qwen Provider 未激活。"
