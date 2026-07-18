"""追踪 — V12 baseline (骨架).

trace_id 贯穿所有调用链。
"""

import uuid


def generate_trace_id() -> str:
    """生成 trace_id (UUID4)."""
    return str(uuid.uuid4())


def generate_request_id() -> str:
    """生成 request_id (UUID4)."""
    return str(uuid.uuid4())
