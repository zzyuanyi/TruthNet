"""ChromaDB persistent 集成测试."""

import shutil
import tempfile


def _get_temp_path() -> str:
    """Create a real temp directory path that works on Windows."""
    tmp = tempfile.mkdtemp(prefix="truthnet_chroma_")
    return tmp


def _cleanup_path(path: str) -> None:
    """Clean up temp directory."""
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


def test_chroma_persistent_write_read():
    """ChromaDB persistent 写入、关闭、重开、读取（固定向量，不触发默认嵌入器）。"""
    import chromadb

    collection_name = "truthnet_v12_test"
    tmpdir = _get_temp_path()

    try:
        # Write
        client = chromadb.PersistentClient(
            path=tmpdir,
            settings=chromadb.config.Settings(anonymized_telemetry=False),
        )
        try:
            client.delete_collection(name=collection_name)
        except Exception:
            pass

        collection = client.create_collection(name=collection_name)
        collection.add(
            documents=["TruthNet V12 persistent test"],
            embeddings=[[1.0, 0.0, 0.0, 0.0]],
            metadatas=[{"source": "integration_test"}],
            ids=["doc_test_1"],
        )

        results = collection.query(query_embeddings=[[1.0, 0.0, 0.0, 0.0]], n_results=1)
        assert results is not None
        assert len(results["ids"]) > 0

        # Close and reopen
        del client

        client2 = chromadb.PersistentClient(
            path=tmpdir,
            settings=chromadb.config.Settings(anonymized_telemetry=False),
        )
        collection2 = client2.get_collection(name=collection_name)
        results2 = collection2.query(
            query_embeddings=[[1.0, 0.0, 0.0, 0.0]], n_results=1
        )
        assert results2 is not None
        assert len(results2["ids"]) > 0
        assert results2["ids"][0][0] == "doc_test_1"

        # Cleanup
        client2.delete_collection(name=collection_name)
        del client2
    finally:
        _cleanup_path(tmpdir)


def test_chroma_persistent_small_data():
    """ChromaDB persistent 小数据写入和检索（固定向量，不触发默认嵌入器）。"""
    import chromadb

    tmpdir = _get_temp_path()

    try:
        client = chromadb.PersistentClient(
            path=tmpdir,
            settings=chromadb.config.Settings(anonymized_telemetry=False),
        )
        try:
            client.delete_collection(name="test_small")
        except Exception:
            pass

        col = client.create_collection(name="test_small")
        docs = [f"Document number {i}" for i in range(5)]
        ids = [f"id_{i}" for i in range(5)]
        vectors = [[float(i), 0.0, 0.0, 0.0] for i in range(5)]
        col.add(documents=docs, embeddings=vectors, ids=ids)

        results = col.query(query_embeddings=[[3.0, 0.0, 0.0, 0.0]], n_results=1)
        assert results is not None
        assert len(results["documents"]) > 0
        assert results["ids"][0][0] == "id_3"

        client.delete_collection(name="test_small")
    finally:
        _cleanup_path(tmpdir)
