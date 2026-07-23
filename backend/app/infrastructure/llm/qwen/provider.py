"""Qwen LLM Provider — full profile 备选 LLM.

实现 LLMProvider Port 协议。
通过阿里云 DashScope OpenAI 兼容 API 调用通义千问。
"""

import logging

from app.core.config import settings
from app.infrastructure.llm.base import BaseOpenAICompatibleProvider

logger = logging.getLogger(__name__)

# Qwen DashScope 兼容端点默认值
_QWEN_DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


class QwenProvider(BaseOpenAICompatibleProvider):
    """Qwen (通义千问) LLM Provider — full profile 备选.

    使用 DashScope OpenAI 兼容 API。
    当 DeepSeek 不可用时作为降级备选。
    """

    def __init__(self):
        base_url = settings.QWEN_BASE_URL or _QWEN_DEFAULT_BASE_URL
        super().__init__(
            api_key=settings.QWEN_API_KEY,
            base_url=base_url,
            model=settings.QWEN_MODEL,
            timeout=settings.LLM_REQUEST_TIMEOUT,
        )

    @property
    def provider_name(self) -> str:
        return "qwen"
