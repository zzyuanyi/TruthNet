"""WebSearchProvider Port — Phase E 会5 B1 联网搜索.

定义 Web Search Provider 接口与统一 SearchResult 数据契约，不依赖具体
搜索引擎 SDK。镜像 LLM Provider 的 `application/ports/llm_provider.py` 模式。

统一契约（换 provider 的关键）：
- 所有 provider 在内部把原始响应归一化到 SearchResult；
- `snippet` 语义统一为「可解析的正文/摘要」——下游只读此字段做解析；
- 日期类字段全部可选（各 provider 原始覆盖差异大，下游不得强依赖）。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """单条联网搜索结果（provider 归一化后的统一契约）.

    字段全部可空：不同 provider 原始响应覆盖差异大，下游不得强依赖
    任何单字段（尤其 published_at），必须做兜底。
    """

    title: str = Field(default="", description="结果标题")
    url: str = Field(default="", description="结果 URL")
    snippet: str = Field(
        default="", description="可解析正文/摘要（下游只读此字段做解析）"
    )
    domain: str = Field(default="", description="来源域名")
    published_at: str | None = Field(default=None, description="发布日期（可空）")
    source: str = Field(default="", description="Provider 名称（来源标注用）")


@runtime_checkable
class WebSearchProvider(Protocol):
    """Web Search Provider 接口.

    off: 不创建任何 Provider（工厂返回 None，零副作用）
    mock: MockWebSearchProvider
    full: BochaWebSearchProvider 等真实实现
    """

    @property
    def provider_name(self) -> str:
        """Provider 名称."""
        ...

    async def search(
        self, query: str, max_results: int | None = None
    ) -> list[SearchResult]:
        """联网搜索 query，返回归一化结果；失败/无结果返回空列表."""
        ...
