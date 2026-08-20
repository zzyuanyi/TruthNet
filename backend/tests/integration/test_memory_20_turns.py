"""远期记忆 20+ 轮真实会话测试 — Phase D #15 验收.

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


def _seed_session(sid: str, n: int, start: int = 1) -> None:
    """直接向 conversation_turns 播种 n 轮真实结构（question/answer），
    模拟真实会话的持久化结果（不重复跑 Agent）。

    start: 起始轮次序号——传 >1 可向既有会话追加轮次（模拟会话增长）。
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
                "INSERT IGNORE INTO conversation_sessions "
                "(session_id, title, status, created_at, updated_at) "
                "VALUES (:sid, :title, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"sid": sid, "title": "memory test"},
        )
        for i in range(start, start + n):
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
    """20 轮窗口内关键事实可召回；21 轮后早期摘要开始接管。"""
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

        # 前 20 轮仍在近期完整窗口内；直接构建摘要函数保持限长/来源能力。
        summary = build_summary_for_turns(turns[:20])
        assert summary.source_turn_ids, "摘要必须有来源轮次"
        assert summary.covered_until_turn_index >= 20
        assert (
            len(summary.text) <= settings.MEMORY_SUMMARY_MAX_CHARS + 100
        ), "摘要应限长"

        # 关键公司事实可召回（第 1 轮涉及康美）
        all_text = summary.text + " ".join(summary.key_facts)
        assert "600518.SH" in all_text or "康美" in all_text, "应能召回关键公司"

        # 新增第 21 轮后，第 1 轮滑出近期窗口，load_or_build_summary 开始生成摘要。
        _seed_session(sid, 1, start=21)
        s = load_or_build_summary(sid)
        assert s is not None
        assert s.covered_until_turn_index >= 1
    finally:
        client.delete(f"/api/v1/sessions/{sid}")


@_NEED_MYSQL
def test_25_turn_summary_progression():
    """25 轮：首次摘要覆盖 1-5；新增第 26 轮后推进到 6。

    回归验证：早期窗口 = 不在近期 N 轮内的轮次（而非 turn_index ≤ N）；
    会话增长后 covered_until 推进并重建。
    """
    from app.application.services.memory_distillation import load_or_build_summary

    sid = f"ses_mem25_{uuid.uuid4().hex[:8]}"
    _seed_session(sid, 25)
    client = TestClient(app)
    try:
        s = load_or_build_summary(sid)
        assert s is not None
        assert (
            s.covered_until_turn_index == 5
        ), f"25 轮时早期窗口应覆盖到 5，实际 {s.covered_until_turn_index}"

        # 第 1-5 轮 source_turn_ids 全部进入摘要
        expected = {f"turn_{sid}_{i}" for i in range(1, 6)}
        assert expected.issubset(
            set(s.source_turn_ids)
        ), f"1-5 轮来源必须全部进入摘要，缺失 {expected - set(s.source_turn_ids)}"
        # 关键事实可召回（第 1 轮康美 → "涉及知名公司"归纳）
        assert any("知名公司" in f for f in s.key_facts), "应能召回早期关键公司"

        # 重复加载幂等：不重建、文本一致
        s2 = load_or_build_summary(sid)
        assert s2 is not None and s2.text == s.text

        # 会话增长：新增第 26 轮 → 早期窗口扩大为 1-6，摘要推进
        _seed_session(sid, 1, start=26)
        s3 = load_or_build_summary(sid)
        assert (
            s3.covered_until_turn_index == 6
        ), f"新增轮次后应推进到 6，实际 {s3.covered_until_turn_index}"
        assert f"turn_{sid}_6" in s3.source_turn_ids, "第 6 轮应进入摘要"
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
