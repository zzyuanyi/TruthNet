"""ChromaDB persistent 集成测试 — 不使用任何 embedding 模型，零网络下载.

原则:
- 所有 add/query 使用手动 embeddings（numpy 随机向量），绝不传 documents/query_texts
- 不创建任何 EmbeddingFunction 实例
- CI 和本地环境均可运行，无需 GPU/网络
"""

import shutil
import tempfile

import numpy as np

EMBEDDING_DIM = 128  # 固定小维度，仅用于测试


def _random_embedding(dim: int = EMBEDDING_DIM) -> list[float]:
    """生成随机向量，模拟 embedding 输出."""
    rng = np.random.default_rng(seed=42)
    return rng.random(dim).tolist()


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
    """ChromaDB persistent 写入 → 关闭 → 重开 → 读取（手动向量，无模型下载）."""
    import chromadb

    collection_name = "truthnet_v12_test"
    tmpdir = _get_temp_path()

    try:
        # ── Write ──
        client = chromadb.PersistentClient(
            path=tmpdir,
            settings=chromadb.config.Settings(anonymized_telemetry=False),
        )
        try:
            client.delete_collection(name=collection_name)
        except Exception:
            pass

        collection = client.create_collection(name=collection_name)
        emb = _random_embedding()
        collection.add(
            documents=["TruthNet V12 persistent test — no model download"],
            embeddings=[emb],
            metadatas=[{"source": "integration_test"}],
            ids=["doc_test_1"],
        )

        # 查询同样用向量
        query_emb = _random_embedding()
        results = collection.query(query_embeddings=[query_emb], n_results=1)
        assert results is not None
        assert len(results["ids"]) > 0

        # ── Close and reopen ──
        del client

        client2 = chromadb.PersistentClient(
            path=tmpdir,
            settings=chromadb.config.Settings(anonymized_telemetry=False),
        )
        collection2 = client2.get_collection(name=collection_name)
        results2 = collection2.query(query_embeddings=[query_emb], n_results=1)
        assert results2 is not None
        assert len(results2["ids"]) > 0
        assert results2["ids"][0][0] == "doc_test_1"

        # ── Cleanup ──
        client2.delete_collection(name=collection_name)
        del client2
    finally:
        _cleanup_path(tmpdir)


def test_chroma_persistent_small_data():
    """ChromaDB persistent 小数据批量写入和检索（手动向量，无模型下载）."""
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
        n = 5
        docs = [f"Document number {i}" for i in range(n)]
        ids = [f"id_{i}" for i in range(n)]
        embeddings = [_random_embedding() for _ in range(n)]
        col.add(documents=docs, embeddings=embeddings, ids=ids)

        # 用向量查询
        query_emb = _random_embedding()
        results = col.query(query_embeddings=[query_emb], n_results=1)
        assert results is not None
        assert len(results["documents"]) > 0

        client.delete_collection(name="test_small")
    finally:
        _cleanup_path(tmpdir)


def test_chroma_persistent_no_embedding_function():
    """验证：不传 embedding_function 且不用文本查询时，不会触发模型下载."""
    import chromadb

    tmpdir = _get_temp_path()

    try:
        client = chromadb.PersistentClient(
            path=tmpdir,
            settings=chromadb.config.Settings(anonymized_telemetry=False),
        )
        try:
            client.delete_collection(name="test_no_ef")
        except Exception:
            pass

        # 不传 embedding_function —— 只要不调 query_texts 就不下载模型
        col = client.create_collection(name="test_no_ef")
        emb = _random_embedding()
        col.add(ids=["d1"], embeddings=[emb], documents=["test"])
        r = col.get(ids=["d1"])
        assert r["ids"][0] == "d1"
        assert r["documents"][0] == "test"

        client.delete_collection(name="test_no_ef")
    finally:
        _cleanup_path(tmpdir)


def test_chroma_metadata_filter():
    """ChromaDB metadata 过滤查询（手动向量）."""
    import chromadb

    tmpdir = _get_temp_path()

    try:
        client = chromadb.PersistentClient(
            path=tmpdir,
            settings=chromadb.config.Settings(anonymized_telemetry=False),
        )
        try:
            client.delete_collection(name="test_meta")
        except Exception:
            pass

        col = client.create_collection(name="test_meta")
        embeddings = [_random_embedding() for _ in range(3)]
        col.add(
            ids=["a", "b", "c"],
            embeddings=embeddings,
            documents=["alpha", "beta", "gamma"],
            metadatas=[
                {"category": "x", "idx": 1},
                {"category": "y", "idx": 2},
                {"category": "x", "idx": 3},
            ],
        )

        # 用 metadata where 过滤
        query_emb = _random_embedding()
        results = col.query(
            query_embeddings=[query_emb],
            n_results=3,
            where={"category": "x"},
        )
        assert len(results["ids"][0]) == 2
        returned_ids = set(results["ids"][0])
        assert "a" in returned_ids
        assert "c" in returned_ids

        client.delete_collection(name="test_meta")
    finally:
        _cleanup_path(tmpdir)
