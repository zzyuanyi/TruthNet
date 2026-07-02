"""TruthNet FastAPI 应用入口."""

import json
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.schemas.common import HealthResponse, UnifiedResponse
from app.schemas.chat import ChatData, RiskScore

# 加载 .env
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(env_path)

app = FastAPI(
    title="TruthNet API",
    description="织网鉴真 — 财报反欺诈智能问答系统",
    version="0.1.0",
)

# CORS（开发阶段允许所有来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=UnifiedResponse[HealthResponse])
async def health_check():
    """健康检查接口。"""
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
async def chat():
    """对话接口（MVP mock 占位 · Prompt4 冻结）。

    TODO: 接入编排 Agent 后替换为真实实现。

    返回结构与 docs/API_CONTRACT.md 严格一致。
    risk_score 已冻结为 RiskScore 对象（overall/financial/ownership/sentiment）。
    """
    trace_id = str(uuid.uuid4())

    return UnifiedResponse(
        code=0,
        data=ChatData(
            answer="Mock 回答：该功能正在开发中。当前为 Prompt4 冻结的 MVP mock 接口。",
            evidence=[
                {
                    "source": "利润表",
                    "field": "营业收入",
                    "value": "1505.60亿（mock）",
                },
                {
                    "source": "现金流量表",
                    "field": "销售商品收到的现金",
                    "value": "1652.35亿（mock）",
                },
            ],
            graph={
                "nodes": [
                    {"id": "600519", "label": "贵州茅台", "type": "company", "depth": 0},
                    {"id": "mt_group", "label": "茅台集团", "type": "controller", "depth": 1},
                ],
                "edges": [
                    {"source": "mt_group", "target": "600519", "relation": "54%控股"},
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
                {
                    "date": "2023-08-02",
                    "title": "发布2023半年报",
                    "category": "公告",
                    "summary": "公司发布2023年半年度报告（mock）",
                    "sentiment": "neutral",
                    "sources": ["上交所公告"],
                },
            ],
            risk_score=RiskScore(
                overall=0.15,
                financial=0.10,
                ownership=0.20,
                sentiment=0.05,
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
async def websocket_chat(ws: WebSocket):
    """WebSocket 对话端点（最小 mock 实现 · Prompt4 冻结）。

    接收用户消息 JSON，返回 status → partial_answer → final_answer 三类消息。
    不调用真实 LLM，不访问真实数据，仅验证消息格式与交互流程。

    final_answer.data 复用 ChatData 字段结构。
    """
    await ws.accept()
    trace_id = str(uuid.uuid4())

    try:
        while True:
            raw = await ws.receive_text()

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({
                    "type": "error",
                    "data": {
                        "code": 400,
                        "message": "无效的 JSON 格式",
                        "trace_id": trace_id,
                    },
                })
                continue

            msg_type = msg.get("type", "")
            msg_data = msg.get("data", {})
            question = msg_data.get("question", "")

            if not question:
                await ws.send_json({
                    "type": "error",
                    "data": {
                        "code": 400,
                        "message": "question 字段为必填项",
                        "trace_id": trace_id,
                    },
                })
                continue

            # 1. status
            await ws.send_json({
                "type": "status",
                "data": {
                    "message": f"正在分析: {question[:50]}...",
                    "trace_id": trace_id,
                },
            })

            # 2. partial_answer（模拟流式输出）
            mock_answer = (
                f"Mock 回答：关于「{question[:30]}...」的分析正在开发中。"
                "当前 WebSocket mock 端点已就绪（Prompt4 冻结）。"
            )
            partial_texts = mock_answer.split("。")
            for i, text in enumerate(partial_texts):
                if text.strip():
                    await ws.send_json({
                        "type": "partial_answer",
                        "data": {
                            "text": text.strip() + "。",
                            "sequence": i + 1,
                            "trace_id": trace_id,
                        },
                    })

            # 3. final_answer（data 结构与 HTTP ChatData 一致）
            await ws.send_json({
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
            })

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await ws.send_json({
                "type": "error",
                "data": {
                    "code": 500,
                    "message": f"内部错误: {str(exc)}",
                    "trace_id": trace_id,
                },
            })
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=settings.DEBUG,
    )
