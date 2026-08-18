"""Web Search Provider Adapters — Phase E 会5 B1.

导出 create_web_search_provider（工厂函数）。镜像
`infrastructure/llm` 的包结构：mock / bocha 两个 Provider 实现。
"""

from app.infrastructure.web_search.factory import create_web_search_provider

__all__ = ["create_web_search_provider"]
