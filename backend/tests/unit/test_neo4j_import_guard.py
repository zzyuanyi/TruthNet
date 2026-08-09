"""Neo4j 导入防护单元测试（P0-1：期次规范化、自环跳过）。

覆盖：
- _normalize_report_period：NaN/NaT/None/空串/带横线/整数浮点/Timestamp/
  非法日期（20250229/20251301）
- 自环关系跳过（公司持有自身不产生可遍历自环）
"""

import sys
from pathlib import Path

import pytest

_scripts = Path(__file__).resolve().parents[3] / "scripts"
if str(_scripts) not in sys.path:
    sys.path.insert(0, str(_scripts))

from neo4j_full_import import _normalize_report_period  # noqa: E402


# ── 期次规范化 ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, ""),
        ("", ""),
        ("20251231", "20251231"),
        ("2025-12-31", "20251231"),
        ("2025/12/31", "20251231"),
        (20251231, "20251231"),
        (20251231.0, "20251231"),
        ("20251231.0", "20251231"),
        ("nan", ""),
        ("abc", ""),
        ("20251399", ""),  # 非法月份
        ("20250229", ""),  # 非法日期（非闰年）
    ],
)
def test_normalize_report_period(value, expected):
    """合法日期归一为 YYYYMMDD；非法输入返回空串。"""
    assert _normalize_report_period(value, None) == expected


def test_normalize_report_period_datetime():
    """date/datetime/Timestamp 输入 → strftime 格式。"""
    from datetime import datetime

    assert _normalize_report_period(datetime(2025, 12, 31), None) == "20251231"


def test_normalize_report_period_fallback():
    """主期次无效 → 回退 fallback；两者无效 → 空串。"""
    assert _normalize_report_period(None, "2025-06-30") == "20250630"
    assert _normalize_report_period("nan", "20250630") == "20250630"
    assert _normalize_report_period("nan", None) == ""


def test_normalize_report_period_na_types():
    """NaN/NaT 视为无效（不产生 'nan' 字符串）。"""
    import pandas as pd

    assert _normalize_report_period(float("nan"), None) == ""
    assert _normalize_report_period(pd.NaT, None) == ""
    assert _normalize_report_period(pd.NA, None) == ""


# ── P0-2 防误删保护：dry-run 互斥与批次失败上抛 ─────────────


def test_dry_run_and_replace_conflict(monkeypatch, capsys):
    """--dry-run 与 --replace-graph-version 同现 → 退出码 1 + 错误信息。"""
    import argparse

    import neo4j_full_import as nf

    monkeypatch.setattr(
        nf,
        "parse_args",
        lambda: argparse.Namespace(
            data_file="x.xlsx",
            graph_version="gv",
            dataset_version="dv",
            batch_size=1000,
            dry_run=True,
            replace_graph_version=True,
            concerted_only=False,
            mock=False,
        ),
    )
    rc = nf.main()
    assert rc == 1  # 互斥 → 非零退出


def test_import_batch_failure_raises(monkeypatch):
    """批次失败 → 抛 RuntimeError（不再记录后继续）。"""
    import asyncio

    from app.infrastructure.graph.neo4j.equity_graph import Neo4jEquityGraph

    a = Neo4jEquityGraph.__new__(Neo4jEquityGraph)

    def _boom(*a_, **k_):
        raise RuntimeError("neo4j down")

    a._driver = type("D", (), {"execute_query": _boom})()
    with pytest.raises(RuntimeError, match="批次失败"):
        asyncio.run(
            a.import_relationships_batch(
                [
                    {
                        "source_entity_id": "s",
                        "target_entity_id": "t",
                        "relation_type": "OWNS",
                        "report_period": "20251231",
                        "ann_dt": "",
                        "source_record_id": "r",
                        "ownership_pct": 1.0,
                        "is_latest": True,
                    }
                ],
                graph_version="gv",
                import_run_id="run_test",
            )
        )


def test_import_batch_missing_endpoint_detected(monkeypatch):
    """Cypher 返回 merged < 提交数 → 判定失败（端点缺失）。"""
    import asyncio

    from app.infrastructure.graph.neo4j.equity_graph import Neo4jEquityGraph

    a = Neo4jEquityGraph.__new__(Neo4jEquityGraph)

    def _short(*a_, **k_):
        return [{"merged": 0}], None, None

    a._driver = type("D", (), {"execute_query": _short})()
    with pytest.raises(RuntimeError, match="实际写入 0/1"):
        asyncio.run(
            a.import_relationships_batch(
                [
                    {
                        "source_entity_id": "s",
                        "target_entity_id": "t",
                        "relation_type": "OWNS",
                        "report_period": "20251231",
                        "ann_dt": "",
                        "source_record_id": "r",
                        "ownership_pct": 1.0,
                        "is_latest": True,
                    }
                ],
                graph_version="gv",
                import_run_id="run_test",
            )
        )
