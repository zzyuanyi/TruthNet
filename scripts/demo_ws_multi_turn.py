"""WS 多轮演示验收脚本 — 金牌家居（603180.SH）四轮同连接问答.

验证 WS 全链路（Phase C 联调验收）：
  - 同一 WebSocket 连接 + 同一 session 跑四轮（连接级 session 由服务端生成）
  - 信封严格：9 字段、schema_version=1.0、event_id/session/turn/trace 非空、
    sequence 正整数、payload 字典；全连接 event_id 不重复
  - 完整事件顺序：turn.accepted → module.started* → module.completed*
    → answer.delta* → artifact.upsert+ → turn.completed
  - 每模块 started 早于该模块 completed；started/completed 模块集合一致
  - 跨轮：四轮 session 相同、turn/trace 各不相同、REST 回读 4 轮、
    问题顺序一致、company_code=603180.SH、REST turn ID 与 WS 一致

用法:
  python scripts/demo_ws_multi_turn.py
  （需在 truthnet 环境执行，见 CLAUDE.md 环境约定）

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
COMPANY_CODE = "603180.SH"

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
    _CHECK.clear()
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    print("=" * 70)
    print("  WS 多轮演示验收 — 金牌家居四轮（同一连接同一会话）")
    print("=" * 70)

    with client.websocket_connect("/api/v1/chat/ws") as ws:
        session_id: str | None = None
        all_seqs: list[int] = []
        all_turn_ids: list[str] = []
        all_trace_ids: list[str] = []
        all_event_ids: list[str] = []
        sids_per_round: list[str] = []

        for rnd, question in enumerate(QUESTIONS, 1):
            print(f"\n第 {rnd} 轮 | {question}")
            ws.send_json({"event_type": "chat.query", "payload": {"text": question}})

            events: list[dict] = []
            while True:
                ev = ws.receive_json()
                events.append(ev)
                etype = ev.get("event_type")
                if etype == "turn.failed":
                    _check(
                        f"第 {rnd} 轮 turn.failed（应失败退出）", False, str(ev)[:120]
                    )
                    print("=" * 70)
                    print(
                        f"  WS 多轮验收：{sum(1 for _, ok, _ in _CHECK if ok)}/"
                        f"{len(_CHECK)} 通过"
                    )
                    print("=" * 70)
                    return 1
                if etype == "turn.completed":
                    break

            # ── 信封严格验证 ──
            env_ok = all(
                set(ev) >= _ENVELOPE_KEYS
                and ev.get("schema_version") == "1.0"
                and isinstance(ev.get("event_id"), str)
                and bool(ev.get("event_id"))
                and isinstance(ev.get("session_id"), str)
                and bool(ev.get("session_id"))
                and isinstance(ev.get("turn_id"), str)
                and bool(ev.get("turn_id"))
                and isinstance(ev.get("trace_id"), str)
                and bool(ev.get("trace_id"))
                and isinstance(ev.get("sequence"), int)
                and ev.get("sequence") > 0
                and isinstance(ev.get("payload"), dict)
                for ev in events
            )
            _check(
                f"第 {rnd} 轮信封严格（9 字段/版本/非空/sequence/字典）",
                env_ok,
                f"events={len(events)}",
            )
            all_event_ids.extend(ev.get("event_id", "") for ev in events)

            # 会话 / 轮次 / 追踪一致性
            sid = events[0].get("session_id")
            if session_id is None:
                session_id = sid
            sids_per_round.append(str(sid))
            _check(
                f"第 {rnd} 轮 session_id 一致",
                all(ev.get("session_id") == sid for ev in events),
            )
            tids = {ev.get("turn_id") for ev in events}
            trids = {ev.get("trace_id") for ev in events}
            _check(f"第 {rnd} 轮 turn_id 一致", len(tids) == 1, f"turns={tids}")
            _check(f"第 {rnd} 轮 trace_id 一致", len(trids) == 1)
            all_turn_ids.extend(tids)
            all_trace_ids.extend(trids)

            # sequence 连接级递增
            seqs = [ev.get("sequence") for ev in events]
            all_seqs.extend(seqs)
            _check(
                f"第 {rnd} 轮 sequence 递增",
                seqs == sorted(seqs) and len(set(seqs)) == len(seqs),
            )

            # ── 完整事件顺序 ──
            order = [ev.get("event_type") for ev in events]
            started_pos = [i for i, t in enumerate(order) if t == "module.started"]
            completed_pos = [i for i, t in enumerate(order) if t == "module.completed"]
            delta_pos = [i for i, t in enumerate(order) if t == "answer.delta"]
            artifact_pos = [i for i, t in enumerate(order) if t == "artifact.upsert"]

            started_mods = {
                ev["payload"].get("module")
                for ev in events
                if ev.get("event_type") == "module.started"
            }
            completed_mods = {
                ev["payload"].get("module")
                for ev in events
                if ev.get("event_type") == "module.completed"
            }
            per_mod_ok = bool(started_mods) and started_mods == completed_mods
            for mod in started_mods:
                s_idx = [
                    i
                    for i, ev in enumerate(events)
                    if ev.get("event_type") == "module.started"
                    and ev["payload"].get("module") == mod
                ]
                c_idx = [
                    i
                    for i, ev in enumerate(events)
                    if ev.get("event_type") == "module.completed"
                    and ev["payload"].get("module") == mod
                ]
                if not (s_idx and c_idx and max(s_idx) < min(c_idx)):
                    per_mod_ok = False

            ok_order = (
                order[0] == "turn.accepted"
                and order[-1] == "turn.completed"
                and len(started_pos) > 0
                and len(completed_pos) > 0
                and len(delta_pos) > 0
                and len(artifact_pos) > 0
                and max(started_pos) < min(completed_pos)
                and max(completed_pos) < min(delta_pos)
                and max(delta_pos) < min(artifact_pos)
                and max(artifact_pos) < len(order) - 1
            )
            _check(f"第 {rnd} 轮事件顺序（完整公式）", ok_order, "→".join(order))
            _check(
                f"第 {rnd} 轮 started/completed 模块集合一致",
                per_mod_ok,
                f"mods={sorted(started_mods)}",
            )

            # 终态 counts + answer
            final_payload = events[-1].get("payload", {})
            cc, ec = (
                final_payload.get("claims_count"),
                final_payload.get("evidence_count"),
            )
            ans = final_payload.get("answer", "")
            counts_ok = (
                isinstance(cc, int) and isinstance(ec, int) and cc >= 0 and ec >= 0
            )
            _check(
                f"第 {rnd} 轮终态 counts 类型与范围",
                counts_ok,
                f"claims={cc} evidence={ec}",
            )
            _check(f"第 {rnd} 轮 answer 非空", bool(ans), ans[:40])
            if rnd == 4:
                _check(
                    "第 4 轮终态 counts 非零",
                    bool(cc) and bool(ec),
                    f"claims={cc} evidence={ec}",
                )

            # 第 2 轮验证指代消解（'它'→金牌家居）
            if rnd == 2:
                _check("第 2 轮指代解析到金牌家居", "金牌家居" in ans, ans[:40])

        # ── 跨轮一致性 ──
        _check(
            "四轮 session 相同且非空",
            len(set(sids_per_round)) == 1 and bool(sids_per_round[0]),
            str(set(sids_per_round)),
        )
        _check(
            "跨轮 turn_id 各不相同（每轮独立轮次）",
            len(set(all_turn_ids)) == 4,
            f"turns={len(set(all_turn_ids))}",
        )
        _check(
            "跨轮 trace_id 各不相同",
            len(set(all_trace_ids)) == 4,
            f"traces={len(set(all_trace_ids))}",
        )
        _check(
            "全连接 event_id 不重复",
            len(set(all_event_ids)) == len(all_event_ids),
            f"events={len(all_event_ids)}",
        )

        # ── 连接级 sequence 全局严格递增 ──
        _check(
            "全连接 sequence 严格递增",
            all_seqs == sorted(all_seqs) and len(set(all_seqs)) == len(all_seqs),
            f"共 {len(all_seqs)} 个事件",
        )

        # ── REST 回读强验证 ──
        r = client.get(f"/api/v1/sessions/{session_id}")
        _check("REST 回读状态码 200", r.status_code == 200, f"code={r.status_code}")
        turns = r.json().get("data", {}).get("turns", [])
        _check(
            "REST 回读恰好 4 轮",
            len(turns) == 4,
            f"回读 {len(turns)} 轮 (session={session_id})",
        )
        ordered = sorted(turns, key=lambda t: t.get("turn_index", 0))
        _check(
            "四轮问题顺序与 QUESTIONS 一致",
            [t.get("question", "") for t in ordered] == QUESTIONS,
            str([t.get("question", "")[:12] for t in ordered]),
        )
        _check(
            "四轮 company_code 均为 603180.SH",
            all(t.get("company_code") == COMPANY_CODE for t in ordered),
            str({t.get("company_code") for t in ordered}),
        )
        rest_turn_ids = {t.get("turn_id") for t in ordered}
        _check(
            "REST turn ID 与 WS turn ID 集合一致",
            rest_turn_ids == set(all_turn_ids),
            f"rest={len(rest_turn_ids)} ws={len(set(all_turn_ids))}",
        )

    passed = sum(1 for _, ok, _ in _CHECK if ok)
    print("=" * 70)
    print(f"  WS 多轮验收：{passed}/{len(_CHECK)} 通过")
    print("=" * 70)
    return 0 if passed == len(_CHECK) else 1


if __name__ == "__main__":
    raise SystemExit(main())
