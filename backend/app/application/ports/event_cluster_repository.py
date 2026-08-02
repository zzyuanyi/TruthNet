"""EventClusterRepository Port — Phase C 任务 15.

事件簇交接数据的访问接口，不依赖具体数据库。
"""

from datetime import date
from typing import Protocol, runtime_checkable

from app.domain.events.contracts import EventClusterRecord


@runtime_checkable
class EventClusterRepository(Protocol):
    """事件簇数据仓库接口."""

    async def list_by_company(
        self,
        wind_code: str,
        start_date: date,
        end_date: date,
    ) -> list[EventClusterRecord]:
        """按公司 + 日期范围列出事件簇."""
        ...

    async def get_by_id(
        self,
        event_cluster_id: str,
    ) -> EventClusterRecord | None:
        """按 ID 获取事件簇."""
        ...
