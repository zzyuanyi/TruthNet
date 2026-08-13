"""孤儿清理三类安全回归测试 — 8.11 P0（审查）：防误删全局证据 + 测试本身安全。

需要 TRUTHNET_RUN_EXTERNAL_TESTS=1 + MySQL 数据齐备。

覆盖（审查要求）：
  1. 全局 NULL turn_id 证据保留（如 neo4j_relationship 股权证据）；
  2. 失效非空 turn_id、无任何引用的证据 → 删除；
  3. 失效非空 turn_id、被有效 Claim 引用的证据 → 只置空 turn_id（保留行）。

安全约束（8.11 P0/P2 审查修订）：
  - turn_bad 使用不存在的随机 ID（不插入 turns），保证"失效"语义真实；
  - setup、清理、断言全部在同一个显式事务内，finally 强制 rollback——
    即使进程被强制终止，未提交事务随连接断开回滚，真库零残留、零污染；
  - execute 模式建议停后端后运行（避免全表清理语句与在线写入竞争）。
"""

import os
import uuid

import pytest
from sqlalchemy import create_engine, text

from app.core.config import settings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.external,
    pytest.mark.skipif(
        os.environ.get("TRUTHNET_RUN_EXTERNAL_TESTS") != "1",
        reason="TRUTHNET_RUN_EXTERNAL_TESTS=1 required for external tests",
    ),
]


@pytest.fixture()
def engine():
    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    )
    eng = create_engine(url)
    yield eng
    eng.dispose()


@pytest.fixture()
def tmp_ids():
    tag = uuid.uuid4().hex[:10]
    return {
        "tag": tag,
        "session_id": f"ses_orph_{tag}",
        # 故意不插入的随机 turn_id（保证 LEFT JOIN 无匹配 = 真正失效）
        "turn_bad": f"turn_ghost_{tag}",
        "turn_good": f"turn_good_{tag}",
    }


def _setup(conn, ids) -> None:
    """在传入事务内插入测试数据（不提交，随事务 rollback 撤销）。"""
    conn.execute(
        text(
            "INSERT INTO conversation_sessions "
            "(session_id, title, status, created_at, updated_at) "
            "VALUES (:s, 'orphan-test', 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ),
        {"s": ids["session_id"]},
    )
    conn.execute(
        text(
            "INSERT INTO conversation_turns "
            "(turn_id, session_id, turn_index, question, created_at) "
            "VALUES (:tg, :s, 1, 'good', CURRENT_TIMESTAMP)"
        ),
        {"tg": ids["turn_good"], "s": ids["session_id"]},
    )
    # 1. 全局证据（turn_id=NULL）
    conn.execute(
        text(
            "INSERT INTO evidence_refs "
            "(evidence_id, source_type, source_record_id, company_code, "
            "dataset_version, retrieved_at) "
            "VALUES (:e1, 'neo4j_relationship', 'rec_g1', '600518.SH', 'test-v1', "
            "CURRENT_TIMESTAMP)"
        ),
        {"e1": f"ev_global_{ids['tag']}"},
    )
    # 2. 失效非空 turn（不存在的 ID）、无引用 → 应删除
    conn.execute(
        text(
            "INSERT INTO evidence_refs "
            "(evidence_id, source_type, source_record_id, company_code, "
            "dataset_version, retrieved_at, turn_id) "
            "VALUES (:e2, 'financial_statement', 'rec_g2', '600518.SH', 'test-v1', "
            "CURRENT_TIMESTAMP, :tb)"
        ),
        {"e2": f"ev_orphan_{ids['tag']}", "tb": ids["turn_bad"]},
    )
    # 3. 失效非空 turn、被有效 claim 引用 → 只置空
    conn.execute(
        text(
            "INSERT INTO evidence_refs "
            "(evidence_id, source_type, source_record_id, company_code, "
            "dataset_version, retrieved_at, turn_id) "
            "VALUES (:e3, 'announcement', 'rec_g3', '600518.SH', 'test-v1', "
            "CURRENT_TIMESTAMP, :tb)"
        ),
        {"e3": f"ev_linked_{ids['tag']}", "tb": ids["turn_bad"]},
    )
    conn.execute(
        text(
            "INSERT INTO claims "
            "(claim_id, turn_id, company_code, claim_type, severity, "
            "verification_status, module, text, generated_at) "
            "VALUES (:c, :tg, '600518.SH', 'rule', 'orange', 'pending', "
            "'finance', '测试 claim', CURRENT_TIMESTAMP)"
        ),
        {"c": f"clm_linked_{ids['tag']}", "tg": ids["turn_good"]},
    )
    conn.execute(
        text(
            "INSERT INTO claim_evidence_links (claim_id, evidence_id) VALUES (:c, :e3)"
        ),
        {"c": f"clm_linked_{ids['tag']}", "e3": f"ev_linked_{ids['tag']}"},
    )


def _assert_cases(conn, ids) -> None:
    """同一事务内断言三类安全边界。"""
    with conn.execute(
        text("SELECT COUNT(*) FROM evidence_refs WHERE evidence_id = :e1"),
        {"e1": f"ev_global_{ids['tag']}"},
    ) as r:
        assert r.scalar_one() == 1, "全局 NULL turn_id 证据不得被删除"

    with conn.execute(
        text("SELECT COUNT(*) FROM evidence_refs WHERE evidence_id = :e2"),
        {"e2": f"ev_orphan_{ids['tag']}"},
    ) as r:
        assert r.scalar_one() == 0, "失效 turn 且无引用的证据应被删除"

    linked = conn.execute(
        text("SELECT turn_id FROM evidence_refs WHERE evidence_id = :e3"),
        {"e3": f"ev_linked_{ids['tag']}"},
    ).first()
    assert linked is not None, "被有效引用的证据行必须保留"
    assert linked[0] is None, "被有效引用的证据 turn_id 应被置空"

    with conn.execute(
        text("SELECT COUNT(*) FROM claim_evidence_links WHERE claim_id = :c"),
        {"c": f"clm_linked_{ids['tag']}"},
    ) as r:
        assert r.scalar_one() == 1, "有效 claim 的 link 必须保留"


def test_orphan_cleanup_three_safety_cases(engine, tmp_ids):
    """三类安全边界一次验证（执行模式，全事务回滚，真库零污染）。"""
    from scripts.cleanup_sessions import _cleanup_orphans

    conn = engine.connect()
    tx = conn.begin()
    try:
        _setup(conn, tmp_ids)
        _cleanup_orphans(conn, execute=True)
        _assert_cases(conn, tmp_ids)
    finally:
        # setup + 清理 + 断言全部在事务内：rollback 撤销一切，真库无残留
        tx.rollback()
        conn.close()


def test_global_evidence_id_guard_allows_legal_nullify(engine, tmp_ids):
    """主流程级（8.11 P3 审查）：全局证据保留 + 被引用失效证据置空 → 保护放行。

    复刻 main() --orphans --confirm 的提交前保护流程：before_ids → 清理 →
    missing_ids 检查 → 四项完整性验收；置空导致全局集合新增是合法行为，
    不得触发回滚（计数保护时代的误回滚边界）。
    """
    from scripts.cleanup_sessions import (
        _cleanup_orphans,
        _global_evidence_ids,
        _integrity_stats,
    )

    conn = engine.connect()
    tx = conn.begin()
    try:
        _setup(conn, tmp_ids)
        before_ids = _global_evidence_ids(conn)
        assert f"ev_global_{tmp_ids['tag']}" in before_ids
        # 被引用失效证据此时 turn_id 非空 → 不在全局集合

        _cleanup_orphans(conn, execute=True)

        after_ids = _global_evidence_ids(conn)
        missing = before_ids - after_ids
        assert not missing, f"已有全局 Evidence 不得消失: {missing}"
        assert f"ev_global_{tmp_ids['tag']}" in after_ids, "全局证据必须保留"
        assert (
            f"ev_linked_{tmp_ids['tag']}" in after_ids
        ), "被有效引用的失效证据置空后应出现在全局集合（合法新增，放行）"

        # 提交前四项完整性验收（同 main 逻辑）
        st = _integrity_stats(conn)
        for k in (
            "claims_missing_turn",
            "evidence_missing_turn",
            "links_missing_claim",
            "links_missing_evidence",
        ):
            assert st[k] == 0, f"提交前验收项 {k} 应为 0，实际 {st[k]}"
    finally:
        tx.rollback()
        conn.close()


def test_global_evidence_id_guard_detects_deletion(engine, tmp_ids):
    """主流程级（8.11 P3 审查）：已有全局 Evidence ID 消失 → 保护必须检出。

    模拟误删（把全局证据 turn_id 改为非空使其离开全局集合）——
    集合比较能捕获，且"一删一增、总数不变"无法绕过。
    """
    from scripts.cleanup_sessions import _global_evidence_ids

    conn = engine.connect()
    tx = conn.begin()
    try:
        _setup(conn, tmp_ids)
        before_ids = _global_evidence_ids(conn)
        conn.execute(
            text(
                "UPDATE evidence_refs SET turn_id = 'turn_ghost_x' "
                "WHERE evidence_id = :e"
            ),
            {"e": f"ev_global_{tmp_ids['tag']}"},
        )
        after_ids = _global_evidence_ids(conn)
        missing = before_ids - after_ids
        assert (
            f"ev_global_{tmp_ids['tag']}" in missing
        ), "被误删的全局证据必须被检出（触发回滚）"
    finally:
        tx.rollback()
        conn.close()


def test_orphan_cleanup_dry_run_does_not_write(engine, tmp_ids):
    """dry-run（execute=False）不得产生任何写操作；事务回滚不留夹具。"""
    from scripts.cleanup_sessions import _cleanup_orphans

    conn = engine.connect()
    tx = conn.begin()
    try:
        _setup(conn, tmp_ids)
        _cleanup_orphans(conn, execute=False)
        with conn.execute(
            text(
                "SELECT COUNT(*) FROM evidence_refs WHERE evidence_id IN "
                "(:e1, :e2, :e3)"
            ),
            {
                "e1": f"ev_global_{tmp_ids['tag']}",
                "e2": f"ev_orphan_{tmp_ids['tag']}",
                "e3": f"ev_linked_{tmp_ids['tag']}",
            },
        ) as r:
            assert r.scalar_one() == 3, "dry-run 不得删除任何证据"
    finally:
        tx.rollback()
        conn.close()
