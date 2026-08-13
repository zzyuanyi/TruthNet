"""Mock LLM Provider — lite profile.

实现 LLMProvider Port 协议。
返回结构化 mock 数据，不调用真实 LLM。
支持 structured_chat（从 chat 文本中解析 JSON 或回退默认值）。
"""

import json
import logging
from typing import AsyncIterator

from pydantic import BaseModel

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

    async def structured_chat(
        self,
        messages: list[dict],
        output_schema: type[BaseModel],
        **kwargs,
    ) -> BaseModel:
        """结构化的 mock 回答.

        尝试从 chat() 响应中解析 JSON；失败则返回 output_schema 默认实例。
        """
        text = await self.chat(messages, **kwargs)

        # 尝试从文本中提取 JSON 片段
        try:
            # 查找可能的 JSON 块
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                json_str = text[start : end + 1]
                return output_schema.model_validate_json(json_str)
        except (json.JSONDecodeError, ValueError) as e:
            logger.debug("MockLLMProvider.structured_chat: JSON 解析失败: %s", e)

        # 回退：使用模型默认值
        try:
            return output_schema()
        except Exception:
            return output_schema.model_validate({})

    async def check_connection(self) -> bool:
        """Mock 始终可用."""
        return True
