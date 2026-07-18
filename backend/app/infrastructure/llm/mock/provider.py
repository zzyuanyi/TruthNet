"""Mock LLM Provider — lite profile.

实现 LLMProvider Port 协议。
返回结构化 mock 数据，不调用真实 LLM。
"""

import logging
from typing import AsyncIterator

logger = logging.getLogger(__name__)


class MockLLMProvider:
    """Mock LLM Provider — lite profile.

    返回预设 mock 回答，用于本地开发和 CI 测试。
    """

    @property
    def provider_name(self) -> str:
        return "mock"

    async def chat(self, messages: list[dict], **kwargs) -> str:
        """返回 mock 回答."""
        user_msg = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        return (
            f"Mock 回答：关于「{user_msg[:50]}...」的问题，"
            "当前使用 Mock LLM Provider（lite profile）。"
            "V12 基线已就绪，待接入 DeepSeek/Qwen 真实 Provider。"
        )

    async def chat_stream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        """流式 mock 回答."""
        answer = await self.chat(messages, **kwargs)
        for i in range(0, len(answer), 10):
            yield answer[i : i + 10]

    async def check_connection(self) -> bool:
        """Mock 始终可用."""
        return True
