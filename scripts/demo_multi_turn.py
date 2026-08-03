"""多轮对话演示脚本 — 金牌家居（603180.SH）四轮真实问答.

用法:
  python scripts/demo_multi_turn.py                          # TestClient + 唯一会话
  python scripts/demo_multi_turn.py --session-id ses_demo    # 复用指定会话
  python scripts/demo_multi_turn.py --session-id ses_demo --cleanup --yes
                                                             # 清理后从零演示
  python scripts/demo_multi_turn.py --url http://127.0.0.1:8000  # 连已启动的 uvicorn

清理安全:
  - 默认不清理、自动生成唯一会话；--cleanup 才允许删除指定会话
  - --url 远端模式禁止本地清理（无服务端删除接口）
  - 删除顺序：本会话 links → claims → 仅删无全局引用的 evidence → turns → session

前置:
  - MySQL 已导入全量数据 + 已跑 task4_name_backfill.py（comp_type_code 回填）
  - .env 配置 SQL_BACKEND=mysql
"""

import argparse
import io
import sys
import uuid
from pathlib import Path

# 保证中文在 Windows 终端正常显示（仅直接运行时；被 import 时不改写 pytest 捕获）
if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_REPO_ROOT / ".env")

QUESTIONS = [
    "金牌家居有财务造假风险吗",
    "它的应收账款增速为什么异常",
    "那它的大股东最近有什么动作吗",
    "综合给一个风险结论",
]


def _build_client(args):
    if args.url:
        import requests

        base = args.url.rstrip("/")
        return (
            lambda q, sid: requests.post(
                f"{base}/api/v1/chat", json={"question": q, "session_id": sid}
            ).json()["data"],
            lambda sid: requests.get(f"{base}/api/v1/sessions/{sid}").json()["data"],
        )
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    return (
        lambda q, sid: client.post(
            "/api/v1/chat", json={"question": q, "session_id": sid}
        ).json()["data"],
        lambda sid: client.get(f"/api/v1/sessions/{sid}").json()["data"],
    )


def _validate_cleanup_args(args) -> str | None:
    """清理参数校验：返回错误信息或 None（可测试的纯函数）。"""
    if args.cleanup and args.url:
        return "错误：--url 远端模式禁止本地清理（无服务端删除接口）。"
    if args.cleanup and not args.session_id:
        return "错误：--cleanup 需要指定 --session-id。"
    return None


def _evids_to_delete(rows: list[tuple[str, int]]) -> list[str]:
    """rows = [(evidence_id, 全局 link 引用数)] → 应删除（引用数为 0）的 ID。

    其他会话仍引用的证据必须保留（evidence_id 跨会话确定性复用）。
    """
    return [eid for eid, refs in rows if refs == 0]


def _cleanup(session_id: str) -> None:
    """清理指定会话（仅 --cleanup 时调用）。

    删除顺序（保证不破坏其他会话，evidence_id 跨会话确定性复用）：
      1. 本会话 claims 的全部 claim_evidence_links
      2. 本会话 claims
      3. 仅删除『已无任何全局 link 引用』的 evidence（本会话 turn 名下）
      4. 本会话 conversation_turns
      5. 本会话 conversation_sessions
    """
    from sqlalchemy import create_engine, text

    from app.core.config import settings

    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    )
    e = create_engine(url)
    with e.begin() as c:
        turn_ids = [
            r[0]
            for r in c.execute(
                text("SELECT turn_id FROM conversation_turns WHERE session_id=:s"),
                {"s": session_id},
            ).fetchall()
        ]
        # 1. 本会话 claims 的 links
        for tid in turn_ids:
            c.execute(
                text(
                    "DELETE FROM claim_evidence_links WHERE claim_id IN "
                    "(SELECT claim_id FROM claims WHERE turn_id=:t)"
                ),
                {"t": tid},
            )
        # 2. 本会话 claims
        for tid in turn_ids:
            c.execute(text("DELETE FROM claims WHERE turn_id=:t"), {"t": tid})
        # 3. 仅删无全局引用的 evidence（其他会话的 links 仍引用则保留）
        if turn_ids:
            ev_rows = c.execute(
                text("SELECT evidence_id FROM evidence_refs " "WHERE turn_id IN :tids"),
                {"tids": tuple(turn_ids)},
            ).fetchall()
            refcount_rows = [
                (
                    eid,
                    c.execute(
                        text(
                            "SELECT COUNT(*) FROM claim_evidence_links "
                            "WHERE evidence_id=:eid"
                        ),
                        {"eid": eid},
                    ).scalar_one(),
                )
                for (eid,) in ev_rows
            ]
            for eid in _evids_to_delete(refcount_rows):
                c.execute(
                    text("DELETE FROM evidence_refs WHERE evidence_id=:eid"),
                    {"eid": eid},
                )
        # 4/5. turns + session
        c.execute(
            text("DELETE FROM conversation_turns WHERE session_id=:s"),
            {"s": session_id},
        )
        c.execute(
            text("DELETE FROM conversation_sessions WHERE session_id=:s"),
            {"s": session_id},
        )
    e.dispose()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default="", help="已启动的后端地址（默认用 TestClient）")
    ap.add_argument(
        "--session-id", default="", help="指定会话 ID（默认自动生成唯一会话，不清理）"
    )
    ap.add_argument(
        "--cleanup", action="store_true", help="清理指定会话（需 --session-id）"
    )
    ap.add_argument("--yes", action="store_true", help="跳过清理交互确认")
    args = ap.parse_args()

    err = _validate_cleanup_args(args)
    if err:
        print(err)
        return 1

    session_id = args.session_id or f"ses_demo_{uuid.uuid4().hex[:12]}"
    if args.cleanup:
        if not args.yes:
            ans = input(f"确认清理会话 {session_id} 的全部数据？[y/N] ") or "n"
            if ans.lower() != "y":
                # 默认拒绝 → 改用全新唯一会话继续，不清理
                session_id = f"ses_demo_{uuid.uuid4().hex[:12]}"
                print(f"已取消清理，改用唯一会话 {session_id}")
        else:
            _cleanup(session_id)
        if args.yes:
            print(f"[会话] {session_id}（已清理，从零开始）\n")
    else:
        print(f"[会话] {session_id}（唯一会话，不清理）\n")

    ask, get_session = _build_client(args)
    print("=" * 70)
    print("  织网鉴真 · 多轮智能问答演示 — 金牌家居（603180.SH）")
    print("  真实后端：LangGraph + 真实规则引擎 + MySQL 全量数据")
    print("=" * 70)

    for i, q in enumerate(QUESTIONS, 1):
        d = ask(q, session_id)
        print(f"{'-' * 70}")
        print(f"第 {i} 轮 | 用户：{q}")
        print(f"{'-' * 70}")
        print(f"【回答】\n{d['answer']}\n")
        follow = d.get("follow_ups") or []
        if follow:
            print(
                f"【追问建议】{' ｜ '.join(follow[:4])}{'…' if len(follow) > 4 else ''}"
            )
        print(f"【证据】{len(d.get('evidence', []))} 条（可追溯至规则、字段和来源）\n")

    print("=" * 70)
    print(f"会话回读 REST 验证：GET /api/v1/sessions/{session_id}")
    turns = get_session(session_id)["turns"]
    print(f"→ 共 {len(turns)} 轮全部真实落库：")
    for t in turns:
        print(f"   [{t['turn_index']}] {t['question'][:28]}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
