"""LLM Port 协议契约测试 — V12 任务 #8.

验证全部 3 个 Provider 满足 LLMProvider 协议，
且 provider_name 与 BackendType 枚举一致。
"""

import pytest

from app.application.ports.llm_provider import LLMProvider
from app.core.enums import BackendType
from app.infrastructure.llm.deepseek.provider import DeepSeekProvider
from app.infrastructure.llm.mock.provider import MockLLMProvider
from app.infrastructure.llm.qwen.provider import QwenProvider


class TestLLMPortContract:
    """LLM Port 契约测试 — 全部 Adapter 满足协议."""

    @pytest.mark.parametrize(
        "provider_cls,expected_name,backend_type",
        [
            (MockLLMProvider, "mock", BackendType.MOCK),
            (DeepSeekProvider, "deepseek", BackendType.DEEPSEEK),
            (QwenProvider, "qwen", BackendType.QWEN),
        ],
    )
    def test_provider_satisfies_protocol(
        self, provider_cls, expected_name, backend_type
    ):
        """每个 Provider 都满足 LLMProvider 协议."""
        provider = provider_cls()
        assert isinstance(provider, LLMProvider), (
            f"{provider_cls.__name__} 不满足 LLMProvider 协议"
        )

    @pytest.mark.parametrize(
        "provider_cls,expected_name,backend_type",
        [
            (MockLLMProvider, "mock", BackendType.MOCK),
            (DeepSeekProvider, "deepseek", BackendType.DEEPSEEK),
            (QwenProvider, "qwen", BackendType.QWEN),
        ],
    )
    def test_provider_name_matches_enum(
        self, provider_cls, expected_name, backend_type
    ):
        """provider_name 与 BackendType 枚举一致."""
        provider = provider_cls()
        assert provider.provider_name == expected_name
        assert provider.provider_name == backend_type

    @pytest.mark.parametrize(
        "provider_cls",
        [MockLLMProvider, DeepSeekProvider, QwenProvider],
    )
    def test_provider_has_all_methods(self, provider_cls):
        """每个 Provider 实现了全部必需方法."""
        provider = provider_cls()
        assert hasattr(provider, "chat")
        assert callable(provider.chat)
        assert hasattr(provider, "chat_stream")
        assert callable(provider.chat_stream)
        assert hasattr(provider, "structured_chat")
        assert callable(provider.structured_chat)
        assert hasattr(provider, "check_connection")
        assert callable(provider.check_connection)
        assert hasattr(provider, "provider_name")
