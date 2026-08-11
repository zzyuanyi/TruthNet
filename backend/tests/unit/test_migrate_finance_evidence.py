"""迁移脚本两阶段测试（v3.5 + v3.6）— 计划绑定/事务/回滚验收.

v3.6 覆盖（审查要求）：
- 审核计划与 apply 计划完全一致；
- 计划文件被篡改时拒绝；
- dry-run 后旧行变化时拒绝；
- dry-run 后新增 legacy 行时拒绝；
- skips > 0 拒绝正式执行；
- source_title=NULL 可迁移并精确回滚为 NULL；
- 错库备份拒绝；
- 无 --confirm 的 rollback 拒绝；
- 错误 SHA 拒绝；
- legacy 数组备份明确拒绝（"legacy backup unsupported"）；
- 提交前不一致整批回滚。
（含 v3.5 八项：dry-run 零写/零多候选/目标库白名单/并发旧值/批量回滚/
备份不覆盖/恢复可逆/44 条可回查。）
"""

import json
import os
from pathlib import Path

import pytest

from app.core.config import settings

_SCRIPTS = "migrate_finance_evidence"


@pytest.fixture(scope="module")
def mig():
    import importlib.util
    import sys

    path = (
        Path(__file__).resolve().parents[3] / "scripts" / "migrate_finance_evidence.py"
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


_FREE_FIELDS = ["core_profit", "cash_to_assets", "borrow"]


def _pick_free_fields(conn, mig, n):
    """挑 n 个未落库字段（600519.SH 20260331 组合，避免 PK 冲突）。"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT field_path FROM evidence_refs "
            "WHERE source_type='financial_statement' "
            "AND company_code='600519.SH' AND period='20260331'"
        )
        existing = {r[0] for r in cur.fetchall()}
    fields = [f for f in _FREE_FIELDS if f not in existing]
    if len(fields) < n:
        raise RuntimeError(f"无可用字段（需 {n} 个，剩余 {fields}）")
    return fields[:n]


def _row(mig, field="core_profit", code="600519.SH", asof="20260331", title="旧标题"):
    """迁移前**扫描行**格式（evidence_id 用 candidate_id 确定性生成）。"""
    base = {
        "source_record_id": f"{code}|{asof}",
        "period": asof,
        "dataset_version": settings.DATASET_VERSION,
        "company_code": code,
        "source_title": title,
    }
    evidence_id = mig.candidate_id(field, base)
    return {
        "evidence_id": evidence_id,
        "source_type": "financial_statement",
        "field_path": "rule_R1",
        **base,
    }


def _insert(conn, row):
    """插入迁移前状态行（row 的 source_title 可为 None → NULL 原样）。"""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO evidence_refs (evidence_id, source_type, source_record_id, "
            "company_code, field_path, period, value, unit, statement_scope, "
            "source_title, dataset_version, retrieved_at, turn_id, trace_id, "
            "module, source_table) "
            "VALUES (%s,%s,%s,%s,%s,%s,NULL,NULL,'parent_company',%s,%s,"
            "CURRENT_TIMESTAMP,NULL,NULL,'finance',NULL)",
            (
                row["evidence_id"],
                row["source_type"],
                row["source_record_id"],
                row["company_code"],
                row["field_path"],
                row["period"],
                row["source_title"],
                row["dataset_version"],
            ),
        )
    conn.commit()


def _delete(conn, eid):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM evidence_refs WHERE evidence_id=%s", (eid,))
    conn.commit()


def _fix(row, field):
    """从扫描行 + 目标字段构造 fix（与 plan_row 输出同构）。"""
    return {
        "evidence_id": row["evidence_id"],
        "source_type": row["source_type"],
        "old_field_path": row["field_path"],
        "old_source_title": row["source_title"],
        "new_field_path": field,
        "new_source_title": "母公司报表 · 财务反欺诈规则字段证据",
        "rule_id": "R1",
        "company_code": row["company_code"],
        "period": row["period"],
        "source_record_id": row["source_record_id"],
        "dataset_version": row["dataset_version"],
    }


def _plan_payload(mig, db, fixes, skips=None):
    return mig.build_plan(db, fixes, skips or [])


def _tmp_plan(mig, tmp_path, db, fixes, skips=None):
    """写计划文件到 tmp；返回 (path, sha)。"""
    payload = _plan_payload(mig, db, fixes, skips)
    path = tmp_path / "plan.json"
    sha = mig.write_exclusive(path, payload)
    return path, sha, payload


def _current_row(conn, eid):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT source_type, source_record_id, field_path, period, "
            "dataset_version, company_code, source_title "
            "FROM evidence_refs WHERE evidence_id=%s",
            (eid,),
        )
        return cur.fetchone()


# ══ v3.5 基础项 ═══════════════════════════════════════


@pytest.mark.skipif(not _mysql(), reason="需 mysql 模式真库")
def test_dry_run_zero_write(mig, monkeypatch):
    """扫描+计划不修改数据。"""
    db = os.environ.get("MYSQL_TEST_DATABASE", "truthnet_test")
    conn = _conn()
    field = _pick_free_fields(conn, mig, 1)[0]
    row = _row(mig, field=field)
    _insert(conn, row)
    monkeypatch.setattr(
        mig, "_candidate_fields", lambda db_, code, asof: {"R1": {field}}
    )
    try:
        fixes, skips = mig._scan(conn, db)
        assert fixes, f"应产生唯一候选匹配（field={field}）"
        with conn.cursor() as cur:
            cur.execute(
                "SELECT field_path FROM evidence_refs WHERE evidence_id=%s",
                (row["evidence_id"],),
            )
            assert cur.fetchone()[0] == "rule_R1"
    finally:
        _delete(conn, row["evidence_id"])
        conn.close()


def test_zero_candidate_skips(mig):
    outcome = mig.plan_row(_row(mig), {})
    assert "reason" in outcome and "0 个" in outcome["reason"]


def test_multi_candidate_skips(mig, monkeypatch):
    row = _row(mig)
    monkeypatch.setattr(mig, "candidate_id", lambda field, r: row["evidence_id"])
    outcome = mig.plan_row(
        row, {"R1": {"acct_rcv_growth", "oper_rev_growth"}, "R2": {"gap"}}
    )
    assert "reason" in outcome and "3 个" in outcome["reason"]


def test_incoherent_identity_skips(mig):
    row = _row(mig)
    row["period"] = "20251231"  # != source_record_id 的 as_of
    outcome = mig.plan_row(row, {"R1": {"acct_rcv_growth"}})
    assert "reason" in outcome and "不自洽" in outcome["reason"]


def test_db_arg_whitelist_rejects(mig):
    with pytest.raises(SystemExit, match="不在白名单"):
        mig.validate_db_arg("definitely_wrong_db")


def test_backup_exclusive_no_overwrite(mig, tmp_path):
    p = tmp_path / "backup.json"
    p.write_text("{}", encoding="utf-8")
    with pytest.raises(mig.MigrateError, match="已存在"):
        mig.write_exclusive(p, {"rows": []})


def test_plan_metadata_and_sha256(mig, tmp_path):
    import hashlib

    p = tmp_path / "fresh.json"
    fixes = [mig.plan_row(_row(mig), {"R1": {"core_profit"}})]
    payload = _plan_payload(mig, "truthnet_test", fixes)
    sha = mig.write_exclusive(p, payload)
    assert payload["schema_version"] == "1.0"
    assert payload["script_version"] == mig._SCRIPT_VERSION
    assert payload["database"] == "truthnet_test"
    assert payload["fix_count"] == 1 and payload["skip_count"] == 0
    assert "generated_at_utc" in payload
    assert len(sha) == 64
    # 内部 plan_sha256 自洽：去掉自身键后规范化 JSON 的 hash
    assert payload["plan_sha256"] == mig.plan_sha256_of(payload)
    # rows_sha256 = fixes 排序 json 的 hash
    rows_json = json.dumps(fixes, sort_keys=True, ensure_ascii=False)
    assert payload["rows_sha256"] == hashlib.sha256(rows_json.encode()).hexdigest()


@pytest.mark.skipif(not _mysql(), reason="需 mysql 模式真库")
def test_concurrent_old_value_change_rolls_back(mig, tmp_path):
    db = os.environ.get("MYSQL_TEST_DATABASE", "truthnet_test")
    conn = _conn()
    field = _pick_free_fields(conn, mig, 1)[0]
    row = _row(mig, field=field)
    _insert(conn, row)
    try:
        fix = _fix(row, field)
        # 模拟并发修改：执行前改 source_title
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE evidence_refs SET source_title='并发修改后的标题' "
                "WHERE evidence_id=%s",
                (row["evidence_id"],),
            )
        conn.commit()
        payload = _plan_payload(mig, db, [fix])
        with pytest.raises(mig.MigrateError, match="旧值不一致|rowcount"):
            mig.apply_plan(
                conn,
                payload,
                db,
                expected_plan_sha256=payload["plan_sha256"],
                backup_dir=tmp_path,
            )
        fp, title = (
            _current_row(conn, row["evidence_id"])[2],
            _current_row(conn, row["evidence_id"])[6],
        )
        assert fp == "rule_R1" and title == "并发修改后的标题"
    finally:
        _delete(conn, row["evidence_id"])
        conn.close()


@pytest.mark.skipif(not _mysql(), reason="需 mysql 模式真库")
def test_batch_failure_rolls_back_all(mig, tmp_path):
    db = os.environ.get("MYSQL_TEST_DATABASE", "truthnet_test")
    conn = _conn()
    field1, field2 = _pick_free_fields(conn, mig, 2)
    row1 = _row(mig, field=field1)
    row2 = _row(mig, field=field2, title="旧标题2")
    _insert(conn, row1)
    _insert(conn, row2)
    try:
        fix1, fix2 = _fix(row1, field1), _fix(row2, field2)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE evidence_refs SET source_title='并发改' "
                "WHERE evidence_id=%s",
                (row2["evidence_id"],),
            )
        conn.commit()
        payload = _plan_payload(mig, db, [fix1, fix2])
        with pytest.raises(mig.MigrateError):
            mig.apply_plan(
                conn,
                payload,
                db,
                expected_plan_sha256=payload["plan_sha256"],
                backup_dir=tmp_path,
            )
        # 第一条虽已执行但整批回滚
        fp1 = _current_row(conn, row1["evidence_id"])[2]
        assert fp1 == "rule_R1"
    finally:
        _delete(conn, row1["evidence_id"])
        _delete(conn, row2["evidence_id"])
        conn.close()


@pytest.mark.skipif(not _mysql(), reason="需 mysql 模式真库")
def test_rollback_restores_original(mig, tmp_path):
    """migrate → rollback → 原字段精确恢复（含 SHA 校验）。"""
    db = os.environ.get("MYSQL_TEST_DATABASE", "truthnet_test")
    conn = _conn()
    field = _pick_free_fields(conn, mig, 1)[0]
    row = _row(mig, field=field)
    _insert(conn, row)
    backup_path = tmp_path / "rollback_plan.json"
    applied_backup_path = None
    try:
        fix = _fix(row, field)
        payload = _plan_payload(mig, db, [fix])
        mig.write_exclusive(backup_path, payload)
        # apply-plan（写真实备份，测试后清理）
        backup_payload, applied_backup_path = mig.apply_plan(
            conn,
            payload,
            db,
            expected_plan_sha256=payload["plan_sha256"],
            backup_dir=tmp_path,
        )
        fp = _current_row(conn, row["evidence_id"])[2]
        assert fp == field
        # 从 apply 生成的备份回滚（校验 SHA）
        sha = mig.file_sha256(applied_backup_path)
        n = mig.rollback_from_backup(conn, applied_backup_path, db, sha)
        assert n == 1
        fp, title = (
            _current_row(conn, row["evidence_id"])[2],
            _current_row(conn, row["evidence_id"])[6],
        )
        assert fp == "rule_R1" and title == "旧标题"
    finally:
        _delete(conn, row["evidence_id"])
        conn.close()
        if applied_backup_path and applied_backup_path.is_file():
            applied_backup_path.unlink()


@pytest.mark.skipif(not _mysql(), reason="需 mysql 模式真库")
def test_migrated_evidence_fully_queryable(mig):
    """测试库 rule_% 已清零，全部 financial_statement 证据 field_path 为真实字段。"""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM evidence_refs "
                "WHERE source_type='financial_statement' AND field_path LIKE 'rule_%'"
            )
            rule_left = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM evidence_refs "
                "WHERE source_type='financial_statement'"
            )
            total = cur.fetchone()[0]
            cur.execute(
                "SELECT evidence_id FROM evidence_refs "
                "WHERE source_type='financial_statement' LIMIT 5"
            )
            sample = [r[0] for r in cur.fetchall()]
    finally:
        conn.close()
    assert rule_left == 0, f"rule_% 残留 {rule_left} 条"
    assert total > 0
    assert all(str(eid).startswith("ev_fin_") for eid in sample)


# ══ v3.6 新增项 ════════════════════════════════════════


@pytest.mark.skipif(not _mysql(), reason="需 mysql 模式真库")
def test_plan_out_matches_scan(mig, monkeypatch, tmp_path):
    """审核计划与 apply 计划完全一致：dry-run 生成的计划 == 扫描结果。"""
    db = os.environ.get("MYSQL_TEST_DATABASE", "truthnet_test")
    conn = _conn()
    field = _pick_free_fields(conn, mig, 1)[0]
    row = _row(mig, field=field)
    _insert(conn, row)
    monkeypatch.setattr(
        mig, "_candidate_fields", lambda db_, code, asof: {"R1": {field}}
    )
    try:
        fixes, skips = mig._scan(conn, db)
        payload = _plan_payload(mig, db, fixes, skips)
        plan_path = tmp_path / "plan_out.json"
        sha = mig.write_exclusive(plan_path, payload)
        # 从计划文件读回 → 与扫描 fixes 完全一致
        loaded = json.loads(plan_path.read_text(encoding="utf-8"))
        assert loaded["fixes"] == fixes
        assert loaded["skip_count"] == len(skips)
        assert mig.file_sha256(plan_path) == sha
        assert mig.validate_plan(loaded, db, sha, plan_path) is None
    finally:
        _delete(conn, row["evidence_id"])
        conn.close()


def test_plan_tampered_rejected(mig, tmp_path):
    """计划文件被篡改（旧值改掉）→ 校验拒绝。"""
    fix = _fix(_row(mig), "core_profit")
    path, sha, payload = _tmp_plan(mig, tmp_path, "truthnet_test", [fix])
    tampered = dict(payload)
    tampered["fixes"] = [dict(fix, old_field_path="rule_R2")]
    tampered_path = tmp_path / "tampered.json"
    mig.write_exclusive(tampered_path, tampered)
    # 篡改后文件 SHA 与原 SHA 不同 → 文件级拒绝（或内部 rows_sha256 拒绝）
    with pytest.raises(mig.MigrateError, match="SHA 不符|rows_sha256|plan_sha256"):
        mig.validate_plan(tampered, "truthnet_test", sha, tampered_path)


def test_plan_wrong_db_rejected(mig, tmp_path):
    fix = _fix(_row(mig), "core_profit")
    path, sha, payload = _tmp_plan(mig, tmp_path, "truthnet_test", [fix])
    with pytest.raises(mig.MigrateError, match="数据库"):
        mig.validate_plan(payload, "truthnet", sha, path)


def test_plan_skips_rejected(mig, tmp_path):
    """skips > 0 拒绝正式执行。"""
    fix = _fix(_row(mig), "core_profit")
    skip = {"evidence_id": "x", "reason": "跳过"}
    path, sha, payload = _tmp_plan(mig, tmp_path, "truthnet_test", [fix], [skip])
    with pytest.raises(mig.MigrateError, match="skips"):
        mig.validate_plan(payload, "truthnet_test", sha, path)


def test_plan_wrong_sha_rejected(mig, tmp_path):
    """错误 SHA 拒绝（文件级 + 内部 plan_sha256 双防线）。"""
    fix = _fix(_row(mig), "core_profit")
    path, sha, payload = _tmp_plan(mig, tmp_path, "truthnet_test", [fix])
    with pytest.raises(mig.MigrateError, match="SHA 不符"):
        mig.validate_plan(payload, "truthnet_test", "0" * 64, path)


def test_plan_unsupported_script_version_rejected(mig, tmp_path):
    """v3.6.1：计划 script_version 不在支持集合 → 校验拒绝（零写入）。"""
    fix = _fix(_row(mig), "core_profit")
    path, _, payload = _tmp_plan(mig, tmp_path, "truthnet_test", [fix])
    payload["script_version"] = "9.9.9"
    # 普通覆盖写（O_EXCL 拒绝已存在文件）+ 重算文件 SHA
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    sha = mig.file_sha256(path)
    with pytest.raises(mig.MigrateError, match="script_version"):
        mig.validate_plan(payload, "truthnet_test", sha, path)


@pytest.mark.skipif(not _mysql(), reason="需 mysql 模式真库")
def test_dry_run_then_row_changed_rejected(mig, monkeypatch, tmp_path):
    """dry-run 后旧行变化 → apply 时 FOR UPDATE 比较失败拒绝。"""
    db = os.environ.get("MYSQL_TEST_DATABASE", "truthnet_test")
    conn = _conn()
    field = _pick_free_fields(conn, mig, 1)[0]
    row = _row(mig, field=field)
    _insert(conn, row)
    monkeypatch.setattr(
        mig, "_candidate_fields", lambda db_, code, asof: {"R1": {field}}
    )
    try:
        fixes, _ = mig._scan(conn, db)
        payload = _plan_payload(mig, db, fixes)
        # dry-run 后旧行变化（模拟并发写入）
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE evidence_refs SET source_title='事后修改' "
                "WHERE evidence_id=%s",
                (row["evidence_id"],),
            )
        conn.commit()
        with pytest.raises(mig.MigrateError, match="旧值不一致"):
            mig.apply_plan(
                conn,
                payload,
                db,
                expected_plan_sha256=payload["plan_sha256"],
                backup_dir=tmp_path,
            )
        assert _current_row(conn, row["evidence_id"])[2] == "rule_R1"
    finally:
        _delete(conn, row["evidence_id"])
        conn.close()


@pytest.mark.skipif(not _mysql(), reason="需 mysql 模式真库")
def test_dry_run_then_new_legacy_row_rejected(mig, monkeypatch, tmp_path):
    """dry-run 后新增 legacy 行 → 提交前 rule_%==0 断言失败整批回滚。"""
    db = os.environ.get("MYSQL_TEST_DATABASE", "truthnet_test")
    conn = _conn()
    field = _pick_free_fields(conn, mig, 2)
    row1 = _row(mig, field=field[0])
    _insert(conn, row1)
    monkeypatch.setattr(
        mig, "_candidate_fields", lambda db_, code, asof: {"R1": {field[0]}}
    )
    extra = _row(mig, field=field[1], title="额外行")
    try:
        fixes, _ = mig._scan(conn, db)
        payload = _plan_payload(mig, db, fixes)
        # dry-run 后新增一条 legacy 行（计划外）
        _insert(conn, extra)
        with pytest.raises(mig.MigrateError, match="rule_% 残留"):
            mig.apply_plan(
                conn,
                payload,
                db,
                expected_plan_sha256=payload["plan_sha256"],
                backup_dir=tmp_path,
            )
        # 整批回滚：两条都未迁移
        assert _current_row(conn, row1["evidence_id"])[2] == "rule_R1"
        assert _current_row(conn, extra["evidence_id"])[2] == "rule_R1"
    finally:
        _delete(conn, row1["evidence_id"])
        _delete(conn, extra["evidence_id"])
        conn.close()


@pytest.mark.skipif(not _mysql(), reason="需 mysql 模式真库")
def test_null_source_title_migrate_and_rollback(mig, tmp_path):
    """source_title=NULL 可迁移，并精确回滚为 NULL（NULL-safe <=>）。"""
    db = os.environ.get("MYSQL_TEST_DATABASE", "truthnet_test")
    conn = _conn()
    field = _pick_free_fields(conn, mig, 1)[0]
    row = _row(mig, field=field, title=None)  # NULL
    _insert(conn, row)
    applied_backup_path = None
    try:
        fix = _fix(row, field)  # row title=None → old_source_title 自然为 None
        payload = _plan_payload(mig, db, [fix])
        _, applied_backup_path = mig.apply_plan(
            conn,
            payload,
            db,
            expected_plan_sha256=payload["plan_sha256"],
            backup_dir=tmp_path,
        )
        cur = _current_row(conn, row["evidence_id"])
        assert cur[2] == field and cur[6] == mig._SOURCE_TITLE
        sha = mig.file_sha256(applied_backup_path)
        mig.rollback_from_backup(conn, applied_backup_path, db, sha)
        cur = _current_row(conn, row["evidence_id"])
        assert cur[2] == "rule_R1" and cur[6] is None  # NULL 精确恢复
    finally:
        _delete(conn, row["evidence_id"])
        conn.close()
        if applied_backup_path and applied_backup_path.is_file():
            applied_backup_path.unlink()


def test_legacy_array_backup_rejected(mig, tmp_path):
    """旧版数组备份明确报 legacy backup unsupported（不抛 AttributeError）。"""
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps([{"evidence_id": "x"}]), encoding="utf-8")
    with pytest.raises(mig.MigrateError, match="legacy backup unsupported"):
        mig.validate_backup([], "truthnet_test", mig.file_sha256(path), path)


def test_wrong_db_backup_rejected(mig, tmp_path):
    """错库备份拒绝。"""
    fix = _fix(_row(mig), "core_profit")
    payload = _backup_payload(mig, "truthnet", [fix])
    path = tmp_path / "wrongdb.json"
    sha = mig.write_exclusive(path, payload)
    with pytest.raises(mig.MigrateError, match="错库"):
        mig.validate_backup(payload, "truthnet_test", sha, path)


def test_rollback_without_confirm_rejected(mig, monkeypatch, tmp_path):
    """无 --confirm 的 rollback 拒绝（main 层 SystemExit）。

    CI 非 mysql 模式无 MYSQL_TEST_DATABASE 环境变量（白名单为空会先拒绝
    --db），此处显式 setenv 兜底，使测试真正走到 --confirm 检查。
    """
    path = tmp_path / "b.json"
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("MYSQL_TEST_DATABASE", "truthnet_test")
    monkeypatch.setattr(
        __import__("sys"),
        "argv",
        [
            "migrate_finance_evidence.py",
            "--db",
            "truthnet_test",
            "--rollback",
            str(path),
        ],
    )
    with pytest.raises(SystemExit, match="confirm"):
        mig.main()


def test_rollback_wrong_sha_rejected(mig, tmp_path):
    """rollback 错误 SHA 拒绝。"""
    fix = _fix(_row(mig), "core_profit")
    payload = {
        "schema_version": "1.0",
        "script_version": mig._SCRIPT_VERSION,
        "database": "truthnet_test",
        "rows_sha256": mig.rows_sha256_of([fix]),
        "rows": [fix],
    }
    path = tmp_path / "b.json"
    mig.write_exclusive(path, payload)
    with pytest.raises(mig.MigrateError, match="SHA 不符"):
        mig.validate_backup(payload, "truthnet_test", "0" * 64, path)


@pytest.mark.skipif(not _mysql(), reason="需 mysql 模式真库")
def test_precommit_inconsistency_rolls_back(mig, tmp_path):
    """提交前不一致（canonical ID 重算失败）→ 整批回滚。"""
    db = os.environ.get("MYSQL_TEST_DATABASE", "truthnet_test")
    conn = _conn()
    field1, field2 = _pick_free_fields(conn, mig, 2)
    row1 = _row(mig, field=field1)
    row2 = _row(mig, field=field2, title="旧标题2")
    _insert(conn, row1)
    _insert(conn, row2)
    try:
        fix1, fix2 = _fix(row1, field1), _fix(row2, field2)
        # 篡改 fix2 的 new_field_path → 提交前 canonical ID 重算不一致
        fix2_bad = dict(fix2, new_field_path=field1)  # 与 evidence_id 不匹配
        payload = _plan_payload(mig, db, [fix1, fix2_bad])
        with pytest.raises(mig.MigrateError, match="canonical ID 不一致"):
            mig.apply_plan(
                conn,
                payload,
                db,
                expected_plan_sha256=payload["plan_sha256"],
                backup_dir=tmp_path,
            )
        assert _current_row(conn, row1["evidence_id"])[2] == "rule_R1"
        assert _current_row(conn, row2["evidence_id"])[2] == "rule_R1"
    finally:
        _delete(conn, row1["evidence_id"])
        _delete(conn, row2["evidence_id"])
        conn.close()


# ══ v3.6.1 新增项 ══════════════════════════════════════


def _backup_payload(mig, db, fixes, plan_sha256="", file_sha=""):
    return {
        "schema_version": mig._BACKUP_SCHEMA,
        "script_version": mig._SCRIPT_VERSION,
        "database": db,
        "generated_at_utc": "2026-08-11T00:00:00+00:00",
        "row_count": len(fixes),
        "source_plan_sha256": plan_sha256 or "plan_internal_hash",
        "source_plan_file_sha256": file_sha or "plan_file_hash",
        "rows_sha256": mig.rows_sha256_of(fixes),
        "rows": fixes,
    }


def test_backup_row_count_tampered_rejected(mig, tmp_path):
    """v3.6.1：备份 row_count 与 rows 行数不符 → 拒绝。"""
    fix = _fix(_row(mig), "core_profit")
    payload = _backup_payload(mig, "truthnet_test", [fix])
    payload["row_count"] = 99  # 篡改
    path = tmp_path / "b.json"
    sha = mig.write_exclusive(path, payload)
    with pytest.raises(mig.MigrateError, match="row_count"):
        mig.validate_backup(payload, "truthnet_test", sha, path)


def test_backup_missing_plan_binding_rejected(mig, tmp_path):
    """v3.6.1：备份缺计划绑定（source_plan_sha256/source_plan_file_sha256）→ 拒绝。"""
    fix = _fix(_row(mig), "core_profit")
    payload = _backup_payload(mig, "truthnet_test", [fix])
    del payload["source_plan_sha256"]
    path = tmp_path / "b.json"
    sha = mig.write_exclusive(path, payload)
    with pytest.raises(mig.MigrateError, match="缺计划绑定"):
        mig.validate_backup(payload, "truthnet_test", sha, path)


def test_backup_unsupported_schema_rejected(mig, tmp_path):
    """v3.6.1：备份 schema 不在支持集合 → 明确拒绝。"""
    fix = _fix(_row(mig), "core_profit")
    payload = _backup_payload(mig, "truthnet_test", [fix])
    payload["schema_version"] = "9.9"
    path = tmp_path / "b.json"
    sha = mig.write_exclusive(path, payload)
    with pytest.raises(mig.MigrateError, match="schema 不支持"):
        mig.validate_backup(payload, "truthnet_test", sha, path)


def test_backup_unsupported_script_version_rejected(mig, tmp_path):
    """v3.6.1：备份 script_version 不在支持集合 → 拒绝（3.6.0 从未产出真实备份，不在集合内）。"""
    fix = _fix(_row(mig), "core_profit")
    payload = _backup_payload(mig, "truthnet_test", [fix])
    payload["script_version"] = "9.9.9"
    path = tmp_path / "b.json"
    sha = mig.write_exclusive(path, payload)
    with pytest.raises(mig.MigrateError, match="script_version"):
        mig.validate_backup(payload, "truthnet_test", sha, path)


@pytest.mark.skipif(not _mysql(), reason="需 mysql 模式真库")
def test_plain_runtime_error_triggers_explicit_rollback(mig, tmp_path, monkeypatch):
    """v3.6.1：普通 RuntimeError（非 MigrateError）也显式 rollback 并原样抛出。"""
    db = os.environ.get("MYSQL_TEST_DATABASE", "truthnet_test")
    conn = _conn()
    field = _pick_free_fields(conn, mig, 1)[0]
    row = _row(mig, field=field)
    _insert(conn, row)
    rollback_calls = {"n": 0}
    orig_rollback = conn.rollback

    def _tracked_rollback():
        rollback_calls["n"] += 1
        orig_rollback()

    try:
        fix = _fix(row, field)
        payload = _plan_payload(mig, db, [fix])

        # 提交前重算阶段注入普通异常（非 MigrateError）
        def _boom(field_, r):
            raise RuntimeError("unexpected db error")

        monkeypatch.setattr(mig, "candidate_id", _boom)
        monkeypatch.setattr(conn, "rollback", _tracked_rollback)
        with pytest.raises(RuntimeError, match="unexpected db error"):
            mig.apply_plan(
                conn,
                payload,
                db,
                expected_plan_sha256=payload["plan_sha256"],
                backup_dir=tmp_path,
            )
        assert rollback_calls["n"] == 1, "普通异常也必须显式 rollback"
        assert _current_row(conn, row["evidence_id"])[2] == "rule_R1"
    finally:
        monkeypatch.setattr(conn, "rollback", orig_rollback)
        _delete(conn, row["evidence_id"])
        conn.close()


@pytest.mark.skipif(not _mysql(), reason="需 mysql 模式真库")
def test_backup_dir_injection_works(mig, tmp_path):
    """v3.6.1：backup_dir 注入 + 两层计划绑定哈希分离验证。

    内部 plan_sha256 与人工审核计划文件的文件 SHA 是两个不同值：
    - source_plan_sha256 绑定 payload["plan_sha256"]（内部计划哈希）；
    - source_plan_file_sha256 绑定 expected_plan_sha256（审核文件 SHA）。
    """
    db = os.environ.get("MYSQL_TEST_DATABASE", "truthnet_test")
    conn = _conn()
    field = _pick_free_fields(conn, mig, 1)[0]
    row = _row(mig, field=field)
    _insert(conn, row)
    try:
        fix = _fix(row, field)
        payload = _plan_payload(mig, db, [fix])
        # 模拟人工审核的计划文件（独立于内部 plan_sha256 的真实文件哈希）
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        expected_file_sha = mig.file_sha256(plan_file)
        assert expected_file_sha != payload["plan_sha256"], "两层哈希必须分离"
        backup_payload, backup_path = mig.apply_plan(
            conn,
            payload,
            db,
            expected_plan_sha256=expected_file_sha,
            backup_dir=tmp_path,
        )
        assert backup_path.parent == tmp_path, "备份应落在注入目录"
        assert backup_path.is_file()
        # 审计元数据完整：内部计划哈希 + 人工审核文件哈希分别绑定
        assert backup_payload["row_count"] == 1
        assert backup_payload["source_plan_sha256"] == payload["plan_sha256"]
        assert backup_payload["source_plan_file_sha256"] == expected_file_sha
        assert backup_payload["schema_version"] == mig._BACKUP_SCHEMA
    finally:
        _delete(conn, row["evidence_id"])
        conn.close()
