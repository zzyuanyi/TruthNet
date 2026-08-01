"""ChromaDB VectorStore 单测：使用 fake embedding monkeypatch，不下载真实模型。"""

import shutil
import tempfile
from unittest.mock import patch

import numpy as np
import pytest
from app.infrastructure.vector.chroma.vector_store import ChromaVectorStore

FAKE_EMBED_DIM = 8


def fake_encode(texts, *args, **kwargs):
    """返回固定维度的随机向量，模拟嵌入。"""
    if isinstance(texts, str):
        texts = [texts]
    return (
        np.random.default_rng(42)
        .random((len(texts), FAKE_EMBED_DIM))
        .astype(np.float32)
    )


@pytest.fixture
def temp_chroma_dir():
    d = tempfile.mkdtemp(suffix="_chroma_test")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.mark.asyncio
@patch(
    "app.infrastructure.vector.chroma.vector_store._get_embedding_model",
    return_value=type("FakeModel", (), {"encode": staticmethod(fake_encode)})(),
)
async def test_search_returns_results_with_fake_model(mock_model, temp_chroma_dir):
    """写入文档 → 查询 → 断言非空 + 分数范围。"""
    store = ChromaVectorStore(persist_dir=temp_chroma_dir)

    await store.add_documents(
        documents=["康美药业因财务造假被证监会立案调查"],
        metadatas=[{"wind_code": "600518.SH"}],
        ids=["test_001"],
    )

    results = await store.search("财务造假", top_k=3)
    assert len(results) > 0, "查询不应返回空"
    assert results[0]["id"] == "test_001"
    assert results[0]["metadata"]["wind_code"] == "600518.SH"
    assert 0.0 <= results[0]["score"] <= 1.0


@pytest.mark.asyncio
@patch(
    "app.infrastructure.vector.chroma.vector_store._get_embedding_model",
    return_value=type("FakeModel", (), {"encode": staticmethod(fake_encode)})(),
)
async def test_search_empty_collection_returns_empty(mock_model, temp_chroma_dir):
    """未导入数据的集合 → 返回 []。"""
    store = ChromaVectorStore(persist_dir=temp_chroma_dir)
    results = await store.search("任意查询", top_k=5)
    assert results == []
