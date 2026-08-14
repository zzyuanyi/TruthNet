"""CompanyCandidateLookup Port — 候选召回接口（v3.1 冻结方案 P0-2/P1-6）.

组件边界（P0-2）：只接收**一个 mention.text**，返回候选；不拆分 mention、
不做历史延续、不做最终选择。Resolver 依赖此 port，不依赖具体 MySQL 类
（P1-6 优先方案第 3 条）。
"""

from typing import Protocol

from app.application.models.company_resolution import CandidateLookupResult


class CompanyCandidateLookup(Protocol):
    """候选召回端口 — 按单个 mention 文本查询候选公司。"""

    def lookup_mention(self, text_query: str, limit: int = 6) -> CandidateLookupResult:
        """查询候选；limit+1 截断判定（P1-3：恰 limit 个不误判 truncated）。

        Returns:
            CandidateLookupResult(matches, truncated)
        """
        ...
