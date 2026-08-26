"""康美无公告降级场景验收脚本（Phase C 完成标志第一条）.

验证康美（600518.SH）降级链路：
  - 实体解析 → 康美；财务 0 触发（无规则明细展开）
  - 无公告 → timeline 空 + NO_ANNOUNCEMENT_DATA warning，不 Mock
  - 第二轮指代延续（'它'→康美）+ 股权链路
  - 本地模式：落库逐 Claim 验证（仅 equity、verified、绑定证据）

用法:
  python scripts/verify_kangmei_degrade.py
  python scripts/verify_kangmei_degrade.py --url http://127.0.0.1:8001
  （需在 truthnet 环境执行，见 CLAUDE.md 环境约定）

注意:
  --url 远端模式禁止查询本机 MySQL（本机库 ≠ 远端库），
  落库验证标记为 SKIP，不伪装通过。
"""

from __future__ import annotations

import argparse
import io
import sys
import uuid
from pathlib import Path

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_REPO_ROOT / ".env")

ROUND1 = "康美药业有财务造假风险吗"
ROUND2 = "它的股权结构怎么样"

_CHECK: list[tuple[str, bool | None, str]] = []


def _check(name: str, ok: bool | None, detail: str = "") -> None:
    _CHECK.append((name, ok, detail))
    if ok is None:
        print(f"  [SKIP] {name}" + (f" — {detail}" if detail else ""))
    else:
        print(f"  [{'✅' if ok else '❌'}] {name}" + (f" — {detail}" if detail else ""))


def main() -> int:
    _CHECK.clear()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default="", help="已启动的后端地址（默认 TestClient）")
    args = ap.parse_args()

    session_id = f"ses_kangmei_{uuid.uuid4().hex[:12]}"
    print(f"[会话] {session_id}（用于人工追溯）\n")

    if args.url:
        import requests

        def ask(q: str) -> dict:
            r = requests.post(
                f"{args.url.rstrip('/')}/api/v1/chat",
                json={"question": q, "session_id": session_id},
                timeout=120,
            )
            r.raise_for_status()
            return r.json()["data"]

    else:
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)

        def ask(q: str) -> dict:
            return client.post(
                "/api/v1/chat", json={"question": q, "session_id": session_id}
            ).json()["data"]

    print("=" * 70)
    print("  康美无公告降级场景验收 — 600518.SH")
    print("=" * 70)

    # ── 第 1 轮：完整链路 + 无公告降级 ─────────────────────
    print(f"\n第 1 轮 | {ROUND1}")
    d1 = ask(ROUND1)
    ans1 = d1.get("answer", "")
    warns1 = d1.get("warnings") or []
    timeline1 = d1.get("timeline") or []

    _check(
        "实体解析到康美（600518.SH）", "600518" in ans1 or "康美药业" in ans1, ans1[:40]
    )
    _check(
        "无公告降级：NO_ANNOUNCEMENT_DATA warning",
        any("NO_ANNOUNCEMENT_DATA" in w for w in warns1),
        "；".join(w for w in warns1 if "NO_ANNOUNCEMENT" in w),
    )
    _check(
        "事件 timeline 为空（不伪造）", timeline1 == [], f"timeline={len(timeline1)}"
    )
    _check(
        "财务 0 触发口径（无规则明细展开）",
        "触发规则明细" not in ans1,
        ans1[-40:],
    )
    _check(
        "无事件维度描述（公告无数据不伪造事件）",
        "事件维度" not in ans1,
        ans1[-60:],
    )
    print(f"\n【第 1 轮回答】\n{ans1}\n")

    # ── 第 2 轮：指代延续 + 股权（不重复要求公告 warning）──
    print(f"第 2 轮 | {ROUND2}")
    d2 = ask(ROUND2)
    ans2 = d2.get("answer", "")

    _check("指代延续（'它'→康美）", "600518" in ans2 or "康美药业" in ans2, ans2[:40])
    _check(
        "股权链路返回（股东数据存在）",
        "股权维度" in ans2 and "控制链" in ans2,
        ans2[:60],
    )
    print(f"\n【第 2 轮回答】\n{ans2}\n")

    # ── 落库逐 Claim 验证（仅本地模式）────────────────────
    if args.url:
        _check(
            "数据库落库验证",
            None,
            "远端模式 SKIP：本机 .env 数据库不一定属于远端服务",
        )
    else:
        from sqlalchemy import create_engine, text

        from app.core.config import settings

        url = (
            f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
            f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
        )
        e = create_engine(url)
        with e.connect() as c:
            rows = c.execute(
                text(
                    "SELECT t.turn_index, c.claim_id, c.claim_type, "
                    "c.verification_status, COUNT(l.evidence_id) AS link_count "
                    "FROM conversation_turns t "
                    "JOIN claims c ON c.turn_id = t.turn_id "
                    "LEFT JOIN claim_evidence_links l ON l.claim_id = c.claim_id "
                    "WHERE t.session_id = :s "
                    "GROUP BY t.turn_index, c.claim_id, c.claim_type, "
                    "c.verification_status "
                    "ORDER BY t.turn_index, c.claim_id"
                ),
                {"s": session_id},
            ).fetchall()
        e.dispose()

        claim_rows = [
            {
                "turn_index": r[0],
                "claim_id": r[1],
                "claim_type": r[2],
                "verification_status": r[3],
                "link_count": r[4],
            }
            for r in rows
        ]
        turns_covered = {r["turn_index"] for r in claim_rows}
        types = {r["claim_type"] for r in claim_rows}

        _check(
            "两轮均存在 Claim",
            turns_covered == {1, 2},
            f"覆盖轮次={sorted(turns_covered)}",
        )
        _check(
            "所有 Claim 均为 equity（无 financial/event）",
            types == {"equity"},
            str(types),
        )
        _check(
            "每条 Claim verification_status=verified",
            all(r["verification_status"] == "verified" for r in claim_rows),
            str({r["verification_status"] for r in claim_rows}),
        )
        _check(
            "每条 Claim 绑定证据（link_count≥1）",
            all(r["link_count"] >= 1 for r in claim_rows),
            f"claims={len(claim_rows)} links={[r['link_count'] for r in claim_rows]}",
        )

    # ── 汇总（SKIP 不视为失败；仅当存在 False 时返回 1）───
    passed = sum(1 for _, ok, _ in _CHECK if ok is True)
    skipped = sum(1 for _, ok, _ in _CHECK if ok is None)
    failures = sum(1 for _, ok, _ in _CHECK if ok is False)
    total = len(_CHECK)
    print("=" * 70)
    print(
        f"  康美降级场景验收：{passed}/{total} 通过"
        + (f"（{skipped} 项 SKIP）" if skipped else "")
    )
    print("=" * 70)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
