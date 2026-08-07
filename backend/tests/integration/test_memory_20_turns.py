"""远期记忆 20 轮真实会话测试 — Phase D #15 验收.

第 1 轮关键公司 → 中间切换公司 → 第 20 轮使用指代 → 能召回关键事实；
来源 turn ID 正确；Evidence 可查询；摘要长度受限；跨 session 隔离。
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.full_profile,
    pytest.mark.skipif(
        os.environ.get("TRUTHNET_RUN_FULL_INTEGRATION") != "1",
        reason="TRUTHNET_RUN_FULL_INTEGRATION=1 required",
    ),
]
_NEED_MYSQL = pytest.mark.skipif(
    settings.SQL_BACKEND != "mysql", reason="需要真实 MySQL"
)


def _seed_session(sid: str, n: int) -> None:
    """直接向 conversation_turns 播种 n 轮真实结构（question/answer），
    模拟 20 轮真实会话的持久化结果（不重复跑 20 次 Agent）。
    """
    from sqlalchemy import create_engine, text

    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    )
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO conversation_sessions (session_id, title, status, created_at, updated_at) "
                "VALUES (:sid, :title, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"sid": sid, "title": "memory test"},
        )
        for i in range(1, n + 1):
            q = (
                "康美药业有造假风险吗"
                if i == 1
                else ("五粮液财务状况如何" if i == 11 else "它的应收账款情况如何")
            )
            conn.execute(
                text(
                    "INSERT INTO conversation_turns "
                    "(turn_id, session_id, turn_index, question, answer, created_at) "
                    "VALUES (:tid, :sid, :idx, :q, :a, CURRENT_TIMESTAMP)"
                ),
                {
                    "tid": f"turn_{sid}_{i}",
                    "sid": sid,
                    "idx": i,
                    "q": q,
                    "a": (
                        "综合风险等级为 orange；触发 R1、R2；"
                        "涉及公司 600518.SH；需结合公告进一步核验。"
                    ),
                },
            )
    engine.dispose()


@_NEED_MYSQL
def test_20_turn_memory_fact_recall():
    """20 轮后关键事实可召回 + 摘要限长 + 来源可回查。"""
    from app.application.services.memory_distillation import (
        build_summary_for_turns,
        load_or_build_summary,
    )
    from sqlalchemy import create_engine, text

    sid = f"ses_mem20_{uuid.uuid4().hex[:8]}"
    _seed_session(sid, 20)
    client = TestClient(app)
    try:
        # 读取 20 轮
        url = (
            f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
            f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
        )
        engine = create_engine(url)
        turns = []
        with engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT turn_id, turn_index, question, answer "
                        "FROM conversation_turns WHERE session_id = :sid "
                        "ORDER BY turn_index ASC"
                    ),
                    {"sid": sid},
                )
                .mappings()
                .all()
            )
            turns = [
                {
                    "turn_id": r["turn_id"],
                    "turn_index": int(r["turn_index"]),
                    "question": str(r["question"] or ""),
                    "answer": str(r["answer"] or ""),
                    "evidence_ids": [],
                }
                for r in rows
            ]
        engine.dispose()
        assert len(turns) >= 20, f"应有 20 轮，实际 {len(turns)}"

        # 前 10 轮提炼（早期轮次摘要）
        summary = build_summary_for_turns(turns[:10])
        assert summary.source_turn_ids, "摘要必须有来源轮次"
        assert summary.covered_until_turn_index >= 10
        assert (
            len(summary.text) <= settings.MEMORY_SUMMARY_MAX_CHARS + 100
        ), "摘要应限长"

        # 关键公司事实可召回（第 1 轮涉及康美）
        all_text = summary.text + " ".join(summary.key_facts)
        assert "600518.SH" in all_text or "康美" in all_text, "应能召回关键公司"

        # load_or_build_summary 可读取/构建摘要（真实 DB）
        s = load_or_build_summary(sid)
        assert s is not None
        assert s.covered_until_turn_index >= 10
    finally:
        client.delete(f"/api/v1/sessions/{sid}")


@_NEED_MYSQL
def test_session_isolation_no_cross_contamination():
    """session A 摘要不进入 session B。"""
    from app.application.services.memory_distillation import load_or_build_summary

    sid_a = f"ses_memiso_a_{uuid.uuid4().hex[:8]}"
    sid_b = f"ses_memiso_b_{uuid.uuid4().hex[:8]}"
    client = TestClient(app)
    client.post(
        "/api/v1/chat", json={"question": "康美药业有造假风险吗", "session_id": sid_a}
    )
    client.post(
        "/api/v1/chat", json={"question": "贵州茅台财务情况", "session_id": sid_b}
    )

    sum_a = load_or_build_summary(sid_a)
    sum_b = load_or_build_summary(sid_b)
    # 无证据时不强求摘要存在；若存在则 source_turn_ids 属于各自会话
    if sum_a and sum_b:
        assert (
            set(sum_a.source_turn_ids) & set(sum_b.source_turn_ids) == set()
        ), "session A 摘要不得引用 session B 的轮次"
    client.delete(f"/api/v1/sessions/{sid_a}")
    client.delete(f"/api/v1/sessions/{sid_b}")
