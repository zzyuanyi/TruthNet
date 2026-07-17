"""VectorStorePort — V12 baseline.

定义向量存储/检索接口，不依赖具体向量数据库。
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class VectorStorePort(Protocol):
    """向量存储接口.

    lite/full 均使用 ChromaDB。
    """

    async def search(self, query: str, collection: str, top_k: int = 5) -> list[dict]:
        """语义搜索."""
        ...

    async def add_documents(
        self, documents: list[str], metadatas: list[dict], collection: str
    ) -> None:
        """添加文档."""
        ...

    async def check_connection(self) -> bool:
        """检查向量库连接."""
        ...
