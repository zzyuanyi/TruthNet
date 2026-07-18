"""Vector Port Contract 测试 — ChromaDB."""

import shutil
import tempfile

import pytest

from app.application.ports.vector_store import VectorStorePort
from app.infrastructure.vector.chroma.vector_store import ChromaVectorStore


class TestVectorPortContract:
    """ChromaDB 满足 VectorStorePort."""

    def test_adapter_satisfies_port(self):
        store = ChromaVectorStore()
        assert isinstance(store, VectorStorePort)

    @pytest.mark.asyncio
    async def test_check_connection(self):
        store = ChromaVectorStore()
        assert await store.check_connection() is True

    @pytest.mark.asyncio
    async def test_search_returns_list(self):
        store = ChromaVectorStore()
        results = await store.search("test query", "test_collection", top_k=3)
        assert isinstance(results, list)
        assert len(results) >= 0

    def test_chroma_persistent_write_reopen_read(self):
        """ChromaDB persistent: write → reopen → read."""
        import chromadb

        tmpdir = tempfile.mkdtemp(prefix="truthnet_vec_")
        try:
            client = chromadb.PersistentClient(
                path=tmpdir,
                settings=chromadb.config.Settings(anonymized_telemetry=False),
            )
            col = client.create_collection(name="test_port_contract")
            col.add(documents=["test doc"], ids=["id_1"])
            results = col.query(query_texts=["test"], n_results=1)
            assert len(results["ids"]) > 0

            del client
            client2 = chromadb.PersistentClient(
                path=tmpdir,
                settings=chromadb.config.Settings(anonymized_telemetry=False),
            )
            col2 = client2.get_collection(name="test_port_contract")
            results2 = col2.query(query_texts=["test"], n_results=1)
            assert results2["ids"][0][0] == "id_1"
            client2.delete_collection(name="test_port_contract")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
