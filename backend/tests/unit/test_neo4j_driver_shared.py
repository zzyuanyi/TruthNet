"""Neo4j 共享 driver 生命周期测试 — 连接泄漏收口.

覆盖：
  - 并发实例化只创建一次 driver（锁 + 双重检查）；
  - close_shared_driver 幂等：关闭后清空引用，再次实例化重建；
  - lifespan 退出时调用 close_shared_driver（不再依赖析构关闭）。
"""

from concurrent.futures import ThreadPoolExecutor
import threading

import neo4j
import pytest
from fastapi.testclient import TestClient

from app.infrastructure.graph.neo4j.equity_graph import Neo4jEquityGraph

_real_driver_cls = neo4j.GraphDatabase.driver


@pytest.fixture(autouse=True)
def _reset():
    """每个测试前后显式关闭共享 driver（不直接置 None——丢弃连接不 close
    会依赖析构触发 warning；close 本身幂等且清空 _shared_driver）。"""
    Neo4jEquityGraph.close_shared_driver()
    yield
    Neo4jEquityGraph.close_shared_driver()


def test_concurrent_init_creates_driver_once(monkeypatch):
    """并发初始化：Barrier 同步冷启动窗口，锁 + 双重检查保证 driver 只创建一次。"""
    counts = {"n": 0}
    barrier = threading.Barrier(16)

    def _counting_driver(*args, **kwargs):
        counts["n"] += 1
        return _real_driver_cls(*args, **kwargs)

    monkeypatch.setattr(neo4j.GraphDatabase, "driver", _counting_driver)

    def _new(_):
        barrier.wait()  # 16 线程同时进入 __init__（稳定覆盖冷启动竞态窗口）
        return Neo4jEquityGraph()

    with ThreadPoolExecutor(max_workers=16) as pool:
        graphs = list(pool.map(_new, range(16)))

    assert counts["n"] == 1, f"并发初始化应只创建一次 driver，实际 {counts['n']} 次"
    drivers = {id(g._driver) for g in graphs}
    assert len(drivers) == 1, "所有实例应共享同一 driver"


def test_close_shared_driver_idempotent_rebuild(monkeypatch):
    """close 后清空引用；再次实例化重建 driver（幂等安全）。"""
    counts = {"n": 0}

    def _counting_driver(*args, **kwargs):
        counts["n"] += 1
        return _real_driver_cls(*args, **kwargs)

    monkeypatch.setattr(neo4j.GraphDatabase, "driver", _counting_driver)

    g1 = Neo4jEquityGraph()
    assert counts["n"] == 1
    d1 = g1._driver

    Neo4jEquityGraph.close_shared_driver()
    Neo4jEquityGraph.close_shared_driver()  # 幂等：二次关闭不报错

    g2 = Neo4jEquityGraph()
    assert counts["n"] == 2, "关闭后应可重建"
    assert g2._driver is not d1


def test_lifespan_exit_closes_shared_driver(monkeypatch):
    """lifespan finally 调用 close_shared_driver（不再依赖析构）。"""
    calls = {"n": 0}
    orig_close = Neo4jEquityGraph.close_shared_driver.__func__

    def _counting_close(*_args):
        calls["n"] += 1
        return orig_close(Neo4jEquityGraph)

    monkeypatch.setattr(
        Neo4jEquityGraph, "close_shared_driver", classmethod(_counting_close)
    )

    # 先实例化，确保进程内有共享 driver 需要关闭
    g = Neo4jEquityGraph()
    assert g._driver is not None or Neo4jEquityGraph._shared_driver is not None

    with TestClient(import_module_app()) as client:
        assert client.get("/api/v1/healthz").status_code == 200

    assert calls["n"] == 1, f"lifespan 退出应恰好调用一次 close，实际 {calls['n']}"
    assert Neo4jEquityGraph._shared_driver is None, "close 后共享引用应清空"


def import_module_app():
    from app.main import app

    return app
