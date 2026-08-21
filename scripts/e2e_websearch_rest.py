"""REST 端到端验收 — anysearch 后端启用（8/19，合并前最后验证）.

会话链验证会5 触发点 + 语义/逻辑：
1. 康美上市日期（company_fact 触发点 → web_search flash → listing_date）
2. 康美最新公告（events 触发点 → web_search announcement → 公告证据）
3. 画像 profile（companies 端点 → web_search profile listing_date）

用法：python scripts/e2e_websearch_rest.py（连 127.0.0.1:8001）
"""

from __future__ import annotations

import json
import time
import urllib.request

BASE = "http://127.0.0.1:8001"
_CHECKS: list[tuple[str, bool]] = []


def _check(name: str, ok: bool, detail: str = "") -> None:
    _CHECKS.append((name, ok))
    suffix = f" - {detail}" if detail else ""
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{suffix}")


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


def _cleanup_session(session_id: str) -> dict:
    """只使用测试库凭据物理清理本次 E2E 会话。"""
    from acceptance_server import apply_test_env_overrides

    apply_test_env_overrides()
    from sqlalchemy import text

    from app.application.services.session_cleanup_service import SessionCleanupService
    from app.core.config import settings
    from app.domain.finance._engine_utils import get_engine

    if settings.MYSQL_DATABASE != settings.MYSQL_TEST_DATABASE:
        raise RuntimeError("REST E2E 清理进程未指向测试库")
    engine = get_engine(settings)
    with engine.connect() as conn:
        actual = str(conn.execute(text("SELECT DATABASE()")).scalar() or "")
    if actual.lower() != settings.MYSQL_TEST_DATABASE.lower():
        raise RuntimeError(f"REST E2E 清理目标库错误: {actual!r}")
    return SessionCleanupService(engine=engine).cleanup_session(session_id)


def main() -> int:
    _CHECKS.clear()
    session = f"ws_e2e_{int(time.time())}"
    print(f"=== session={session} ===")
    cleanup_ok = False
    try:
        # 1. 对话：康美上市日期（company_fact 触发点）
        print("\n--- 1. 康美上市日期 ---")
        r = _chat(session, "康美药业什么时候上市的")
        d = r.get("data") or {}
        evs = d.get("evidence") or []
        ws_ev = [e for e in evs if e.get("source_type") == "web_search"]
        print("intent:", d.get("intent"))
        print("answer:", (d.get("answer") or "")[:200])
        _check("上市日期路由 company_fact", d.get("intent") == "company_fact")
        _check("上市日期回答非空", bool(d.get("answer")))
        _check("上市日期含联网证据", bool(ws_ev), f"web_search={len(ws_ev)}")

        # 2. 对话：康美最新公告（events 触发点）
        print("\n--- 2. 康美最新公告 ---")
        r2 = _chat(session, "康美药业 600518.SH 的公告")
        d2 = r2.get("data") or {}
        evs2 = d2.get("evidence") or []
        ws_ev2 = [e for e in evs2 if e.get("source_type") == "web_search"]
        print("intent:", d2.get("intent"))
        print("answer:", (d2.get("answer") or "")[:200])
        _check(
            "公告未误入实体/关系澄清",
            d2.get("intent") not in {"entity_error", "relation_clarify", "ambiguous"},
            str(d2.get("intent")),
        )
        _check("公告回答非空", bool(d2.get("answer")))
        _check("公告含联网证据", bool(ws_ev2), f"web_search={len(ws_ev2)}")

        # 3. 画像 profile（companies 触发点）
        print("\n--- 3. 画像 profile 康美 ---")
        prof = _get("/api/v1/companies/600518.SH")
        p = prof.get("data") or {}
        print("listing_date:", p.get("listing_date"))
        ws_warn = [
            w
            for w in (p.get("warnings") or [])
            if "WEB_SEARCH" in str(w.get("code", ""))
        ]
        print("web_search warnings:", len(ws_warn))
        _check("画像回填上市日期", bool(p.get("listing_date")))
    except Exception as exc:  # noqa: BLE001 - E2E 汇总后仍需执行清理
        _check("REST E2E 执行无异常", False, repr(exc))
    finally:
        try:
            stats = _cleanup_session(session)
            cleanup_ok = bool(stats.get("session_deleted"))
            _check("测试会话物理清理", cleanup_ok, str(stats))
        except Exception as exc:  # noqa: BLE001 - 清理失败必须反映为退出失败
            _check("测试会话物理清理", False, repr(exc))

    passed = bool(_CHECKS) and all(ok for _, ok in _CHECKS) and cleanup_ok
    print(f"\n=== 端到端{'通过' if passed else '失败'} ===")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
