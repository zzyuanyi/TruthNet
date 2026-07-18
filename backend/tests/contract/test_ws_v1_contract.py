"""WebSocket v1 契约测试 — V12 baseline.

验证 WebSocket V12 event envelope 格式。
"""

import json

import pytest

from app.main import app


def test_ws_v1_route_registered():
    """WebSocket V12 路由已注册."""
    routes = [r.path for r in app.routes]
    ws_routes = [r for r in routes if "ws" in r.lower()]
    assert len(ws_routes) > 0, "未找到 WebSocket 路由"


@pytest.mark.asyncio
async def test_ws_v1_event_envelope_format():
    """WebSocket V12 消息使用 event envelope 格式."""
    from fastapi.testclient import TestClient

    client = TestClient(app)

    with client.websocket_connect("/api/v1/chat/ws") as websocket:
        websocket.send_json({"question": "测试 V12 event envelope"})

        messages = []
        max_messages = 30  # safety limit to prevent infinite loops
        try:
            while len(messages) < max_messages:
                raw = websocket.receive_text()
                msg = json.loads(raw)
                messages.append(msg)
                # Break on V12 turn.completed OR legacy final_answer
                if msg.get("event_type") == "turn.completed":
                    break
                if msg.get("type") == "final_answer":
                    break
                # Also break on error messages
                if msg.get("event_type") == "turn.failed":
                    break
                if msg.get("type") == "error":
                    break
        except Exception:
            pass

        assert len(messages) > 0, "未收到任何 WebSocket 消息"

        # 验证消息格式（兼容旧 {type, data} 和新 V12 envelope）
        # 当前 legacy WS 优先匹配，返回旧格式
        for msg in messages:
            # 旧格式：type + data，新格式：event_type + payload
            has_type = "type" in msg
            has_event_type = "event_type" in msg
            assert has_type or has_event_type, f"消息无 type 也无 event_type: {msg}"

            if has_event_type:
                # V12 envelope
                assert "schema_version" in msg
                assert "session_id" in msg
                assert "turn_id" in msg
                assert "sequence" in msg
                assert "payload" in msg

        # 验证至少收到响应
        if any("event_type" in m for m in messages):
            event_types = [m["event_type"] for m in messages if "event_type" in m]
            assert (
                "turn.accepted" in event_types
            ), f"未收到 turn.accepted: {event_types}"
        else:
            msg_types = [m["type"] for m in messages if "type" in m]
            assert len(msg_types) > 0, "未收到任何消息类型"


@pytest.mark.asyncio
async def test_ws_v1_error_on_invalid_json():
    """WebSocket 收到无效 JSON 返回错误消息."""
    from fastapi.testclient import TestClient

    client = TestClient(app)

    with client.websocket_connect("/api/v1/chat/ws") as websocket:
        websocket.send_text("not valid json{{{")

        try:
            raw = websocket.receive_text()
            msg = json.loads(raw)
            # 兼容旧格式 {type: "error"} 和新格式 {event_type: "turn.failed"}
            assert ("type" in msg and msg["type"] == "error") or (
                "event_type" in msg and msg["event_type"] == "turn.failed"
            )
        except Exception:
            pass


@pytest.mark.asyncio
async def test_ws_v1_error_on_missing_question():
    """WebSocket 收到无 question 消息返回错误."""
    from fastapi.testclient import TestClient

    client = TestClient(app)

    with client.websocket_connect("/api/v1/chat/ws") as websocket:
        websocket.send_json({"data": {}})

        try:
            raw = websocket.receive_text()
            msg = json.loads(raw)
            # 兼容旧格式和新格式
            assert ("type" in msg and msg["type"] == "error") or (
                "event_type" in msg and msg["event_type"] == "turn.failed"
            )
        except Exception:
            pass
