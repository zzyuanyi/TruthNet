"""DeepSeek LLM Provider — full profile (骨架).

实现 LLMProvider Port 协议。
当前为空实现，不调用真实 DeepSeek API。
"""

import logging
from typing import AsyncIterator

from app.core.config import settings

logger = logging.getLogger(__name__)


class DeepSeekProvider:
    """DeepSeek LLM Provider — full profile 骨架.

    TODO: 接入 DeepSeek API (OpenAI 兼容接口)。
    """

    def __init__(self):
        self._available = False
        logger.info("DeepSeekProvider: 骨架已加载，API 未激活")

    @property
    def provider_name(self) -> str:
        return "deepseek"

    async def check_connection(self) -> bool:
        """检查 DeepSeek API 连接."""
        if not settings.DEEPSEEK_API_KEY:
            logger.warning("DeepSeek API key 未配置")
            return False
        # TODO: 真实 API 连通性检查
        return False

    async def chat(self, messages: list[dict], **kwargs) -> str:
        """对话 (空实现 — 不调用真实 API)."""
        logger.warning("DeepSeekProvider.chat: 未实现")
        return "DeepSeek Provider 未激活，请在 full profile 下配置 DEEPSEEK_API_KEY。"

    async def chat_stream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        """流式对话 (空实现)."""
        logger.warning("DeepSeekProvider.chat_stream: 未实现")
        yield "DeepSeek Provider 未激活。"
