"""TruthNet 评测 API 客户端 — Phase D 真实化."""

import time
from typing import Any

import requests

BASE_URL = "http://127.0.0.1:8000"
REQUEST_TIMEOUT = 30


def _safe_get(url: str, timeout: int = REQUEST_TIMEOUT) -> dict[str, Any]:
    """安全 GET 请求，超时/异常时返回错误信息."""
    t0 = time.time()
    try:
        resp = requests.get(url, timeout=timeout)
        elapsed = int((time.time() - t0) * 1000)
        return {
            "data": resp.json()
            if resp.headers.get("content-type", "").startswith("application/json")
            else {},
            "http_status": resp.status_code,
            "duration_ms": elapsed,
            "error": None,
        }
    except requests.exceptions.Timeout:
        elapsed = int((time.time() - t0) * 1000)
        return {
            "data": {},
            "http_status": 504,
            "duration_ms": elapsed,
            "error": "TIMEOUT",
        }
    except requests.exceptions.ConnectionError:
        elapsed = int((time.time() - t0) * 1000)
        return {
            "data": {},
            "http_status": 503,
            "duration_ms": elapsed,
            "error": "CONNECTION_REFUSED",
        }
    except Exception as e:
        elapsed = int((time.time() - t0) * 1000)
        return {"data": {}, "http_status": 500, "duration_ms": elapsed, "error": str(e)}


def _safe_post(
    url: str, json_data: dict, timeout: int = REQUEST_TIMEOUT
) -> dict[str, Any]:
    """安全 POST 请求."""
    t0 = time.time()
    try:
        resp = requests.post(url, json=json_data, timeout=timeout)
        elapsed = int((time.time() - t0) * 1000)
        body = (
            resp.json()
            if resp.headers.get("content-type", "").startswith("application/json")
            else {}
        )
        return {
            "data": body.get("data", body),
            "meta": body.get("meta", {}),
            "warnings": body.get("warnings", []),
            "http_status": resp.status_code,
            "duration_ms": elapsed,
        }
    except requests.exceptions.Timeout:
        elapsed = int((time.time() - t0) * 1000)
        return {
            "data": {},
            "http_status": 504,
            "duration_ms": elapsed,
            "error": "TIMEOUT",
        }
    except requests.exceptions.ConnectionError:
        elapsed = int((time.time() - t0) * 1000)
        return {
            "data": {},
            "http_status": 503,
            "duration_ms": elapsed,
            "error": "CONNECTION_REFUSED",
        }
    except Exception as e:
        elapsed = int((time.time() - t0) * 1000)
        return {"data": {}, "http_status": 500, "duration_ms": elapsed, "error": str(e)}


def call_chat(question: str, session_id: str = "eval") -> dict[str, Any]:
    """调对话接口，获取系统回答."""
    result = _safe_post(
        f"{BASE_URL}/api/v1/chat", {"question": question, "session_id": session_id}
    )
    data = result.get("data", {})
    return {
        "question": question,
        "answer": data.get("answer", data.get("final_response", {}).get("answer", ""))
        if isinstance(data, dict)
        else "",
        "risk_level": data.get("risk_level") if isinstance(data, dict) else None,
        "claims": data.get("claims", []) if isinstance(data, dict) else [],
        "evidence": data.get("evidence", []) if isinstance(data, dict) else [],
        "warnings": result.get("warnings", []),
        "http_status": result["http_status"],
        "duration_ms": result["duration_ms"],
        "error": result.get("error"),
    }


def call_finance(company_code: str) -> dict[str, Any]:
    """调财务分析接口."""
    return _safe_get(f"{BASE_URL}/api/v1/companies/{company_code}/finance")


def call_risk(company_code: str) -> dict[str, Any]:
    """调风险评分接口."""
    return _safe_get(f"{BASE_URL}/api/v1/companies/{company_code}/risk")


def call_company_search(query: str) -> dict[str, Any]:
    """调公司搜索接口."""
    return _safe_get(f"{BASE_URL}/api/v1/companies?query={query}")


def api_available() -> bool:
    """检查后端是否可连接."""
    try:
        # 先试 readyz，再试实际 API 端点
        resp = requests.get(f"{BASE_URL}/readyz", timeout=5)
        if resp.status_code in (200, 503, 404):
            # 404 也可能是端点未实现但后端在运行，再试搜索端点
            r2 = requests.get(f"{BASE_URL}/api/v1/companies?query=test", timeout=5)
            return r2.status_code == 200
        return resp.status_code in (200, 503)
    except Exception:
        return False


# ── WebSocket 评测（Phase D 联调窗口 D5-D8）─────────────────


def ws_available() -> bool:
    """检查 WS 端点是否可达."""
    try:
        resp = requests.get(f"{BASE_URL}/readyz", timeout=3)
        return resp.status_code in (200, 503, 404)
    except Exception:
        return False


def call_chat_ws(question: str, session_id: str = "eval_ws") -> dict[str, Any]:
    """通过 WebSocket 调对话接口，收集流式事件。

    连接 /api/v1/chat/ws，发送 chat.query，收集所有事件直到
    turn.completed / turn.failed，返回聚合结果。

    Returns:
        {
            "answer": "...",                  # 拼接所有 answer.delta
            "events": [...],                  # 完整事件列表
            "time_to_first_text_ms": 1234,    # 首块文本延迟
            "total_duration_ms": 5678,        # 总延迟
            "module_sequence": [...],         # 模块执行顺序
            "http_status": 200,
            "error": "...",                   # None if success
        }
    """
    import asyncio

    async def _ws_session():
        import websockets

        t0 = time.time()
        first_text_at = None
        answer_parts: list[str] = []
        events: list[dict] = []
        module_seq: list[str] = []
        error = None

        try:
            async with websockets.connect(
                "ws://127.0.0.1:8000/api/v1/chat/ws",
                open_timeout=10,
                close_timeout=5,
            ) as ws:
                # 发送 query
                import json as _json

                await ws.send(
                    _json.dumps(
                        {
                            "event_type": "chat.query",
                            "payload": {"text": question, "session_id": session_id},
                        }
                    )
                )

                # 收集事件
                async for raw in ws:
                    try:
                        evt = _json.loads(raw)
                    except _json.JSONDecodeError:
                        continue
                    evt_type = evt.get("event_type", "")
                    events.append(evt)

                    if evt_type == "answer.delta":
                        if first_text_at is None:
                            first_text_at = time.time()
                        answer_parts.append(evt.get("payload", {}).get("delta", ""))

                    if evt_type == "module.started":
                        module_seq.append(evt.get("payload", {}).get("module", "?"))

                    if evt_type in ("turn.completed", "turn.failed"):
                        break

        except Exception as e:
            error = str(e)

        elapsed = int((time.time() - t0) * 1000)
        ttf = int((first_text_at - t0) * 1000) if first_text_at else None

        return {
            "answer": "".join(answer_parts),
            "events": events,
            "time_to_first_text_ms": ttf,
            "total_duration_ms": elapsed,
            "module_sequence": module_seq,
            "http_status": 200 if not error else 503,
            "error": error,
        }

    try:
        return asyncio.run(_ws_session())
    except Exception as e:
        return {
            "answer": "",
            "events": [],
            "time_to_first_text_ms": None,
            "total_duration_ms": 0,
            "module_sequence": [],
            "http_status": 503,
            "error": str(e),
        }


def call_format_check(question: str, session_id: str = "eval_fmt") -> dict[str, Any]:
    """仅验证格式合规性的轻量调用（使用 REST）.

    对所有有公司名的题调用此函数，检查系统返回的 JSON 是否符合预期 schema。
    不评估回答内容的正确性。

    Returns:
        {"valid_json": True/False, "has_claims": True/False, "fields_ok": [...], ...}
    """
    result = call_chat(question, session_id)
    if result.get("error"):
        return {"valid_json": False, "error": result["error"]}

    checks = {
        "has_answer": bool(result.get("answer")),
        "http_200": result.get("http_status") == 200,
        "has_claims_or_warnings": bool(result.get("claims") or result.get("warnings")),
    }
    return {
        "valid_json": checks["http_200"],
        "checks": checks,
        "duration_ms": result.get("duration_ms", 0),
    }
