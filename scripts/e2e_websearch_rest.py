"""REST 端到端验收 — anysearch 后端启用（8/19，合并前最后验证）.

会话链验证会5 触发点 + 语义/逻辑：
1. 康美上市日期（company_fact 触发点 → web_search flash → listing_date）
2. 康美最新公告（events 触发点 → web_search announcement → 公告证据）
3. 画像 profile（companies 端点 → web_search profile listing_date）

用法：python scripts/e2e_websearch_rest.py（连 127.0.0.1:8001）
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8001"


def _post(path: str, body: dict, timeout: int = 120) -> dict:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(path: str, timeout: int = 60) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _chat(session: str, question: str) -> dict:
    return _post("/api/v1/chat", {"session_id": session, "question": question})


def main() -> int:
    session = f"ws_e2e_{int(time.time())}"
    print(f"=== session={session} ===")

    # 1. 对话：康美上市日期（company_fact 触发点）
    print("\n--- 1. 康美上市日期 ---")
    r = _chat(session, "康美药业什么时候上市的")
    d = r.get("data") or {}
    print("intent:", d.get("intent"))
    print("answer:", (d.get("answer") or "")[:200])
    evs = d.get("evidence") or []
    ws_ev = [e for e in evs if e.get("source_type") == "web_search"]
    print("evidence 总数:", len(evs), "| web_search:", len(ws_ev))
    for e in ws_ev[:2]:
        print("  -", e.get("field_path"), "|", str(e.get("value"))[:80])

    # 2. 对话：康美最新公告（events 触发点）
    print("\n--- 2. 康美最新公告 ---")
    r2 = _chat(session, "康美药业 600518.SH 的公告")
    d2 = r2.get("data") or {}
    print("intent:", d2.get("intent"))
    print("answer:", (d2.get("answer") or "")[:200])
    evs2 = d2.get("evidence") or []
    ws_ev2 = [e for e in evs2 if e.get("source_type") == "web_search"]
    print("evidence 总数:", len(evs2), "| web_search:", len(ws_ev2))
    for e in ws_ev2[:2]:
        print("  -", e.get("field_path"), "|", str(e.get("value"))[:80])

    # 3. 画像 profile（companies 触发点）
    print("\n--- 3. 画像 profile 康美 ---")
    try:
        prof = _get("/api/v1/companies/600518.SH")
        p = prof.get("data") or {}
        print("listing_date:", p.get("listing_date"))
        ws_warn = [w for w in (p.get("warnings") or []) if "WEB_SEARCH" in str(w.get("code", ""))]
        print("web_search warnings:", len(ws_warn))
    except Exception as exc:  # noqa: BLE001
        print("画像端点异常:", exc)

    print("\n=== 端到端完成 ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
