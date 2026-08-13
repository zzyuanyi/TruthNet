"""Session cleanup safety and dry-run query regression tests."""

from argparse import Namespace
from pathlib import Path


def _load_script():
    import importlib.util

    path = Path(__file__).resolve().parents[3] / "scripts" / "cleanup_sessions.py"
    spec = importlib.util.spec_from_file_location("cleanup_sessions_tested", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_orphan_confirm_does_not_require_session_keep_list():
    module = _load_script()
    assert (
        module._confirm_requires_keep(Namespace(confirm=True, orphans=True, keep=[]))
        is False
    )
    assert (
        module._confirm_requires_keep(Namespace(confirm=True, orphans=False, keep=[]))
        is True
    )


def test_orphan_preflight_counts_only_valid_claim_references():
    module = _load_script()

    class Result:
        def __init__(self, value):
            self.value = value

        def scalars(self):
            return self

        def all(self):
            return []

        def scalar(self):
            return self.value

    class Connection:
        def __init__(self):
            self.sql: list[str] = []

        def execute(self, statement, *_args, **_kwargs):
            sql = str(statement)
            self.sql.append(sql)
            if "SELECT c.claim_id" in sql:
                return Result(0)
            return Result(0)

    connection = Connection()
    assert module._cleanup_orphans(connection, execute=False) == (0, 0, 0)
    evidence_sql = connection.sql[-1]
    assert "JOIN claims c" in evidence_sql
    assert "JOIN conversation_turns valid_t" in evidence_sql
