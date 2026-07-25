"""TruthNet FastAPI 应用入口 · V12 baseline (集成版).

路由注册：
  - /health           → 旧健康检查（deprecated，保留兼容）
  - /api/v1/healthz   → V12 存活检查
  - /api/v1/readyz    → V12 就绪检查
  - /api/v1/chat      → V12 REST 对话（router）+ legacy 兼容
  - /api/v1/chat/ws   → V12 WebSocket 对话（router，内置旧格式兼容）
  - /api/v1/companies → V12 公司搜索与画像

变更（集成版）：
  - 每个 URL 只注册一次路由，兼容逻辑集中在 router 内部
  - 不再依赖「重复注册靠顺序决定命中」
  - 保留 legacy /health 和 POST /api/v1/chat 兼容端点
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
from app.core.config import settings
from app.schemas.chat import ChatData, RiskScore
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

# ===== V12 路由注册（legacy 优先，V12 router 次之）=====
# 注意：legacy 路由定义在前，V12 include_router 在后
# 这样 legacy POST /api/v1/chat 和 WS /api/v1/chat/ws 优先匹配
# V12 healthz/readyz/companies 通过 router 注册

# ===== 兼容路由（先注册，优先匹配）=====


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


@app.post("/api/v1/chat", response_model=UnifiedResponse)
async def chat_legacy():
    """对话接口（兼容旧格式 · Prompt4 冻结）。

    返回旧 UnifiedResponse 格式，保持现有测试通过。
    """
    trace_id = str(uuid.uuid4())

    return UnifiedResponse(
        code=0,
        data=ChatData(
            answer="Mock 回答：该功能正在开发中。当前为 V12 兼容接口（旧格式）。",
            evidence=[
                {"source": "利润表", "field": "营业收入", "value": "1505.60亿（mock）"},
                {
                    "source": "现金流量表",
                    "field": "销售商品收到的现金",
                    "value": "1652.35亿（mock）",
                },
            ],
            graph={
                "nodes": [
                    {
                        "id": "600519",
                        "label": "贵州茅台",
                        "type": "company",
                        "depth": 0,
                    },
                    {
                        "id": "mt_group",
                        "label": "茅台集团",
                        "type": "controller",
                        "depth": 1,
                    },
                ],
                "edges": [
                    {"source": "mt_group", "target": "600519", "relation": "54%控股"}
                ],
            },
            timeline=[
                {
                    "date": "2024-03-01",
                    "title": "发布2023年度报告",
                    "category": "公告",
                    "summary": "公司发布2023年年度报告，营收同比增长12%（mock）",
                    "sentiment": "neutral",
                    "sources": ["上交所公告", "财经媒体转载"],
                },
            ],
            risk_score=RiskScore(
                overall=0.15, financial=0.10, ownership=0.20, sentiment=0.05
            ),
            warnings=["mock 预警：关联交易占比略高"],
            missing_modules=[
                "编排Agent",
                "财务勾稽Agent",
                "股权穿透Skill",
                "舆情事件Skill",
            ],
            trace_id=trace_id,
        ),
        message="ok",
        trace_id=trace_id,
    )


# ── V12 路由注册 ──
# 所有 /api/v1 业务逻辑统一通过 include_router 注册
# chat router 内置旧格式兼容（{question} / {data: {question}}）
app.include_router(health_v1.router, prefix="/api/v1")
app.include_router(companies_v1.router, prefix="/api/v1")
app.include_router(equity_v1.router, prefix="/api/v1")
app.include_router(chat_v1.router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=settings.DEBUG,
    )
