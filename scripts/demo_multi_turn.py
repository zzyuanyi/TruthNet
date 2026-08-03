"""多轮对话演示脚本 — 金牌家居（603180.SH）四轮真实问答.

用法:
  python scripts/demo_multi_turn.py            # 默认 TestClient（无需启动服务）
  python scripts/demo_multi_turn.py --url http://127.0.0.1:8000   # 连已启动的 uvicorn

前置:
  - MySQL 已导入全量数据 + 已跑 task4_name_backfill.py（comp_type_code 回填）
  - .env 配置 SQL_BACKEND=mysql
"""

import argparse
import io
import sys
from pathlib import Path

# 保证中文在 Windows 终端正常显示
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
SESSION_ID = "ses_demo_teacher"


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


def _cleanup(session_id: str) -> None:
    from sqlalchemy import create_engine, text

    from app.core.config import settings

    url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    )
    e = create_engine(url)
    with e.begin() as c:
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
    args = ap.parse_args()

    ask, get_session = _build_client(args)
    print("=" * 70)
    print("  织网鉴真 · 多轮智能问答演示 — 金牌家居（603180.SH）")
    print("  真实后端：LangGraph + 真实规则引擎 + MySQL 全量数据")
    print("=" * 70)

    _cleanup(SESSION_ID)
    print(f"\n[会话] {SESSION_ID}（历史已清理，从零开始）\n")

    for i, q in enumerate(QUESTIONS, 1):
        d = ask(q, SESSION_ID)
        print(f"{'-' * 70}")
        print(f"第 {i} 轮 | 用户：{q}")
        print(f"{'-' * 70}")
        print(f"【回答】\n{d['answer']}\n")
        follow = d.get("follow_ups") or []
        if follow:
            print(
                f"【追问建议】{' ｜ '.join(follow[:4])}{'…' if len(follow) > 4 else ''}"
            )
        print(
            f"【证据】{len(d.get('evidence', []))} 条（每条含规则/字段/数值/口径来源）\n"
        )

    print("=" * 70)
    print(f"会话回读 REST 验证：GET /api/v1/sessions/{SESSION_ID}")
    turns = get_session(SESSION_ID)["turns"]
    print(f"→ 共 {len(turns)} 轮全部真实落库：")
    for t in turns:
        print(f"   [{t['turn_index']}] {t['question'][:28]}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
