"""LLMProvider Port — V12 baseline.

定义 LLM Provider 接口，不依赖具体 LLM SDK。
V12 §7.7: 增加 structured_chat 结构化输出支持。
"""

from typing import AsyncIterator, Protocol, runtime_checkable

from pydantic import BaseModel


@runtime_checkable
class LLMProvider(Protocol):
    """LLM Provider 接口.

    lite: MockLLMProvider
    full: DeepSeekProvider / QwenProvider
    """

    async def chat(self, messages: list[dict], **kwargs) -> str:
        """发送对话请求，返回文本回答."""
        ...

    async def chat_stream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        """流式对话请求，yield 文本片段."""
        ...

    async def structured_chat(
        self,
        messages: list[dict],
        output_schema: type[BaseModel],
        **kwargs,
    ) -> BaseModel:
        """结构化对话请求，返回 Pydantic 模型实例.

        Provider 使用 JSON 模式或工具调用，
        确保输出可解析为 output_schema 指定的模型。
        """
        ...

    async def check_connection(self) -> bool:
        """检查 LLM 连接."""
        ...

    @property
    def provider_name(self) -> str:
        """Provider 名称."""
        ...
