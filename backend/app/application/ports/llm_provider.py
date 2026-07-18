"""LLMProvider Port — V12 baseline.

定义 LLM Provider 接口，不依赖具体 LLM SDK。
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """LLM Provider 接口.

    lite: MockLLMProvider
    full: DeepSeekProvider / QwenProvider
    """

    async def chat(self, messages: list[dict], **kwargs) -> str:
        """发送对话请求，返回文本回答."""
        ...

    async def chat_stream(self, messages: list[dict], **kwargs):
        """流式对话请求，yield 文本片段."""
        ...

    async def check_connection(self) -> bool:
        """检查 LLM 连接."""
        ...

    @property
    def provider_name(self) -> str:
        """Provider 名称."""
        ...
