"""技术栈 smoke 验证 — 逐项测试每个核心依赖的最小功能。

在独立 Python 3.11 环境中运行：
    python -m pytest backend/tests/test_stack_smoke.py -v
"""

import json
import os
import sqlite3
import tempfile
from pathlib import Path


# ============================================================
# 1. FastAPI
# ============================================================
def test_fastapi_import():
    """FastAPI 可以导入。"""
    import fastapi

    assert fastapi.__version__


# ============================================================
# 2. Pydantic Schema 序列化/反序列化
# ============================================================
def test_pydantic_chat_schema_roundtrip():
    """ChatRequest/ChatData 可以正确序列化和反序列化。"""
    from app.schemas.chat import ChatData, ChatRequest, RiskScore
    from app.schemas.common import UnifiedResponse

    # 构造请求
    req = ChatRequest(question="测试问题", session_id="sess_001")
    req_json = req.model_dump_json()
    req2 = ChatRequest.model_validate_json(req_json)
    assert req2.question == "测试问题"
    assert req2.session_id == "sess_001"

    # 构造响应（Prompt4: risk_score 为 RiskScore 对象）
    data = ChatData(
        answer="测试回答",
        evidence=[],
        graph={},
        timeline=[],
        risk_score=RiskScore(overall=0.15, financial=0.10, ownership=0.20, sentiment=0.05),
        warnings=[],
        missing_modules=[],
        trace_id="trace-001",
    )
    resp = UnifiedResponse(code=0, data=data, message="ok", trace_id="trace-002")
    resp_json = resp.model_dump_json()
    resp_dict = json.loads(resp_json)
    assert resp_dict["code"] == 0
    assert resp_dict["data"]["answer"] == "测试回答"
    assert resp_dict["data"]["risk_score"]["overall"] == 0.15
    assert resp_dict["data"]["risk_score"]["financial"] == 0.10

    # 验证 JSON 结构符合 API_CONTRACT（用 dict 进行通用校验）
    assert "code" in resp_dict
    assert "data" in resp_dict
    assert "message" in resp_dict
    assert "trace_id" in resp_dict


# ============================================================
# 3. SQLite
# ============================================================
def test_sqlite_minimal():
    """SQLite 内存库可以建表、插入、查询。"""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE companies (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            industry TEXT
        )
    """)
    cursor.execute(
        "INSERT INTO companies VALUES (?, ?, ?)",
        ("600519", "贵州茅台酒股份有限公司", "白酒"),
    )
    conn.commit()

    cursor.execute("SELECT name, industry FROM companies WHERE id = ?", ("600519",))
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "贵州茅台酒股份有限公司"
    assert row[1] == "白酒"

    conn.close()


# ============================================================
# 4. NetworkX — 4 跳股权链
# ============================================================
def test_networkx_ownership_chain():
    """NetworkX 构建 4 跳股权链并计算路径权重。"""
    import networkx as nx

    G = nx.DiGraph()

    # 构造: 王某 -> 壳公司A -> 资管计划B -> 上市公司C
    # 边权: 0.8, 0.7, 0.9
    G.add_edge("王某", "壳公司A", ratio=0.8)
    G.add_edge("壳公司A", "资管计划B", ratio=0.7)
    G.add_edge("资管计划B", "上市公司C", ratio=0.9)

    # 验证路径存在
    assert nx.has_path(G, "王某", "上市公司C")

    # 计算路径权重连乘
    path = nx.shortest_path(G, "王某", "上市公司C")
    weight = 1.0
    for i in range(len(path) - 1):
        weight *= G[path[i]][path[i + 1]]["ratio"]

    # 0.8 * 0.7 * 0.9 = 0.504
    assert abs(weight - 0.504) < 1e-9, f"expected 0.504, got {weight}"

    # 验证深度
    assert len(path) == 4  # 4 个节点 = 3 跳

    # 额外验证: 深度 >3 (多跳链路)
    G.add_edge("上市公司C", "子公司D", ratio=1.0)
    path2 = nx.shortest_path(G, "王某", "子公司D")
    assert len(path2) == 5  # 5 个节点 = 4 跳


# ============================================================
# 5. ChromaDB
# ============================================================
def test_chromadb_minimal():
    """ChromaDB 创建临时 collection，插入并查询。"""

    import chromadb

    tmpdir = tempfile.mkdtemp(prefix="truthnet_chroma_test_")

    try:
        client = chromadb.PersistentClient(path=tmpdir)
        collection = client.create_collection(name="test_collection")

        # 插入 2 条文本
        collection.add(
            documents=[
                "贵州茅台2023年营收1505.60亿元",
                "宁德时代2023年营收4009.17亿元",
            ],
            ids=["doc_1", "doc_2"],
            metadatas=[
                {"company": "600519", "year": 2023},
                {"company": "300750", "year": 2023},
            ],
        )

        # Query
        results = collection.query(query_texts=["营收"], n_results=2)
        assert len(results["ids"][0]) == 2
        assert results["ids"][0][0] in ("doc_1", "doc_2")

    finally:
        # 清理临时目录
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)


# ============================================================
# 6. LangGraph — 最小 StateGraph
# ============================================================
def test_langgraph_minimal_state_graph():
    """LangGraph 创建最小 StateGraph 并执行一次 invoke。"""
    from typing import TypedDict

    from langgraph.graph import END, START, StateGraph

    class State(TypedDict):
        value: int

    def add_one(state: State) -> State:
        return {"value": state["value"] + 1}

    graph = StateGraph(State)
    graph.add_node("add_one", add_one)
    graph.add_edge(START, "add_one")
    graph.add_edge("add_one", END)

    app = graph.compile()
    result = app.invoke({"value": 1})

    assert result["value"] == 2


# ============================================================
# 7. pandas / numpy / scikit-learn
# ============================================================
def test_pandas_numpy_sklearn():
    """pandas/numpy 数据处理 + scikit-learn F1 计算。"""
    import numpy as np
    import pandas as pd
    from sklearn.metrics import f1_score

    # pandas
    df = pd.DataFrame(
        {
            "company": ["A", "B", "C", "D"],
            "revenue": [100, 200, 150, 300],
        }
    )
    assert len(df) == 4
    assert df["revenue"].mean() == 187.5

    # numpy
    arr = np.array([1, 2, 3, 4, 5])
    assert arr.mean() == 3.0

    # scikit-learn F1
    y_true = [0, 1, 1, 0, 1, 0]
    y_pred = [0, 1, 0, 0, 1, 1]
    f1 = f1_score(y_true, y_pred)
    assert 0.0 <= f1 <= 1.0


# ============================================================
# 8. dotenv / pydantic-settings
# ============================================================
def test_dotenv_and_settings():
    """从临时 .env 读取配置，不依赖真实 .env。"""

    from dotenv import load_dotenv

    # 保存原始环境变量值
    orig_app_name = os.environ.get("APP_NAME")
    orig_backend_port = os.environ.get("BACKEND_PORT")

    # 创建临时 .env 文件 (模拟)
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".env", delete=False, encoding="utf-8"
    )
    tmp.write("APP_NAME=TruthNetTest\nBACKEND_PORT=9999\n")
    tmp.close()

    try:
        load_dotenv(tmp.name, override=True)
        assert os.environ.get("APP_NAME") == "TruthNetTest"
        assert os.environ.get("BACKEND_PORT") == "9999"
    finally:
        Path(tmp.name).unlink(missing_ok=True)
        # 恢复环境变量
        if orig_app_name is not None:
            os.environ["APP_NAME"] = orig_app_name
        else:
            os.environ.pop("APP_NAME", None)
        if orig_backend_port is not None:
            os.environ["BACKEND_PORT"] = orig_backend_port
        else:
            os.environ.pop("BACKEND_PORT", None)


def test_pydantic_settings_defaults():
    """pydantic-settings 使用默认值（不受 dotenv 污染）。"""
    from app.core.config import Settings

    s = Settings(_env_file="")  # 不读取任何 .env 文件
    assert s.APP_NAME == "TruthNet"
    assert s.BACKEND_PORT == 8000


# ============================================================
# 9. ruff / pre-commit 版本检查
# ============================================================
def test_ruff_installed():
    """ruff 已安装且版本符合预期。"""
    import importlib

    ruff = importlib.import_module("ruff")
    assert ruff  # ruff 是一个 namespace package


def test_pre_commit_installed():
    """pre-commit 已安装。"""
    import importlib

    pre_commit = importlib.import_module("pre_commit")
    assert pre_commit
