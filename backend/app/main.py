"""TruthNet FastAPI 应用入口 · V12 baseline (Phase C v2).

路由注册：
  - /health                              → 旧健康检查（deprecated，保留兼容）
  - /api/v1/healthz                      → V12 存活检查
  - /api/v1/readyz                       → V12 就绪检查
  - /api/v1/chat                         → V12 REST 对话
  - /api/v1/chat/ws                      → V12 WebSocket 对话
  - /api/v1/companies                    → V12 公司搜索与画像
  - /api/v1/companies/{code}/equity      → V12 股权穿透
  - /api/v1/companies/{code}/finance     → V12 财务分析 (§11.10)
  - /api/v1/companies/{code}/events      → V12 舆情事件 (§11.11)
  - /api/v1/companies/{code}/risk        → V12 综合风险 (§11.12)
  - /api/v1/companies/{code}/benchmarks  → V12 行业对标 (§11.13)
  - /api/v1/comparisons                  → V12 跨公司对比 (§11.14)
  - /api/v1/sessions                     → V12 会话管理
"""

import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.exception_handlers import (
    general_exception_handler,
    http_exception_handler,
    not_found_handler,
    validation_exception_handler,
)
from app.api.v1.routers import benchmarks as benchmarks_v1
from app.api.v1.routers import chat as chat_v1
from app.api.v1.routers import companies as companies_v1
from app.api.v1.routers import comparisons as comparisons_v1
from app.api.v1.routers import rules as rules_v1
from app.api.v1.routers import equity as equity_v1
from app.api.v1.routers import events as events_v1
from app.api.v1.routers import finance as finance_v1
from app.api.v1.routers import health as health_v1
from app.api.v1.routers import provenance as provenance_v1
from app.api.v1.routers import reports as reports_v1
from app.api.v1.routers import risk as risk_v1
from app.api.v1.routers import sessions as sessions_v1
from app.core.config import settings
from app.schemas.common import HealthResponse, UnifiedResponse

logger = logging.getLogger(__name__)

# 加载 .env
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(env_path)


def _validate_release_mode() -> None:
    """v3.3.1 §9.1 + 8/16 语义裁决启用（队长拍板，演示/答辩环境）：
    - off：确定性路径（生产默认，零 LLM）；
    - suggest：演示/答辩环境启用——mentionness 的 non_company_context
      判定生效（非公司词不再报"疑似公司"），selector 输出 LLM 推荐
      （不自动绑定身份，用户确认兜底 fail-closed）；
    - auto：自动绑定身份，仅限离线 runner 显式构造
      CompanySemanticSelector(mode=...) 运行，生产/演示一律拒绝启动。

    最终续审 §6 C3：Interpreter 同步调用同样会增加在线延迟（shadow 不
    改变结果），生产只允许 off 或 fallback（5s fail-closed），shadow
    仅限离线 runner。
    """
    from app.core.config import settings as _settings

    if _settings.ENTITY_SEMANTIC_SELECTION_MODE not in ("off", "suggest"):
        raise RuntimeError(
            f"ENTITY_SEMANTIC_SELECTION_MODE="
            f"{_settings.ENTITY_SEMANTIC_SELECTION_MODE} 仅限离线评测；"
            "生产/演示允许 off（确定性）或 suggest（LLM 建议不自动绑定）；"
            "auto 自动绑定身份请离线 runner 显式构造 selector"
        )
    if _settings.ENTITY_QUERY_INTERPRETER_MODE not in ("off", "fallback"):
        raise RuntimeError(
            f"ENTITY_QUERY_INTERPRETER_MODE="
            f"{_settings.ENTITY_QUERY_INTERPRETER_MODE} 仅限离线评测"
            "（shadow 同步调用不改变结果，不应在线开启）；"
            "生产允许 off（零调用）或 fallback（5s fail-closed）"
        )


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """应用生命周期.

    启动：发布模式校验（§9.1）；恢复遗留 running 报告任务（Phase D #8，
    重启后不永久卡死）；注册 WS janitor 周期清理（缓冲 TTL + 空闲会话回收）。
    关闭：停止 janitor task（不阻塞）。
    """
    import asyncio

    _validate_release_mode()
    # 最终续审 §6 C3：实体链路配置启动观测（验收必须能核对模式）
    from app.core.config import settings as _settings

    logger.info(
        "entity config: entity_selector_mode=%s "
        "entity_query_interpreter_mode=%s "
        "entity_query_interpreter_budget_seconds=%s llm_backend=%s",
        _settings.ENTITY_SEMANTIC_SELECTION_MODE,
        _settings.ENTITY_QUERY_INTERPRETER_MODE,
        _settings.ENTITY_QUERY_INTERPRETER_BUDGET_SECONDS,
        _settings.LLM_BACKEND,
    )

    try:
        from app.application.services.report_service import recover_stale_running_jobs

        n = recover_stale_running_jobs()
        if n:
            logger.info("启动时恢复 %d 个遗留 running 报告任务", n)
    except Exception:  # noqa: BLE001 — 恢复失败不阻塞启动
        logger.warning("启动时报告任务恢复失败", exc_info=True)

    # 启动预热（真流式首块优化）：预编译 graph + 预热存储连接，
    # readyz 在预热完成后才返回 ready（避免首请求承担冷启动 4s+）
    try:
        from app.core.startup import prewarm_runtime

        await asyncio.to_thread(prewarm_runtime)
        logger.info("启动预热完成（graph/MySQL/Neo4j/Chroma）")
    except Exception:  # noqa: BLE001 — 预热失败不阻塞启动（首请求承担冷启动）
        logger.warning("启动预热失败（不阻塞启动）", exc_info=True)

    # WS janitor：周期清理过期缓冲事件 + 空闲超时会话（防止内存无界增长）
    from app.application.services.ws_session_manager import session_manager

    janitor_stop = asyncio.Event()

    async def _ws_janitor_loop() -> None:
        while not janitor_stop.is_set():
            try:
                await asyncio.wait_for(
                    janitor_stop.wait(),
                    timeout=settings.WS_JANITOR_INTERVAL_SECONDS,
                )
            except asyncio.TimeoutError:
                pass
            if janitor_stop.is_set():
                break
            try:
                stats = session_manager.janitor()
                if stats["expired_sessions"] or stats["expired_events"]:
                    logger.info("WS janitor: %s", stats)
            except Exception:  # noqa: BLE001 — 单轮清理失败不终止循环
                logger.warning("WS janitor 执行失败", exc_info=True)

    janitor_task = asyncio.create_task(_ws_janitor_loop())
    try:
        yield
    finally:
        janitor_stop.set()
        try:
            await janitor_task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        # 显式关闭 Neo4j 共享 driver（避免依赖析构关闭，解释器退出 warning）
        try:
            from app.infrastructure.graph.neo4j.equity_graph import (
                Neo4jEquityGraph,
            )

            Neo4jEquityGraph.close_shared_driver()
        except Exception:  # noqa: BLE001 — 关闭失败不阻塞退出
            logger.warning("Neo4j 共享 driver 关闭失败", exc_info=True)


app = FastAPI(
    title="TruthNet API",
    description="织网鉴真 — 财报反欺诈智能问答系统 (V12 baseline)",
    version="0.2.0",
    lifespan=_lifespan,
)

# CORS（开发阶段允许所有来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== V12 异常处理器 =====
app.add_exception_handler(Exception, general_exception_handler)
app.add_exception_handler(404, not_found_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)

# ===== 兼容路由 =====


@app.get("/health", response_model=UnifiedResponse[HealthResponse])
async def health_check():
    """健康检查接口（deprecated — 请使用 /api/v1/healthz）。

    保留兼容，不立即删除。
    """
    return UnifiedResponse(
        code=0,
        data=HealthResponse(
            status="healthy",
            version=app.version,
        ),
        message="ok",
        trace_id=str(uuid.uuid4()),
    )


# ── V12 路由注册（每个 URL 只注册一次）──
app.include_router(health_v1.router, prefix="/api/v1")
app.include_router(companies_v1.router, prefix="/api/v1")
app.include_router(equity_v1.router, prefix="/api/v1")
app.include_router(finance_v1.router, prefix="/api/v1")
app.include_router(events_v1.router, prefix="/api/v1")
app.include_router(risk_v1.router, prefix="/api/v1")
app.include_router(benchmarks_v1.router, prefix="/api/v1")
app.include_router(provenance_v1.router, prefix="/api/v1")
app.include_router(comparisons_v1.router, prefix="/api/v1")
app.include_router(rules_v1.router, prefix="/api/v1")
app.include_router(chat_v1.router, prefix="/api/v1")
app.include_router(reports_v1.router, prefix="/api/v1")
app.include_router(sessions_v1.router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=settings.DEBUG,
    )
