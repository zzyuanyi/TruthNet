"""LLM Provider 单元测试 — V12 任务 #8.

测试覆盖:
- Protocol 合规
- Mock Provider 结构化输出
- DeepSeek Provider (mock AsyncOpenAI)
- Qwen Provider (mock AsyncOpenAI)
- 重试机制
- 连接失败
- Provider 工厂
- 降级模板
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel, Field

from app.application.ports.llm_provider import LLMProvider
from app.core.enums import BackendType
from app.infrastructure.llm.degradation import (
    create_degradation_response,
    create_degradation_structured,
)
from app.infrastructure.llm.deepseek.provider import DeepSeekProvider
from app.infrastructure.llm.factory import (
    FallbackLLMProvider,
    create_llm_provider,
)
from app.infrastructure.llm.mock.provider import MockLLMProvider
from app.infrastructure.llm.qwen.provider import QwenProvider


# ── 测试用 Schema ─────────────────────────────────────────


class OutputFixture(BaseModel):
    answer: str = ""
    confidence: float = 0.0
    sources: list[str] = Field(default_factory=list)


# ── Mock DeepSeek Provider ────────────────────────────────


class TestDeepSeekProviderProtocol:
    """DeepSeekProvider Protocol 合规测试."""

    def test_satisfies_protocol(self):
        provider = DeepSeekProvider()
        assert isinstance(provider, LLMProvider)

    def test_provider_name(self):
        provider = DeepSeekProvider()
        assert provider.provider_name == "deepseek"
        assert provider.provider_name == BackendType.DEEPSEEK


class TestQwenProviderProtocol:
    """QwenProvider Protocol 合规测试."""

    def test_satisfies_protocol(self):
        provider = QwenProvider()
        assert isinstance(provider, LLMProvider)

    def test_provider_name(self):
        provider = QwenProvider()
        assert provider.provider_name == "qwen"
        assert provider.provider_name == BackendType.QWEN


class TestMockProviderStructuredChat:
    """MockLLMProvider structured_chat 测试."""

    @pytest.mark.asyncio
    async def test_structured_chat_returns_model_instance(self):
        provider = MockLLMProvider()
        result = await provider.structured_chat(
            [{"role": "user", "content": "分析风险"}],
            OutputFixture,
        )
        assert isinstance(result, OutputFixture)
        assert isinstance(result.answer, str)


# ── Mock AsyncOpenAI 测试 ─────────────────────────────────


class MockChatCompletion:
    """模拟 OpenAI chat completion 响应."""

    class Choice:
        class Message:
            content: str

            def __init__(self, content: str):
                self.content = content

        def __init__(self, content: str):
            self.message = self.Message(content)

    def __init__(self, content: str):
        self.choices = [self.Choice(content)]


def _mock_async_openai():
    """创建 mock AsyncOpenAI 客户端."""
    mock = MagicMock()
    mock.chat.completions.create = AsyncMock()
    return mock


class TestDeepSeekProviderChat:
    """DeepSeek 正常 chat 测试（mock AsyncOpenAI）."""

    @pytest.mark.asyncio
    async def test_chat_success(self):
        provider = DeepSeekProvider()
        mock_client = _mock_async_openai()
        mock_client.chat.completions.create.return_value = MockChatCompletion(
            "DeepSeek 分析结果"
        )
        provider._client = mock_client
        provider._available = True

        result = await provider.chat([{"role": "user", "content": "分析康美药业"}])
        assert result == "DeepSeek 分析结果"
        mock_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_without_client_returns_unavailable(self):
        provider = DeepSeekProvider()
        provider._client = None
        provider._available = False

        result = await provider.chat([{"role": "user", "content": "分析"}])
        assert "未激活" in result or "API_KEY" in result


class TestDeepSeekProviderChatStream:
    """DeepSeek 流式 chat 测试."""

    @pytest.mark.asyncio
    async def test_chat_stream_success(self):
        provider = DeepSeekProvider()

        # 模拟流式响应 chunks
        class MockStreamChunk:
            class Choice:
                class Delta:
                    def __init__(self, content: str | None):
                        self.content = content

                def __init__(self, content: str | None):
                    self.delta = self.Delta(content)

            def __init__(self, content: str | None):
                self.choices = [self.Choice(content)]

        # 此处不直接测真实 API，只测 client=None 时的行为
        provider._client = None
        chunks = []
        async for chunk in provider.chat_stream([{"role": "user", "content": "测试"}]):
            chunks.append(chunk)
        assert len(chunks) == 1
        assert "未激活" in chunks[0] or "API_KEY" in chunks[0]

    @pytest.mark.asyncio
    async def test_chat_stream_yields_chunks(self):
        """测试流式输出 (使用 mock client)."""
        provider = DeepSeekProvider()
        mock_client = _mock_async_openai()

        chunks = ["Deep", "Seek", " 回答"]
        mock_chunks = []
        for c in chunks:
            m = MagicMock()
            m.choices = [MagicMock()]
            m.choices[0].delta.content = c
            mock_chunks.append(m)

        # 创建异步迭代器
        async def _async_iter():
            for c in mock_chunks:
                yield c

        mock_client.chat.completions.create.return_value = _async_iter()
        provider._client = mock_client
        provider._available = True

        result = []
        async for chunk in provider.chat_stream([{"role": "user", "content": "测试"}]):
            result.append(chunk)

        assert "".join(result) == "DeepSeek 回答"


class TestDeepSeekProviderStructuredChat:
    """DeepSeek 结构化输出测试."""

    @pytest.mark.asyncio
    async def test_structured_chat_success(self):
        provider = DeepSeekProvider()
        mock_client = _mock_async_openai()

        output_data = {
            "answer": "风险较高",
            "confidence": 0.85,
            "sources": ["source1"],
        }
        mock_client.chat.completions.create.return_value = MockChatCompletion(
            json.dumps(output_data, ensure_ascii=False)
        )
        provider._client = mock_client
        provider._available = True

        result = await provider.structured_chat(
            [{"role": "user", "content": "分析"}],
            OutputFixture,
        )
        assert isinstance(result, OutputFixture)
        assert result.answer == "风险较高"
        assert result.confidence == 0.85

    @pytest.mark.asyncio
    async def test_structured_chat_no_client(self):
        provider = DeepSeekProvider()
        provider._client = None
        provider._available = False

        result = await provider.structured_chat(
            [{"role": "user", "content": "分析"}],
            OutputFixture,
        )
        assert isinstance(result, OutputFixture)

    @pytest.mark.asyncio
    async def test_structured_chat_json_parse_error_retry(self):
        """测试 JSON 解析失败后重试成功."""
        provider = DeepSeekProvider()
        mock_client = _mock_async_openai()

        # 第一次返回非法 JSON，第二次返回正确 JSON
        output_data = {
            "answer": "最终答案",
            "confidence": 0.9,
            "sources": ["src"],
        }
        mock_client.chat.completions.create.side_effect = [
            MockChatCompletion("not valid json {{{"),
            MockChatCompletion(json.dumps(output_data, ensure_ascii=False)),
        ]
        provider._client = mock_client
        provider._available = True

        result = await provider.structured_chat(
            [{"role": "user", "content": "分析"}],
            OutputFixture,
        )
        assert isinstance(result, OutputFixture)
        assert result.answer == "最终答案"
        # 应该调用了两次
        assert mock_client.chat.completions.create.call_count == 2


class TestDeepSeekProviderRetry:
    """DeepSeek 重试测试."""

    @pytest.mark.asyncio
    async def test_chat_retry_on_transient_error(self):
        """测试瞬时错误自动重试成功."""
        from openai import APIStatusError

        provider = DeepSeekProvider()
        mock_client = _mock_async_openai()

        # 第一次返回 503 → 重试 → 第二次成功
        mock_client.chat.completions.create.side_effect = [
            APIStatusError("503 Service Unavailable", response=MagicMock(), body={}),
            MockChatCompletion("重试后成功"),
        ]
        provider._client = mock_client
        provider._available = True

        result = await provider.chat([{"role": "user", "content": "测试"}])
        assert "重试后成功" in result


class TestDeepSeekProviderConnectionFailure:
    """DeepSeek 连接失败测试."""

    @pytest.mark.asyncio
    async def test_check_connection_no_client(self):
        provider = DeepSeekProvider()
        provider._client = None
        result = await provider.check_connection()
        assert result is False

    @pytest.mark.asyncio
    async def test_check_connection_api_error(self):
        from openai import APIConnectionError

        provider = DeepSeekProvider()
        mock_client = _mock_async_openai()
        mock_client.chat.completions.create.side_effect = APIConnectionError(
            request=MagicMock()
        )
        provider._client = mock_client

        result = await provider.check_connection()
        assert result is False
        assert provider._available is False


# ── Provider 工厂测试 ─────────────────────────────────────


class TestProviderFactory:
    """create_llm_provider 工厂测试."""

    def test_create_mock_provider(self):
        provider = create_llm_provider("mock")
        assert isinstance(provider, MockLLMProvider)
        assert provider.provider_name == "mock"

    def test_create_deepseek_provider(self):
        provider = create_llm_provider("deepseek")
        assert isinstance(provider, DeepSeekProvider)
        assert provider.provider_name == "deepseek"

    def test_create_qwen_provider(self):
        provider = create_llm_provider("qwen")
        assert isinstance(provider, QwenProvider)
        assert provider.provider_name == "qwen"

    def test_create_unknown_falls_back_to_mock(self):
        provider = create_llm_provider("unknown")
        assert isinstance(provider, MockLLMProvider)

    def test_create_llm_provider_satisfies_protocol(self):
        for backend in ["mock", "deepseek", "qwen"]:
            provider = create_llm_provider(backend)
            assert isinstance(
                provider, LLMProvider
            ), f"{backend} not satisfying protocol"


# ── 降级模板测试 ──────────────────────────────────────────


class TestDegradationTemplates:
    """降级模板测试."""

    def test_create_degradation_response_returns_string(self):
        result = create_degradation_response("finance_analysis")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_create_degradation_response_general(self):
        result = create_degradation_response("general")
        assert "LLM" in result

    def test_create_degradation_response_unknown_type(self):
        result = create_degradation_response("unknown_type")
        assert isinstance(result, str)

    def test_create_degradation_structured_returns_model(self):
        result = create_degradation_structured(OutputFixture, "连接失败")
        assert isinstance(result, OutputFixture)

    def test_create_degradation_structured_default_values(self):
        result = create_degradation_structured(OutputFixture, "连接失败")
        assert result.answer == ""
        assert result.confidence == 0.0


# ── FallbackLLMProvider 测试 ──────────────────────────────


class TestFallbackLLMProvider:
    """降级 Provider 包装测试."""

    @pytest.mark.asyncio
    async def test_primary_success(self):
        primary = MockLLMProvider()
        fallback = FallbackLLMProvider(primary)

        result = await fallback.chat([{"role": "user", "content": "测试"}])
        assert "Mock" in result

    @pytest.mark.asyncio
    async def test_fallback_when_primary_fails(self):
        """主 Provider 失败时降级到备选."""
        primary = MockLLMProvider()

        class FailingProvider:
            @property
            def provider_name(self) -> str:
                return "failing"

            async def chat(self, messages, **kwargs) -> str:
                raise RuntimeError("主 Provider 故障")

        fallback = FallbackLLMProvider(
            FailingProvider(),
            fallback=primary,
            task_type="general",
        )

        result = await fallback.chat([{"role": "user", "content": "测试"}])
        assert "Mock" in result

    @pytest.mark.asyncio
    async def test_degradation_when_all_fail(self):
        """全部 Provider 失败时返回降级模板."""

        class AlwaysFail:
            @property
            def provider_name(self) -> str:
                return "always_fail"

            async def chat(self, messages, **kwargs) -> str:
                raise RuntimeError("故障")

        fallback = FallbackLLMProvider(
            AlwaysFail(),
            fallback=AlwaysFail(),
            task_type="general",
        )

        result = await fallback.chat([{"role": "user", "content": "测试"}])
        assert "LLM" in result
        assert "故障" in result

    @pytest.mark.asyncio
    async def test_structured_chat_fallback(self):
        """structured_chat 降级测试."""

        class AlwaysFail:
            @property
            def provider_name(self) -> str:
                return "failing"

            async def structured_chat(self, messages, output_schema, **kwargs):
                raise RuntimeError("故障")

        fallback = FallbackLLMProvider(AlwaysFail(), task_type="general")
        result = await fallback.structured_chat(
            [{"role": "user", "content": "测试"}], OutputFixture
        )
        assert isinstance(result, OutputFixture)

    @pytest.mark.asyncio
    async def test_check_connection_delegates_to_primary(self):
        primary = MockLLMProvider()
        fallback = FallbackLLMProvider(primary)
        assert await fallback.check_connection() is True


# ── ChatStream 异常降级测试 ────────────────────────────────


class TestChatStreamDegradation:
    """流式降级测试."""

    @pytest.mark.asyncio
    async def test_fallback_provider_stream(self):
        """主 Provider 流式失败时降级到备选 Provider 流式."""

        class FailingStream:
            @property
            def provider_name(self) -> str:
                return "failing"

            async def chat_stream(self, messages, **kwargs):
                if False:  # never runs
                    yield
                raise RuntimeError("流式中断")

        mock = MockLLMProvider()
        fallback = FallbackLLMProvider(FailingStream(), fallback=mock)

        chunks = []
        async for chunk in fallback.chat_stream([{"role": "user", "content": "测试"}]):
            chunks.append(chunk)
        assert len(chunks) > 0
        full = "".join(chunks)
        assert "Mock" in full

    @pytest.mark.asyncio
    async def test_degradation_stream_when_all_fail(self):
        """全部流式失败时返回降级模板."""

        class AlwaysFail:
            @property
            def provider_name(self) -> str:
                return "always_fail"

            async def chat_stream(self, messages, **kwargs):
                if False:
                    yield
                raise RuntimeError("故障")

        fallback = FallbackLLMProvider(AlwaysFail(), task_type="general")
        chunks = []
        async for chunk in fallback.chat_stream([{"role": "user", "content": "测试"}]):
            chunks.append(chunk)
        full = "".join(chunks)
        assert "LLM" in full
