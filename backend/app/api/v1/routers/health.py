"""健康检查路由 — V12 baseline.

新增 /healthz 和 /readyz 端点。
V12 full profile: /readyz 报告外部服务状态。
"""

import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter

from app.api.v1.schemas.common import ApiMeta, V12Response
from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz():
    """V12 健康检查 — 进程存活探针（不依赖外部服务）."""
    trace_id = str(uuid.uuid4())
    return V12Response(
        data={
            "status": "healthy",
            "version": "0.2.0",
            "profile": settings.TRUTHNET_PROFILE,
        },
        meta=ApiMeta(
            request_id=trace_id,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
        ),
        warnings=[],
    )


def _check_mysql() -> dict:
    """检测 MySQL 连接状态."""
    if settings.SQL_BACKEND != "mysql":
        return {
            "status": "not_configured",
            "reason": f"SQL_BACKEND={settings.SQL_BACKEND}",
        }

    if not settings.MYSQL_PASSWORD:
        return {"status": "not_configured", "reason": "MYSQL_PASSWORD not set"}

    try:
        import socket

        sock = socket.create_connection(
            (settings.MYSQL_HOST, settings.MYSQL_PORT), timeout=3
        )
        sock.close()
        return {
            "status": "reachable",
            "host": settings.MYSQL_HOST,
            "port": settings.MYSQL_PORT,
        }
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        return {"status": "unreachable", "reason": str(e)[:80]}
    except Exception as e:
        return {"status": "error", "reason": str(e)[:80]}


def _check_neo4j() -> dict:
    """检测 Neo4j 连接状态."""
    if settings.GRAPH_BACKEND != "neo4j":
        return {
            "status": "not_configured",
            "reason": f"GRAPH_BACKEND={settings.GRAPH_BACKEND}",
        }

    if not settings.NEO4J_PASSWORD:
        return {"status": "not_configured", "reason": "NEO4J_PASSWORD not set"}

    # Parse URI for host:port
    host = "localhost"
    port = 7687
    uri = settings.NEO4J_URI
    if "bolt://" in uri:
        netloc = uri.replace("bolt://", "").split("@")[-1]
        if ":" in netloc:
            host = netloc.split(":")[0]
            port = int(netloc.split(":")[1])

    try:
        import socket

        sock = socket.create_connection((host, port), timeout=3)
        sock.close()
        return {"status": "reachable", "host": host, "port": port}
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        return {"status": "unreachable", "reason": str(e)[:80]}
    except Exception as e:
        return {"status": "error", "reason": str(e)[:80]}


def _check_chroma() -> dict:
    """检测 ChromaDB 状态."""
    from pathlib import Path

    persist_dir = settings.CHROMA_PERSIST_DIR
    dir_path = Path(settings.CHROMA_PERSIST_DIR)
    if not dir_path.is_absolute():
        dir_path = Path.cwd() / persist_dir

    if not dir_path.exists():
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return {"status": "error", "reason": f"cannot create dir: {e}"}

    writable = os.access(str(dir_path), os.W_OK)
    if writable:
        return {"status": "ok", "persist_dir": str(dir_path)}
    else:
        return {"status": "error", "reason": "persist_dir not writable"}


def _check_llm() -> dict:
    """检测 LLM 状态."""
    backend = settings.LLM_BACKEND
    if backend == "mock":
        return {"status": "mock", "reason": "using MockLLMProvider"}
    elif backend == "deepseek":
        if not settings.DEEPSEEK_API_KEY:
            return {"status": "not_configured", "reason": "DEEPSEEK_API_KEY not set"}
        return {"status": "configured", "provider": "deepseek"}
    elif backend == "qwen":
        if not settings.QWEN_API_KEY:
            return {"status": "not_configured", "reason": "QWEN_API_KEY not set"}
        return {"status": "configured", "provider": "qwen"}
    return {"status": "unknown", "reason": f"unknown backend: {backend}"}


@router.get("/readyz")
async def readyz():
    """V12 就绪检查 — 依赖服务探针.

    lite profile: 始终返回 ready（不因 MySQL/Neo4j 缺失而失败）。
    full profile: 检查各外部服务的 TCP 可达性。
    不暴露密码、完整 DSN。
    """
    trace_id = str(uuid.uuid4())
    profile = settings.TRUTHNET_PROFILE

    if profile == "full":
        checks = {
            "mysql": _check_mysql(),
            "neo4j": _check_neo4j(),
            "chroma": _check_chroma(),
            "llm": _check_llm(),
        }
        # Determine overall status
        statuses = [c["status"] for c in checks.values()]
        if all(
            s == "ok" or s == "reachable" or s == "configured" or s == "mock"
            for s in statuses
        ):
            overall = "ready"
        elif any(s == "error" or s == "unreachable" for s in statuses):
            overall = "degraded"
        else:
            overall = "not_ready"
    else:
        checks = {
            "sql_backend": {"status": "ok", "backend": settings.SQL_BACKEND},
            "graph_backend": {"status": "ok", "backend": settings.GRAPH_BACKEND},
            "vector_backend": {"status": "ok", "backend": settings.VECTOR_BACKEND},
            "llm_backend": {"status": "ok", "backend": settings.LLM_BACKEND},
        }
        overall = "ready"

    warnings = []
    if profile == "full":
        for name, check in checks.items():
            if check["status"] in ("unreachable", "error", "not_configured"):
                warnings.append(
                    {
                        "code": f"{name.upper()}_UNAVAILABLE",
                        "message": f"{name}: {check.get('reason', check['status'])}",
                        "module": name,
                        "recoverable": True,
                    }
                )

    return V12Response(
        data={
            "status": overall,
            "profile": profile,
            "checks": checks,
        },
        meta=ApiMeta(
            request_id=trace_id,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
        ),
        warnings=warnings,
    )
