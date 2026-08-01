"""TruthNet FastAPI 应用入口 · V12 baseline (审计修复版).

路由注册（去重后）：
  - /health           → 旧健康检查（deprecated，保留兼容）
  - /api/v1/healthz   → V12 存活检查
  - /api/v1/readyz    → V12 就绪检查
  - /api/v1/chat      → V12 REST 对话（唯一注册，进入 Agent graph）
  - /api/v1/chat/ws   → V12 WebSocket 对话（进入 Agent graph）
  - /api/v1/companies → V12 公司搜索与画像
  - /api/v1/companies/{code}/equity → V12 股权穿透
  - /api/v1/sessions → V12 会话列表/创建/详情

变更（审计修复 P0-1）：
  - 移除 POST /api/v1/chat 旧 legacy 注册（硬编码贵州茅台 mock）
  - POST /api/v1/chat 唯一注册 → chat_v1 router（V12 DTO + Agent graph）
  - 旧 UnifiedResponse 格式仅保留 /health 端点
"""

import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.exception_handlers import general_exception_handler, not_found_handler
from app.api.v1.routers import chat as chat_v1
from app.api.v1.routers import companies as companies_v1
from app.api.v1.routers import equity as equity_v1
from app.api.v1.routers import health as health_v1
from app.api.v1.routers import sessions as sessions_v1
from app.core.config import settings
from app.schemas.common import HealthResponse, UnifiedResponse

# 加载 .env
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(env_path)

app = FastAPI(
    title="TruthNet API",
    description="织网鉴真 — 财报反欺诈智能问答系统 (V12 baseline)",
    version="0.2.0",
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
app.include_router(chat_v1.router, prefix="/api/v1")
app.include_router(sessions_v1.router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=settings.DEBUG,
    )
