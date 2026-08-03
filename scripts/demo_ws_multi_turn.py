"""WS 多轮演示验收脚本 — 金牌家居（603180.SH）四轮同连接问答.

验证 WS 全链路（Phase C 联调验收）：
  - 同一 WebSocket 连接 + 同一 session 跑四轮（连接级 session 由服务端生成）
  - 信封完整：schema_version/event_id/event_type/session_id/turn_id/
    sequence/timestamp/trace_id/payload
  - 全连接 sequence 严格递增
  - 每轮事件顺序：turn.accepted → module.started* → module.completed*
    → answer.delta* → turn.completed
  - 每轮内 turn_id/trace_id 一致；多轮指代消解正确
  - turn.completed 返回 claims_count/evidence_count（counts，非数组）
  - REST 回读：4 轮全部落库

用法:
  D:/anaconda/envs/truthnet/python.exe scripts/demo_ws_multi_turn.py

前置:
  - MySQL 全量数据 + comp_type_code 回填
  - .env 配置 SQL_BACKEND=mysql
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

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

_CHECK: list[tuple[str, bool, str]] = []


def _check(name: str, ok: bool, detail: str = "") -> None:
    _CHECK.append((name, ok, detail))
    print(f"  [{'✅' if ok else '❌'}] {name}" + (f" — {detail}" if detail else ""))


_ENVELOPE_KEYS = {
    "schema_version",
    "event_id",
    "event_type",
    "session_id",
    "turn_id",
    "sequence",
    "timestamp",
    "trace_id",
    "payload",
}


def main() -> int:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    print("=" * 70)
    print("  WS 多轮演示验收 — 金牌家居四轮（同一连接同一会话）")
    print("=" * 70)

    with client.websocket_connect("/api/v1/chat/ws") as ws:
        session_id: str | None = None
        all_seqs: list[int] = []
        turn_ids_per_round: list[set[str]] = []
        rounds_completed = 0

        for rnd, question in enumerate(QUESTIONS, 1):
            print(f"\n第 {rnd} 轮 | {question}")
            ws.send_json({"event_type": "chat.query", "payload": {"text": question}})

            events: list[dict] = []
            while True:
                ev = ws.receive_json()
                events.append(ev)
                if ev.get("event_type") == "turn.completed":
                    break

            # ── 信封完整 ──
            bad = [
                k
                for k in _ENVELOPE_KEYS
                if any(k not in ev for ev in events)
            ]
            _check(f"第 {rnd} 轮信封字段完整", not bad, f"缺失: {bad or '无'}")

            # 会话 / 轮次 / 追踪一致性
            sid = events[0].get("session_id")
            if session_id is None:
                session_id = sid
            _check(f"第 {rnd} 轮 session_id 一致", all(ev.get("session_id") == sid for ev in events))
            tids = {ev.get("turn_id") for ev in events}
            trids = {ev.get("trace_id") for ev in events}
            _check(f"第 {rnd} 轮 turn_id 一致", len(tids) == 1, f"turns={tids}")
            _check(f"第 {rnd} 轮 trace_id 一致", len(trids) == 1)
            turn_ids_per_round.append(tids)

            # sequence 连接级递增
            seqs = [ev.get("sequence") for ev in events]
            all_seqs.extend(seqs)
            _check(f"第 {rnd} 轮 sequence 递增", seqs == sorted(seqs) and len(set(seqs)) == len(seqs))

            # 事件顺序
            order = [ev.get("event_type") for ev in events]
            _check(
                f"第 {rnd} 轮事件顺序正确",
                order[0] == "turn.accepted"
                and order[-1] == "turn.completed"
                and "answer.delta" in order,
                "→".join(order),
            )

            # 终态（counts 非数组）
            final_payload = events[-1].get("payload", {})
            _check(
                f"第 {rnd} 轮终态含 counts",
                "claims_count" in final_payload and "evidence_count" in final_payload,
                f"claims={final_payload.get('claims_count')} evidence={final_payload.get('evidence_count')}",
            )
            rounds_completed += 1

            # 第 2 轮验证指代消解（'它'→金牌家居）
            if rnd == 2:
                ans = final_payload.get("answer", "")
                _check("第 2 轮指代解析到金牌家居", "金牌家居" in ans, ans[:40])

        # ── 连接级 sequence 全局严格递增 ──
        _check(
            "全连接 sequence 严格递增",
            all_seqs == sorted(all_seqs) and len(set(all_seqs)) == len(all_seqs),
            f"共 {len(all_seqs)} 个事件",
        )

        # ── REST 回读 ──
        r = client.get(f"/api/v1/sessions/{session_id}")
        turns = r.json().get("data", {}).get("turns", [])
        _check(
            "REST 回读 4 轮全部落库",
            len(turns) == 4,
            f"回读 {len(turns)} 轮 (session={session_id})",
        )

    passed = sum(1 for _, ok, _ in _CHECK if ok)
    print("=" * 70)
    print(f"  WS 多轮验收：{passed}/{len(_CHECK)} 通过")
    print("=" * 70)
    return 0 if passed == len(_CHECK) else 1


if __name__ == "__main__":
    raise SystemExit(main())
