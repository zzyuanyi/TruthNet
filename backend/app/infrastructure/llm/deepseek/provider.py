"""DeepSeek LLM Provider — full profile 主 LLM.

实现 LLMProvider Port 协议。
通过 OpenAI 兼容 API 调用 DeepSeek，使用 AsyncOpenAI SDK。
"""

import logging

from app.core.config import settings
from app.infrastructure.llm.base import BaseOpenAICompatibleProvider

logger = logging.getLogger(__name__)


class DeepSeekProvider(BaseOpenAICompatibleProvider):
    """DeepSeek LLM Provider — full profile 主 LLM.

    使用 DeepSeek OpenAI 兼容 API (https://api.deepseek.com/v1)。
    支持 chat、流式输出、结构化输出（JSON mode）和自动重试。
    """

    def __init__(self):
        super().__init__(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            model=settings.DEEPSEEK_MODEL,
            timeout=settings.LLM_REQUEST_TIMEOUT,
        )

    @property
    def provider_name(self) -> str:
        return "deepseek"
