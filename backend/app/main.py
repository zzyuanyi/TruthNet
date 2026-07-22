"""TruthNet FastAPI 应用入口 · V12 baseline.

V12 增量变更：
- 新增 /healthz, /readyz 端点
- 新增 GET /api/v1/companies 端点
- POST /api/v1/chat 和 WS /api/v1/chat/ws 保留兼容，同时注册 V12 路由
- 旧 /health 端点保留兼容（deprecated）
- 新增 V12 response envelope (data/meta/warnings)
- 新增 Problem Details 错误格式
"""

import json
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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


@app.websocket("/api/v1/chat/ws")
async def websocket_chat_legacy(ws: WebSocket):
    """WebSocket 对话端点（兼容旧格式 · Prompt4 冻结）。

    保留旧格式兼容。
    """
    await ws.accept()
    trace_id = str(uuid.uuid4())

    try:
        while True:
            raw = await ws.receive_text()

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json(
                    {
                        "type": "error",
                        "data": {
                            "code": 400,
                            "message": "无效的 JSON 格式",
                            "trace_id": trace_id,
                        },
                    }
                )
                continue

            question = msg.get("data", {}).get("question", "")
            if not question:
                await ws.send_json(
                    {
                        "type": "error",
                        "data": {
                            "code": 400,
                            "message": "question 字段为必填项",
                            "trace_id": trace_id,
                        },
                    }
                )
                continue

            await ws.send_json(
                {
                    "type": "status",
                    "data": {
                        "message": f"正在分析: {question[:50]}...",
                        "trace_id": trace_id,
                    },
                }
            )

            mock_answer = (
                f"Mock 回答：关于「{question[:30]}...」的分析正在开发中。"
                "当前 WebSocket 端点已就绪（V12 兼容，旧格式）。"
            )
            partial_texts = mock_answer.split("。")
            for i, text in enumerate(partial_texts):
                if text.strip():
                    await ws.send_json(
                        {
                            "type": "partial_answer",
                            "data": {
                                "text": text.strip() + "。",
                                "sequence": i + 1,
                                "trace_id": trace_id,
                            },
                        }
                    )

            await ws.send_json(
                {
                    "type": "final_answer",
                    "data": {
                        "answer": mock_answer,
                        "evidence": [],
                        "graph": {"nodes": [], "edges": []},
                        "timeline": [],
                        "risk_score": {
                            "overall": 0.0,
                            "financial": 0.0,
                            "ownership": 0.0,
                            "sentiment": 0.0,
                        },
                        "warnings": [],
                        "missing_modules": [
                            "编排Agent",
                            "财务勾稽Agent",
                            "股权穿透Skill",
                            "舆情事件Skill",
                        ],
                        "trace_id": trace_id,
                    },
                }
            )

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await ws.send_json(
                {
                    "type": "error",
                    "data": {
                        "code": 500,
                        "message": f"内部错误: {str(exc)}",
                        "trace_id": trace_id,
                    },
                }
            )
        except Exception:
            pass


# ===== V12 路由注册（次优先）=====
# healthz, readyz, companies 等新端点
app.include_router(health_v1.router, prefix="/api/v1")
app.include_router(companies_v1.router, prefix="/api/v1")
app.include_router(equity_v1.router, prefix="/api/v1")
# V12 chat router 也注册，但 legacy 路由优先匹配
app.include_router(chat_v1.router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=settings.DEBUG,
    )
