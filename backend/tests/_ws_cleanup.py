"""WS 集成测试会话清理 helper（对齐审计 P1-4：并发安全）.

策略：每个测试记录自己从 WS 事件信封获得的 session_id，
teardown 时只删除明确归属于本测试的 ID——不使用"全库差集"
（并发智能体/用户创建的会话不会误删）。

全局 session 钩子（conftest.py）只检查并告警，不执行删除。
"""

from fastapi.testclient import TestClient

from app.main import app


def ws_envelope_sids(events: list[dict]) -> set[str]:
    """从 WS 事件信封提取 session_id（事件归属本测试连接）。"""
    sids = {e.get("session_id") for e in events if e.get("session_id")}
    return {s for s in sids if s}


def cleanup_ws_sids(events: list[dict]) -> int:
    """删除事件信封中出现的会话（幂等），返回删除数。仅 mysql 时生效。"""
    from app.core.config import settings

    if settings.SQL_BACKEND != "mysql":
        return 0
    sids = ws_envelope_sids(events)
    if not sids:
        return 0
    client = TestClient(app)
    deleted = 0
    for sid in sorted(sids):
        resp = client.delete(f"/api/v1/sessions/{sid}")
        if resp.status_code == 200:
            deleted += 1
        elif resp.status_code != 404:
            print(f"WS test session cleanup failed: {sid} -> {resp.status_code}")
    return deleted
