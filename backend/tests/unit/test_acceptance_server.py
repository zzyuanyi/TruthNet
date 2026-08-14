"""acceptance_server 启动器契约测试 — 2026-08-14 验收事故回归。

锁定三个契约：
  1. .env 解析：演示/测试两组凭据正确解析（引号、行内注释）；
  2. 顺序契约：apply_test_env_overrides 必须在导入/实例化 Settings
     之前调用——注入后新 Settings 实例的 MYSQL_DATABASE 必须是测试库
     （2026-08-14 事故根因：先导入 settings 再注入环境变量）；
  3. 守卫纯函数：SELECT DATABASE() 与目标库不一致必须拒绝。
"""

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "acceptance_server.py"


@pytest.fixture(scope="module")
def acceptance_server():
    spec = importlib.util.spec_from_file_location(
        "acceptance_server_under_test", _SCRIPT
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_env(path: Path, lines: list[str]) -> Path:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_load_env_credentials_parses_demo_and_test(acceptance_server, tmp_path):
    env = _write_env(
        tmp_path / ".env",
        [
            "MYSQL_USER=truthnet",
            'MYSQL_PASSWORD="demo-pass"',
            "MYSQL_DATABASE=truthnet",
            "MYSQL_TEST_USER=truthnet_test",
            "MYSQL_TEST_PASSWORD='test-pass'",
            "MYSQL_TEST_DATABASE=truthnet_test  # 测试库（行内注释）",
        ],
    )
    creds = acceptance_server.load_env_credentials(env)
    assert creds["demo"] == {
        "user": "truthnet",
        "password": "demo-pass",
        "database": "truthnet",
    }
    assert creds["test"] == {
        "user": "truthnet_test",
        "password": "test-pass",
        "database": "truthnet_test",
    }


def test_apply_missing_test_env_raises(acceptance_server, tmp_path):
    env = _write_env(
        tmp_path / ".env", ["MYSQL_USER=truthnet", "MYSQL_DATABASE=truthnet"]
    )
    with pytest.raises(RuntimeError, match="MYSQL_TEST_"):
        acceptance_server.apply_test_env_overrides(env)


def test_apply_overrides_before_settings_instance_picks_test_db(
    acceptance_server, tmp_path, monkeypatch
):
    """顺序契约回归：注入先于 Settings 实例化 → 测试库身份。"""
    env = _write_env(
        tmp_path / ".env",
        [
            "MYSQL_USER=truthnet",
            "MYSQL_PASSWORD=demo-pass",
            "MYSQL_DATABASE=truthnet",
            "MYSQL_TEST_USER=truthnet_test",
            "MYSQL_TEST_PASSWORD=test-pass",
            "MYSQL_TEST_DATABASE=truthnet_test",
        ],
    )
    saved = {
        k: monkeypatch.delenv(k, raising=False)
        for k in ("MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE")
    }
    try:
        overrides = acceptance_server.apply_test_env_overrides(env)
        assert overrides["database"] == "truthnet_test"

        from app.core.config import Settings

        fresh = Settings()
        assert fresh.MYSQL_DATABASE == "truthnet_test"
        assert fresh.MYSQL_USER == "truthnet_test"
        assert fresh.MYSQL_DATABASE == fresh.MYSQL_TEST_DATABASE
    finally:
        for key, value in saved.items():
            if value is not None:
                monkeypatch.setenv(key, value)


def test_verify_selected_database_ok_case_insensitive(acceptance_server):
    acceptance_server.verify_selected_database("TruthNet_Test", "truthnet_test")


def test_verify_selected_database_mismatch_raises(acceptance_server):
    with pytest.raises(AssertionError, match="启动守卫失败"):
        acceptance_server.verify_selected_database("truthnet", "truthnet_test")
