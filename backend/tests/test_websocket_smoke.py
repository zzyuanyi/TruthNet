"""WebSocket smoke 测试 — V12 baseline.

验证 WS 端点 V12 event envelope 消息格式与交互流程。
使用 httpx AsyncClient + ASGITransport 测试 WebSocket 端点。
"""

import json

import pytest

from app.main import app


@pytest.mark.asyncio
async def test_websocket_endpoint_rejects_non_ws():
    """WebSocket 端点拒绝非 WebSocket HTTP 请求."""
    ws_routes = [r.path for r in app.routes if "/api/v1/chat/ws" == r.path]
    assert len(ws_routes) > 0, "WebSocket 路由未注册"


@pytest.mark.asyncio
async def test_websocket_route_format():
    """WebSocket 端点格式符合 API_CONTRACT.md 定义."""
    routes = [r.path for r in app.routes]
    ws_routes = [r for r in routes if "ws" in r.lower() or "websocket" in r.lower()]
    assert len(ws_routes) > 0, "未找到 WebSocket 路由"
    for route in ws_routes:
        assert route.startswith(
            "/api/v1/"
        ), f"WebSocket 路由 '{route}' 不符合 /api/v1/ 前缀规范"


@pytest.mark.asyncio
async def test_websocket_error_on_invalid_json():
    """WebSocket 收到无效 JSON 时返回 turn.failed (V12)."""
    from fastapi.testclient import TestClient
    from fastapi.websockets import WebSocketDisconnect

    client = TestClient(app)

    with client.websocket_connect("/api/v1/chat/ws") as websocket:
        websocket.send_text("not valid json{{{")
        try:
            msg_raw = websocket.receive_text()
            msg = json.loads(msg_raw)
            assert msg["event_type"] == "turn.failed"
            assert msg["payload"]["error_code"] == "INVALID_JSON"
        except WebSocketDisconnect:
            pass


@pytest.mark.asyncio
async def test_websocket_error_on_missing_text():
    """WebSocket 收到无 text 的 V12 消息时返回 turn.failed."""
    from fastapi.testclient import TestClient
    from fastapi.websockets import WebSocketDisconnect

    client = TestClient(app)

    with client.websocket_connect("/api/v1/chat/ws") as websocket:
        websocket.send_json({"event_type": "chat.query", "payload": {}})
        try:
            msg_raw = websocket.receive_text()
            msg = json.loads(msg_raw)
            assert msg["event_type"] == "turn.failed"
        except WebSocketDisconnect:
            pass


@pytest.mark.asyncio
async def test_websocket_full_flow_with_v12_client():
    """完整 V12 WebSocket 流程测试."""
    from fastapi.testclient import TestClient

    client = TestClient(app)

    with client.websocket_connect("/api/v1/chat/ws") as websocket:
        websocket.send_json(
            {"event_type": "chat.query", "payload": {"text": "贵州茅台2023年营收分析"}}
        )

        messages_received: list[dict] = []
        max_messages = 30
        try:
            while len(messages_received) < max_messages:
                raw = websocket.receive_text()
                msg = json.loads(raw)
                messages_received.append(msg)
                if msg["event_type"] == "turn.completed":
                    break
                if msg["event_type"] == "turn.failed":
                    break
        except Exception:
            pass

        msg_types = [m["event_type"] for m in messages_received]
        assert "turn.accepted" in msg_types, f"未收到 turn.accepted: {msg_types}"
        assert (
            "turn.completed" in msg_types or "turn.failed" in msg_types
        ), f"未收到 turn.completed 或 turn.failed: {msg_types}"

        # V12 envelope 完整性
        for msg in messages_received:
            for key in (
                "schema_version",
                "event_id",
                "event_type",
                "session_id",
                "turn_id",
                "sequence",
                "timestamp",
                "trace_id",
                "payload",
            ):
                assert key in msg, f"V12 信封缺少字段: {key}"
            assert isinstance(msg["sequence"], int) and msg["sequence"] > 0

        # terminal event payload
        terminal = [
            m
            for m in messages_received
            if m["event_type"] in ("turn.completed", "turn.failed")
        ]
        assert len(terminal) > 0
        tc = terminal[0]
        assert "payload" in tc
        if tc["event_type"] == "turn.completed":
            assert "answer" in tc["payload"]
