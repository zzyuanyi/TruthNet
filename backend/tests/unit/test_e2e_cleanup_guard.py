"""E2E 清理守卫测试（v3.5）— 三个失败路径必须抛异常（脚本退出码非零）.

覆盖（v3.5 验收要求）：
- 清理错库：SELECT DATABASE() 与 MYSQL_TEST_DATABASE 不一致 → 拒绝清理抛 RuntimeError；
- session 不存在：清理前断言 session 存在失败 → 抛 RuntimeError；
- 清理异常：底层 engine 连接/执行失败 → 异常向上抛（调用方 cleanup_ok=False）。
均为 mysql 模式（conftest 守卫自动切测试库）。
"""

import importlib.util
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts" / "e2e_ws_three_turn.py"


def _load_e2e():
    spec = importlib.util.spec_from_file_location("e2e_ws_three_turn_tested", _SCRIPTS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e2e():
    return _load_e2e()


def _mysql() -> bool:
    from app.core.config import settings

    return settings.SQL_BACKEND == "mysql"


class _FakeConn:
    """返回固定库名的假连接（构造'清理错库'场景，不依赖真库）。"""

    def __init__(self, db_name: str) -> None:
        self._db = db_name

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, *a, **kw):
        return self

    def scalar(self):
        return self._db


class _FakeEngine:
    def __init__(self, db_name: str) -> None:
        self._db = db_name

    def connect(self):
        return _FakeConn(self._db)


def test_cleanup_wrong_database_rejected(e2e, monkeypatch):
    """清理错库：SELECT DATABASE()（演示库名）与 MYSQL_TEST_DATABASE 不符 → 拒绝。

    不依赖真库：注入返回演示库名的 fake engine，校验逻辑应抛 RuntimeError。
    """
    monkeypatch.setattr(e2e, "_cleanup_engine", lambda: _FakeEngine("truthnet"))
    with pytest.raises(RuntimeError, match="清理目标库不符"):
        e2e._cleanup_session("whatever_session")


@pytest.mark.skipif(not _mysql(), reason="需 mysql 模式真库")
def test_cleanup_missing_session_rejected(e2e):
    """session 不存在：清理前断言失败 → 抛异常（退出码非零）。"""
    with pytest.raises(RuntimeError, match="不存在"):
        e2e._cleanup_session("no_such_session_e2e_guard")


@pytest.mark.skipif(not _mysql(), reason="需 mysql 模式真库")
def test_cleanup_exception_propagates(e2e, monkeypatch):
    """清理异常：底层 engine 连接失败 → 异常向上抛（cleanup_ok=False）。"""

    def _bad_engine():
        from sqlalchemy import create_engine
        from sqlalchemy.engine import URL

        url = URL.create(
            "mysql+pymysql",
            username="no_such_user",
            password="no_such_pwd",
            host="127.0.0.1",
            port=3306,
            database="no_such_db",
            query={"charset": "utf8mb4"},
        )
        return create_engine(url, echo=False)

    monkeypatch.setattr(e2e, "_cleanup_engine", _bad_engine)
    with pytest.raises(Exception):
        e2e._cleanup_session("whatever_session")
