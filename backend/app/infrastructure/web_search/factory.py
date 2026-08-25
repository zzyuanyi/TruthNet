"""Web Search Provider 工厂 — Phase E 会5 B1.

根据 WEB_SEARCH_BACKEND 配置创建对应的 Provider 实例。
- off（默认）= 不创建，返回 None → 业务侧行为与现状完全一致；
- mock = 本地测试/演示；
- bocha = 博查真实联网（中文通用搜索，数据源拍板后启用，未拍板保持 off）；
- anysearch = AnySearch（带 A 股代码走 finance MCP 垂直域；无码 query 可走
  REST /v1/search 通用入口，但 provider 会做相关性 Gate，低质结果返回空；
  免费注册 Key 见调研文档 §2.4）。

镜像 `infrastructure/llm/factory.py` 的注册表模式。
换 provider = 新增类 + 在 _PROVIDER_CLASSES 登记一行 + `.env` 改后端名。
"""

from __future__ import annotations

import logging

from app.application.ports.web_search_provider import WebSearchProvider
from app.core.config import settings
from app.infrastructure.web_search.anysearch.provider import AnySearchWebSearchProvider
from app.infrastructure.web_search.bocha.provider import BochaWebSearchProvider
from app.infrastructure.web_search.coze.provider import CozeWebSearchProvider
from app.infrastructure.web_search.mock.provider import MockWebSearchProvider

logger = logging.getLogger(__name__)

_PROVIDER_CLASSES: dict[str, type] = {
    "mock": MockWebSearchProvider,
    "bocha": BochaWebSearchProvider,
    "anysearch": AnySearchWebSearchProvider,
    # 平台托管联网搜索（沙箱预置 SDK、免 Key）：地球舆情深挖等场景默认走此源
    "coze": CozeWebSearchProvider,
}


def create_web_search_provider(
    backend: str | None = None,
) -> WebSearchProvider | None:
    """根据配置创建 Web Search Provider 实例.

    Args:
        backend: 指定后端；None 则使用 settings.WEB_SEARCH_BACKEND。

    Returns:
        Provider 实例；`off` / 未知后端 → None（off 语义，调用方不联网）。
    """
    backend = (backend or settings.WEB_SEARCH_BACKEND or "off").lower()
    if backend == "off":
        return None
    provider_cls = _PROVIDER_CLASSES.get(backend)
    if provider_cls is None:
        logger.warning("未知 WEB_SEARCH_BACKEND=%s，按 off 处理（不联网）", backend)
        return None
    logger.info("创建 Web Search Provider: %s", backend)
    return provider_cls()
