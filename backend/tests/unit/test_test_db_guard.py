"""测试库隔离守卫纯函数单测（v3.1 + v3.4）.

覆盖 conftest 守卫规则：
- 三件套显式配置（含非空密码）、拒绝演示库/系统库、安全命名；
- v3.4：大小写不敏感（lower_case_table_names=1）、测试用户名不得等于
  演示用户名、空密码拒绝；
- 越权检查分支（fake connector 覆盖）：成功连接=越权拒绝、
  1044=符合预期放行、其他错误=无法证明隔离拒绝。
真实权限验证属 external 集成（不在单测内连接真实 MySQL）。
"""

import pytest

from tests.conftest import _check_test_account_isolation, _validate_test_db_config

DEMO_DB = "truthnet"
TEST_USER = "truthnet_test"
TEST_PASSWORD = "secret123"


@pytest.mark.parametrize(
    "test_db, test_user, test_pwd, expect_substr",
    [
        ("", TEST_USER, TEST_PASSWORD, "必须显式配置"),
        (TEST_USER, "", TEST_PASSWORD, "必须显式配置"),
        (TEST_USER, TEST_USER, "", "必须显式配置"),  # 空密码拒绝（v3.4）
    ],
)
def test_missing_config_rejected(test_db, test_user, test_pwd, expect_substr):
    err = _validate_test_db_config(
        DEMO_DB, test_db, test_user, test_pwd, mysql_user="truthnet"
    )
    assert err is not None
    assert expect_substr in err


def test_same_as_demo_db_rejected():
    err = _validate_test_db_config(
        DEMO_DB, DEMO_DB, TEST_USER, TEST_PASSWORD, mysql_user="truthnet"
    )
    assert err is not None
    assert "与演示库" in err


def test_case_insensitive_demo_db_rejected():
    """v3.4：MySQL lower_case_table_names=1 下 TRUTHNET 即 truthnet。"""
    err = _validate_test_db_config(
        DEMO_DB, "TRUTHNET", TEST_USER, TEST_PASSWORD, mysql_user="truthnet"
    )
    assert err is not None
    assert "与演示库" in err


def test_case_insensitive_forbidden_names_rejected():
    err = _validate_test_db_config(
        DEMO_DB, "MYSQL", TEST_USER, TEST_PASSWORD, mysql_user="truthnet"
    )
    assert err is not None
    assert "拒绝名单" in err


def test_same_user_as_demo_rejected():
    """v3.4：测试用户名不得等于演示用户名。"""
    err = _validate_test_db_config(
        DEMO_DB, "truthnet_test", "truthnet", TEST_PASSWORD, mysql_user="truthnet"
    )
    assert err is not None
    assert "与演示用户名相同" in err


@pytest.mark.parametrize(
    "forbidden",
    ["truthnet", "mysql", "information_schema", "performance_schema", "sys"],
)
def test_system_db_names_rejected(forbidden):
    # 演示库用独立名字，避免与拒绝名单成员先命中"与演示库相同"检查
    err = _validate_test_db_config(
        "demo_db", forbidden, TEST_USER, TEST_PASSWORD, mysql_user="truthnet"
    )
    assert err is not None
    assert "拒绝名单" in err


@pytest.mark.parametrize(
    "unsafe",
    [
        "truthnet_test; DROP TABLE x",  # 注入
        "truthnet test",  # 空格
        "truthnet'test",  # 引号
        "truthnet-test",  # 破折号
        "truthnet.test",  # 点号
    ],
)
def test_unsafe_naming_rejected(unsafe):
    err = _validate_test_db_config(
        DEMO_DB, unsafe, TEST_USER, TEST_PASSWORD, mysql_user="truthnet"
    )
    assert err is not None
    assert "不安全字符" in err


@pytest.mark.parametrize("safe", ["truthnet_test", "test_db_2026", "TruthNet_Test1"])
def test_valid_test_db_accepted(safe):
    assert (
        _validate_test_db_config(
            DEMO_DB, safe, TEST_USER, TEST_PASSWORD, mysql_user="truthnet"
        )
        is None
    )


# ── 越权检查分支（fake connector，不连真实 MySQL）──────────


class _FakeConn:
    def __init__(self, exc: Exception | None = None) -> None:
        self._exc = exc

    def close(self) -> None:
        pass


class _FakePymysql:
    def __init__(self, outcome) -> None:
        self._outcome = outcome  # ("ok",) | ("error", errno, msg) | ("raise", exc)

    def connect(self, **kwargs):
        kind = self._outcome[0]
        if kind == "ok":
            return _FakeConn()
        if kind == "error":
            raise self._outcome[1]
        raise self._outcome[1]


def _fake_check(outcome, monkeypatch):
    import pymysql as real_pymysql

    fake = _FakePymysql(outcome)
    monkeypatch.setattr(real_pymysql, "connect", fake.connect)
    return _check_test_account_isolation(
        host="127.0.0.1",
        port=3306,
        test_user="truthnet_test",
        test_password="x",
        demo_db="truthnet",
    )


def test_isolation_ok_when_connect_succeeds(monkeypatch):
    """成功连接演示库 = 越权，拒绝。"""

    err = _fake_check(("ok",), monkeypatch)
    assert err is not None
    assert "越权" in err


def test_isolation_ok_when_1044_denied(monkeypatch):
    """1044 权限拒绝 = 符合预期，放行。"""
    import pymysql.err

    err = _fake_check(
        ("error", pymysql.err.OperationalError(1044, "denied")), monkeypatch
    )
    assert err is None


def test_isolation_rejected_on_unknown_db(monkeypatch):
    """未知数据库（1049）无法证明隔离，拒绝。"""
    import pymysql.err

    err = _fake_check(
        ("error", pymysql.err.OperationalError(1049, "unknown db")), monkeypatch
    )
    assert err is not None
    assert "无法证明" in err


def test_isolation_rejected_on_network_error(monkeypatch):
    """网络/认证类错误无法证明隔离，拒绝。"""
    err = _fake_check(("raise", ConnectionError("timeout")), monkeypatch)
    assert err is not None
    assert "无法证明" in err
