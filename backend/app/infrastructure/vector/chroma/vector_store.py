"""ChromaDB VectorStore Adapter — 真实 ChromaDB 查询。

与 chroma_embed.py / chroma_import.py 统一：
  持久化目录: CHROMA_PERSIST_DIR
  集合名:     research_report_chunks
  嵌入模型:   BAAI/bge-small-zh-v1.5（查询时用 query_embeddings）
"""

from __future__ import annotations

import logging
import os

from app.core.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "research_report_chunks"

_embedding_model = None


def _get_embedding_model():
    """惰性加载 BGE 嵌入模型（优先本地缓存，其次 ModelScope）。"""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer

            try:
                from modelscope import snapshot_download

                model_dir = snapshot_download(
                    settings.EMBEDDING_MODEL, cache_dir=settings.EMBEDDING_CACHE_DIR
                )
                _embedding_model = SentenceTransformer(model_dir, device="cpu")
                logger.info("BGE 模型已通过 ModelScope 加载")
            except Exception:
                # 回退：从本地缓存加载
                _embedding_model = SentenceTransformer(
                    settings.EMBEDDING_MODEL,
                    cache_folder=settings.EMBEDDING_CACHE_DIR,
                    device="cpu",
                )
                logger.info("BGE 模型已从本地缓存加载")
        except Exception:
            logger.exception("BGE 嵌入模型加载失败")
            return None
    return _embedding_model


class ChromaVectorStore:
    """ChromaDB 向量存储 — 基于 chromadb.PersistentClient。"""

    def __init__(self, persist_dir: str | None = None):
        self._persist_dir = persist_dir or settings.CHROMA_PERSIST_DIR
        self._client = None
        self._available = False
        logger.info(f"ChromaVectorStore: 已初始化, persist_dir={self._persist_dir}")

    def _get_client(self):
        """惰性初始化 ChromaDB 客户端。"""
        if self._client is None:
            try:
                import chromadb
                from chromadb.config import Settings as ChromaSettings

                os.makedirs(self._persist_dir, exist_ok=True)
                # 关闭匿名遥测：消除测试输出噪声 + 离线环境兼容
                self._client = chromadb.PersistentClient(
                    path=self._persist_dir,
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
                self._available = True
            except Exception:
                logger.exception("ChromaDB 客户端初始化失败")
                self._available = False
        return self._client

    async def search(
        self, query: str, collection: str = COLLECTION_NAME, top_k: int = 5
    ) -> list[dict]:
        """语义搜索 — 用 BGE 模型生成查询向量，query_embeddings 查询。

        先检查集合是否存在，避免空库无意义下载模型。
        """
        client = self._get_client()
        if client is None:
            return []

        # 集合不存在 → 直接返回空，不加载模型
        try:
            client.get_collection(collection)
        except Exception:
            return []

        # 生成查询向量（与导入时同一模型、同一维度）
        model = _get_embedding_model()
        if model is None:
            return []
        try:
            query_emb = model.encode([query], normalize_embeddings=True)
        except Exception:
            logger.exception("查询向量生成失败")
            return []

        try:
            col = client.get_collection(collection)
            results = col.query(query_embeddings=query_emb.tolist(), n_results=top_k)
        except Exception:
            logger.exception("ChromaDB 查询失败: collection=%s", collection)
            return []

        if not results or not results.get("ids") or not results["ids"][0]:
            return []

        items = []
        ids = results["ids"][0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        for i in range(len(ids)):
            items.append(
                {
                    "id": ids[i],
                    "content": docs[i] if i < len(docs) else "",
                    "metadata": metas[i] if i < len(metas) else {},
                    "score": max(0.0, min(1.0, 1.0 - float(distances[i])))
                    if i < len(distances)
                    else 0.0,
                }
            )
        return items

    async def add_documents(
        self,
        documents: list[str],
        metadatas: list[dict],
        collection: str = COLLECTION_NAME,
        ids: list[str] | None = None,
    ) -> None:
        """添加文档到指定 collection（含嵌入计算）。"""
        client = self._get_client()
        if client is None:
            return

        model = _get_embedding_model()
        if model is None:
            return

        try:
            embeddings = model.encode(documents, normalize_embeddings=True)
        except Exception:
            logger.exception("文档嵌入生成失败")
            return

        try:
            col = client.get_or_create_collection(
                collection, metadata={"hnsw:space": "cosine"}
            )
            if ids is None:
                import uuid

                ids = [uuid.uuid4().hex[:16] for _ in documents]
            col.add(
                documents=documents,
                embeddings=embeddings.tolist(),
                metadatas=metadatas,
                ids=ids,
            )
            logger.info("添加 %d 文档到 collection=%s", len(documents), collection)
        except Exception:
            logger.exception("ChromaDB 添加文档失败: collection=%s", collection)

    async def check_connection(self) -> bool:
        """检查 ChromaDB 连接。"""
        if self._client is None:
            self._get_client()
        return self._available
