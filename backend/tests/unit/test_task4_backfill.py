"""task4_name_backfill.py 回填脚本单元测试（Phase C 修正版）.

覆盖（验收 14.6）:
- 规范化：wind_code 大小写/后缀、comp_type_code 安全转换、非法值；
- 冲突仲裁：来源优先级 + 最新报告期 + 多数/平票；
- 全文件扫描（多个 CSV，不止第一个）；
- 类型规划（NULL/非法才更新）；
- 名称规划（缺失定义、来源优先级、低置信度跳过）；
- 幂等（第二次更新为 0）。
"""

import csv
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import task4_name_backfill as t4  # noqa: E402


# ── 规范化 ─────────────────────────────────────────────────


def test_normalize_wind_code():
    assert t4.normalize_wind_code("600519.SH") == "600519.SH"
    assert t4.normalize_wind_code(" 600519.sh ") == "600519.SH"
    assert t4.normalize_wind_code("000858.sz") == "000858.SZ"
    assert t4.normalize_wind_code("430047.bj") == "430047.BJ"
    assert t4.normalize_wind_code("12345") is None  # 非法长度
    assert t4.normalize_wind_code("ABCDEF.SH") is None  # 非数字
    assert t4.normalize_wind_code("600519.XX") is None  # 非法后缀
    assert t4.normalize_wind_code(None) is None
    assert t4.normalize_wind_code("") is None


def test_normalize_comp_type():
    assert t4.normalize_comp_type(1) == 1
    assert t4.normalize_comp_type("1") == 1
    assert t4.normalize_comp_type(1.0) == 1
    assert t4.normalize_comp_type("3") == 3
    assert t4.normalize_comp_type(4) == 4
    assert t4.normalize_comp_type(None) is None
    assert t4.normalize_comp_type(0) is None  # 0 非法，不默认 1
    assert t4.normalize_comp_type(7) is None  # 非法
    assert t4.normalize_comp_type("nan") is None
    assert t4.normalize_comp_type("") is None
    assert t4.normalize_comp_type("abc") is None


# ── 冲突仲裁 ───────────────────────────────────────────────


def _row(rank, rp, ct):
    return (rank, rp, ct)


def test_resolve_source_priority_beats_later_source():
    """balance_sheet(rank=0) 全部为 2，cash_flow(rank=2) 全部为 1 → 取 2。"""
    rows = [
        _row(0, "20251231", 2),
        _row(0, "20241231", 2),
        _row(2, "20251231", 1),
        _row(2, "20241231", 1),
    ]
    sel, reason, _d = t4.resolve_comp_type(rows)
    assert sel == 2
    assert "source_priority" in reason


def test_resolve_latest_period_wins():
    """同来源最新报告期 4，旧期 1 → 取 4。"""
    rows = [
        _row(0, "20241231", 1),
        _row(0, "20250630", 1),
        _row(0, "20251231", 4),
    ]
    sel, reason, _d = t4.resolve_comp_type(rows)
    assert sel == 4
    assert "latest_period" in reason


def test_resolve_majority_within_top():
    """顶层组内多数决定。"""
    rows = [
        _row(0, "20251231", 2),
        _row(0, "20251231", 2),
        _row(0, "20251231", 1),
    ]
    sel, _reason, _d = t4.resolve_comp_type(rows)
    assert sel == 2


def test_resolve_tie_is_conflict():
    """平票 → 不写入（conflict_tie）。"""
    rows = [
        _row(0, "20251231", 2),
        _row(0, "20251231", 3),
    ]
    sel, reason, _d = t4.resolve_comp_type(rows)
    assert sel is None
    assert reason == "conflict_tie"


def test_resolve_no_valid_type():
    """全部非法/缺失 → 无法确定。"""
    rows = [_row(0, "20251231", None), _row(0, "20241231", 7)]
    sel, reason, _d = t4.resolve_comp_type(rows)
    assert sel is None
    assert reason == "no_valid_type"


# ── 全文件扫描（不止第一个 CSV）──────────────────────────


def _write_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["wind_code", "comp_type_code", "report_period"]
        )
        writer.writeheader()
        writer.writerows(rows)


def test_scan_raw_comp_types_multiple_files(tmp_path, monkeypatch):
    """扫描全部匹配文件（多个 CSV 合并），不是只读第一个。"""
    raw_dir = tmp_path / "4"
    _write_csv(
        raw_dir / "asharebalancesheet_a.csv",
        [
            {
                "wind_code": "600001.SH",
                "comp_type_code": "1",
                "report_period": "20251231",
            },
            {
                "wind_code": "600001.SH",
                "comp_type_code": "1",
                "report_period": "20250630",
            },
        ],
    )
    _write_csv(
        raw_dir / "ashareincome_b.csv",
        [
            {
                "wind_code": "600001.SH",
                "comp_type_code": "2",
                "report_period": "20251231",
            },
            {
                "wind_code": "600002.SZ",
                "comp_type_code": "3",
                "report_period": "20251231",
            },
        ],
    )
    _write_csv(
        raw_dir / "asharecashflow_c.csv",
        [
            {
                "wind_code": "600002.SZ",
                "comp_type_code": "3",
                "report_period": "20251231",
            },
            {
                "wind_code": "600003.BJ",
                "comp_type_code": "4",
                "report_period": "20251231",
            },
        ],
    )
    monkeypatch.setattr(t4, "RAW_DIR", raw_dir)
    per_code, stats = t4.scan_raw_comp_types()
    assert stats["distinct_wind_code"] == 3
    assert set(per_code) == {"600001.SH", "600002.SZ", "600003.BJ"}
    assert len(stats["files"]) == 3
    # 600001 来自两个来源，候选类型 {1,2}
    assert per_code["600001.SH"]["candidate_types"] == {1, 2}


# ── 类型/名称规划（mock DB）────────────────────────────────


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, *a, **k):
        return self

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, rows):
        self._cursor = _FakeCursor(rows)

    def cursor(self):
        return self._cursor


def test_plan_type_updates_only_null_or_invalid():
    """只回填 NULL/非法类型；已有有效类型不覆盖。"""
    conn = _FakeConn(
        [
            ("600001.SH", None),  # NULL → 更新
            ("600002.SZ", 7),  # 非法 → 更新
            ("600003.BJ", 1),  # 有效且匹配 → 不更新
            ("600004.SH", 4),  # 有效且匹配 → 不更新
            ("600005.SZ", 2),  # 有效但与 raw 决议不同 → skip 不覆盖
        ]
    )
    decisions = {
        "600001.SH": {"type": 1, "reason": "x"},
        "600002.SZ": {"type": 2, "reason": "x"},
        "600003.BJ": {"type": 1, "reason": "x"},
        "600004.SH": {"type": 4, "reason": "x"},
        "600005.SZ": {"type": 1, "reason": "x"},
    }
    updates, skips = t4.plan_type_updates(conn, decisions)
    assert {u["wind_code"] for u in updates} == {"600001.SH", "600002.SZ"}
    assert [s["wind_code"] for s in skips] == ["600005.SZ"]


def test_plan_name_updates_missing_only_and_source_priority():
    """只更新缺失名称；已有真实名称不覆盖；来源优先级 companies_history 优先。"""
    conn = _FakeConn(
        [
            ("600001.SH", "600001.SH"),  # 缺失（=代码）
            ("600002.SZ", None),  # 缺失
            ("600003.BJ", "  "),  # 缺失（空白）
            ("600004.SH", "已有真名"),  # 不覆盖
            ("600005.SZ", "600005.SZ"),  # 缺失但无候选 → skip
        ]
    )
    candidates = {
        "600001.SH": {
            "name": "康美",
            "source": "research_reports",
            "confidence": "medium",
        },
        "600002.SZ": {
            "name": "茅台",
            "source": "companies_history",
            "confidence": "high",
        },
        "600003.BJ": {
            "name": "平安",
            "source": "announcements",
            "confidence": "medium",
        },
        "600004.SH": {
            "name": "不应覆盖",
            "source": "announcements",
            "confidence": "medium",
        },
    }
    updates, skipped = t4.plan_name_updates(conn, candidates)
    update_map = {u["wind_code"]: u for u in updates}
    assert set(update_map) == {"600001.SH", "600002.SZ", "600003.BJ"}
    assert update_map["600002.SZ"]["source"] == "companies_history"
    assert [s["wind_code"] for s in skipped] == ["600005.SZ"]


# ── 幂等性（纯逻辑层面）────────────────────────────────────


def test_idempotency_second_run_zero_updates():
    """第一次写入后，DB 已有有效类型/名称 → 第二次规划 0 更新。"""
    # 类型：全部有效且匹配
    conn = _FakeConn(
        [
            ("600001.SH", 1),
            ("600002.SZ", 2),
        ]
    )
    decisions = {
        "600001.SH": {"type": 1, "reason": "x"},
        "600002.SZ": {"type": 2, "reason": "x"},
    }
    updates, _ = t4.plan_type_updates(conn, decisions)
    assert updates == []

    # 名称：全部已有真实名称
    conn2 = _FakeConn([("600001.SH", "康美"), ("600002.SZ", "茅台")])
    upd2, _ = t4.plan_name_updates(
        conn2, {"600001.SH": {"name": "康美", "source": "r", "confidence": "m"}}
    )
    assert upd2 == []
