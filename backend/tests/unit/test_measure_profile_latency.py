"""性能脚本清理回归测试（v3.6）— 统一 initial 基线 + 全维度回查.

覆盖（审查要求）：
- HTTP 阶段新 Evidence 出现在 instrument 基线：统一用 initial_evidence_baseline
  （阶段前一次）清理时，HTTP 阶段新证据必须被识别为"新"并删除——
  instrument 阶段自采基线（旧逻辑）会把它当旧证据漏删；
- 清理前记录目标 claim IDs → 清理后 links/claims/runs/新 Evidence 全 0。
"""

import os

import pytest

from app.core.config import settings

_SCRIPTS = "measure_profile_latency"


@pytest.fixture(scope="module")
def meas():
    import importlib.util
    import sys

    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[3] / "scripts" / "measure_profile_latency.py"
    )
    spec = importlib.util.spec_from_file_location(_SCRIPTS, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_SCRIPTS] = mod
    spec.loader.exec_module(mod)
    return mod


def _mysql() -> bool:
    return settings.SQL_BACKEND == "mysql"


def _conn():
    import pymysql

    return pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_TEST_USER", ""),
        password=os.environ.get("MYSQL_TEST_PASSWORD", ""),
        database=os.environ.get("MYSQL_TEST_DATABASE", "truthnet_test"),
        charset="utf8mb4",
    )


def _insert_provenance(conn, trace: str, eid: str):
    """插入完整 provenance 行（evidence + claim + link + run）。"""
    claim_id = f"claim_regr_{trace}"
    run_id = f"run_regr_{trace}"
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO evidence_refs (evidence_id, source_type, source_record_id, "
            "company_code, field_path, period, value, unit, statement_scope, "
            "source_title, dataset_version, retrieved_at, turn_id, trace_id, "
            "module, source_table) "
            "VALUES (%s,'regression','','600519.SH','x','20260331',NULL,NULL,"
            "'parent_company',NULL,%s,CURRENT_TIMESTAMP,NULL,%s,'test',NULL)",
            (eid, settings.DATASET_VERSION, trace),
        )
        cur.execute(
            "INSERT INTO claims (claim_id, turn_id, text, claim_type, severity, "
            "confidence, rule_id, rule_version, verification_status, generated_at, "
            "trace_id, company_code, module) "
            "VALUES (%s,%s,'x','risk_signal','low',0.5,NULL,'1.0.0','verified',"
            "CURRENT_TIMESTAMP,%s,'600519.SH','test')",
            (claim_id, trace, trace),
        )
        cur.execute(
            "INSERT INTO claim_evidence_links (claim_id, evidence_id, relation_type, "
            "sequence_no, created_at) VALUES (%s,%s,'supports',0,CURRENT_TIMESTAMP)",
            (claim_id, eid),
        )
        cur.execute(
            "INSERT INTO analysis_runs (run_id, trace_id, endpoint, company_codes, "
            "period, statement_scope, status, created_at) "
            "VALUES (%s,%s,'companies/{code}/risk',NULL,NULL,'parent_company',"
            "'completed',CURRENT_TIMESTAMP)",
            (run_id, trace),
        )
    conn.commit()


def _delete_provenance(conn, trace: str, eid: str):
    claim_id = f"claim_regr_{trace}"
    run_id = f"run_regr_{trace}"
    with conn.cursor() as cur:
        cur.execute("DELETE FROM claim_evidence_links WHERE claim_id=%s", (claim_id,))
        cur.execute("DELETE FROM claims WHERE claim_id=%s", (claim_id,))
        cur.execute("DELETE FROM evidence_refs WHERE evidence_id=%s", (eid,))
        cur.execute("DELETE FROM analysis_runs WHERE run_id=%s", (run_id,))
    conn.commit()


@pytest.mark.skipif(not _mysql(), reason="需 mysql 模式真库")
def test_initial_baseline_covers_http_new_evidence(meas):
    """HTTP 阶段新 Evidence 必须被识别为新并删除（统一 initial 基线）。

    旧逻辑（instrument 阶段自采基线）下，HTTP 阶段新证据会进入 instrument
    基线而被当旧证据漏删——回归测试证明 initial 基线（阶段前一次）不含
    HTTP 新证据，清理必须删除它。
    """
    conn = _conn()
    http_trace = "trace_http_regr"
    inst_trace = "trace_inst_regr"
    http_eid = f"ev_regr_http_{http_trace[:8]}"
    inst_eid = f"ev_regr_inst_{inst_trace[:8]}"
    try:
        # 1. initial 基线（所有阶段前一次）
        initial = meas._evidence_baseline()
        # 2. HTTP 阶段产生新证据
        _insert_provenance(conn, http_trace, http_eid)
        assert http_eid not in initial, "HTTP 新证据不应出现在 initial 基线"
        # 3. instrument 阶段（旧逻辑会在此刻自采基线——含 HTTP 新证据）
        _insert_provenance(conn, inst_trace, inst_eid)
        # 4. 统一用 initial 基线清理两阶段
        stats = meas._cleanup_traces({http_trace, inst_trace}, initial)
        assert http_eid in stats["new_evidence_ids"], "HTTP 新证据必须被识别为新"
        assert inst_eid in stats["new_evidence_ids"]
        # 5. 全维度回查零残留
        verify = meas._verify_cleanup(
            {http_trace, inst_trace},
            claim_ids=stats["claim_ids"],
            new_evidence_ids=stats["new_evidence_ids"],
        )
        assert verify == {
            "claims_left": 0,
            "runs_left": 0,
            "links_left": 0,
            "evidence_left": 0,
        }, verify
    finally:
        _delete_provenance(conn, http_trace, http_eid)
        _delete_provenance(conn, inst_trace, inst_eid)
        conn.close()


@pytest.mark.skipif(not _mysql(), reason="需 mysql 模式真库")
def test_cleanup_verifies_links_by_recorded_claim_ids(meas):
    """清理前记录目标 claim IDs → 清理后 links 回查为零（无 trace 列）。"""
    conn = _conn()
    trace = "trace_links_regr"
    eid = f"ev_regr_links_{trace[:8]}"
    try:
        initial = meas._evidence_baseline()
        _insert_provenance(conn, trace, eid)
        assert eid not in initial
        stats = meas._cleanup_traces({trace}, initial)
        assert stats["claim_ids"], "应记录目标 claim IDs"
        assert stats["links"] == 1  # 清理时删除 1 条 link
        verify = meas._verify_cleanup(
            {trace},
            claim_ids=stats["claim_ids"],
            new_evidence_ids=stats["new_evidence_ids"],
        )
        assert verify["links_left"] == 0
        assert verify["claims_left"] == 0 and verify["runs_left"] == 0
        assert verify["evidence_left"] == 0
    finally:
        _delete_provenance(conn, trace, eid)
        conn.close()
