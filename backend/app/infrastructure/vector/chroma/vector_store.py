"""ChromaDB VectorStore Adapter — lite/full 共用.

实现 VectorStorePort 协议。
"""

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class ChromaVectorStore:
    """ChromaDB 向量存储 — lite/full 共用.

    当前为骨架实现，后续接入真实 ChromaDB 查询。
    """

    def __init__(self, persist_dir: str | None = None):
        self._persist_dir = persist_dir or settings.CHROMA_PERSIST_DIR
        self._available = False
        logger.info(f"ChromaVectorStore: 已初始化, persist_dir={self._persist_dir}")

    async def search(self, query: str, collection: str, top_k: int = 5) -> list[dict]:
        """语义搜索 (mock)."""
        return [
            {
                "id": f"doc_{i}",
                "content": f"Mock document {i} for query: {query[:30]}",
                "metadata": {"source": "mock", "collection": collection},
                "score": 1.0 - (i * 0.1),
            }
            for i in range(min(top_k, 3))
        ]

    async def add_documents(
        self, documents: list[str], metadatas: list[dict], collection: str
    ) -> None:
        """添加文档 (mock)."""
        logger.info(f"Mock: 添加 {len(documents)} 文档到 collection={collection}")

    async def check_connection(self) -> bool:
        """检查 ChromaDB 连接."""
        self._available = True
        return True
