"""Conversation 对话领域模型 — V12 baseline."""

from pydantic import BaseModel, Field


class ChatContext(BaseModel):
    """对话附加上下文."""

    company_code: str | None = Field(None, description="公司代码")
    fiscal_year: int | None = Field(None, description="财年")
    report_type: str | None = Field(None, description="报表类型")
