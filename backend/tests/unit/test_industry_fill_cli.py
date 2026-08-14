"""CLI 契约与凭据注入单元测试（档案 v1.1 §4/P1-3）。

不执行 main() 主流程；只验证参数契约与注入函数。
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "industry_fill.py"


def _load_cli():
    spec = importlib.util.spec_from_file_location("industry_fill_cli", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture(scope="module")
def cli_mod():
    return _load_cli()


class TestArgParserContract:
    def test_limit_default_none_no_implicit_50(self, cli_mod):
        ap = cli_mod.build_arg_parser()
        args = ap.parse_args(["--database", "truthnet_test"])
        assert args.limit is None
        assert args.offset == 0

    def test_limit_and_offset(self, cli_mod):
        ap = cli_mod.build_arg_parser()
        args = ap.parse_args(
            ["--database", "truthnet_test", "--limit", "50", "--offset", "10"]
        )
        assert args.limit == 50
        assert args.offset == 10

    def test_apply_and_dry_run_mutually_exclusive(self, cli_mod):
        ap = cli_mod.build_arg_parser()
        args = ap.parse_args(["--database", "truthnet_test", "--apply", "--dry-run"])
        with pytest.raises(SystemExit):
            cli_mod._validate_args(args)

    def test_replace_requires_apply(self, cli_mod):
        ap = cli_mod.build_arg_parser()
        args = ap.parse_args(["--database", "truthnet_test", "--replace"])
        with pytest.raises(SystemExit):
            cli_mod._validate_args(args)

    def test_apply_with_skip_benchmark_rebuild_rejected(self, cli_mod):
        """审查整改 P2：--apply 与 --skip-benchmark-rebuild 必须互斥。"""
        ap = cli_mod.build_arg_parser()
        args = ap.parse_args(
            ["--database", "truthnet_test", "--apply", "--skip-benchmark-rebuild"]
        )
        with pytest.raises(SystemExit):
            cli_mod._validate_args(args)

    def test_provider_only_akshare(self, cli_mod):
        ap = cli_mod.build_arg_parser()
        with pytest.raises(SystemExit):
            ap.parse_args(["--database", "truthnet_test", "--provider", "unknown"])


class TestResolveDatabaseEnv:
    def test_test_triple_injected(self, monkeypatch, tmp_path):
        from backend.app.application.services.industry_fill.guards import (
            resolve_database_env,
        )

        env = tmp_path / ".env"
        env.write_text(
            "MYSQL_DATABASE=truthnet\n"
            "MYSQL_USER=demo_u\n"
            "MYSQL_PASSWORD=demo_p\n"
            "MYSQL_TEST_DATABASE=truthnet_test\n"
            "MYSQL_TEST_USER=test_u\n"
            "MYSQL_TEST_PASSWORD=test_p\n",
            encoding="utf-8",
        )
        monkeypatch.delenv("MYSQL_DATABASE", raising=False)
        user, password, database = resolve_database_env("truthnet_test", env)
        assert (user, password, database) == ("test_u", "test_p", "truthnet_test")
        assert os.environ["MYSQL_DATABASE"] == "truthnet_test"
        assert os.environ["MYSQL_USER"] == "test_u"
        assert os.environ["MYSQL_PASSWORD"] == "test_p"

    def test_unknown_database_fail_closed(self, monkeypatch, tmp_path):
        from backend.app.application.services.industry_fill.guards import (
            resolve_database_env,
        )

        env = tmp_path / ".env"
        env.write_text(
            "MYSQL_DATABASE=truthnet\n"
            "MYSQL_USER=demo_u\n"
            "MYSQL_PASSWORD=demo_p\n"
            "MYSQL_TEST_DATABASE=truthnet_test\n"
            "MYSQL_TEST_USER=test_u\n"
            "MYSQL_TEST_PASSWORD=test_p\n",
            encoding="utf-8",
        )
        monkeypatch.delenv("MYSQL_DATABASE", raising=False)
        with pytest.raises(RuntimeError, match="不在 .env 允许清单"):
            resolve_database_env("evil_db", env)

    def test_verify_selected_database(self):
        from backend.app.application.services.industry_fill.guards import (
            masked_profile,
            verify_selected_database,
        )

        verify_selected_database("truthnet_test", "truthnet_test")
        with pytest.raises(AssertionError, match="数据库守卫失败"):
            verify_selected_database("truthnet", "truthnet_test")
        assert "secret" not in masked_profile(
            "user", "127.0.0.1", 3306, "truthnet_test"
        )
