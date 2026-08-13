"""LLM Provider Adapters — V12 §7.7.

导出 create_llm_provider（工厂函数）、BaseOpenAICompatibleProvider（共享基类）
和降级模块。
"""

from app.infrastructure.llm.base import BaseOpenAICompatibleProvider
from app.infrastructure.llm.degradation import (
    create_degradation_response,
    create_degradation_structured,
)
from app.infrastructure.llm.factory import (
    FallbackLLMProvider,
    create_llm_provider,
    create_llm_provider_with_fallback,
)

__all__ = [
    "BaseOpenAICompatibleProvider",
    "create_llm_provider",
    "create_llm_provider_with_fallback",
    "FallbackLLMProvider",
    "create_degradation_response",
    "create_degradation_structured",
]
