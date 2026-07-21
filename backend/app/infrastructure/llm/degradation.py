"""LLM 降级模块 — V12 §7.7 第 3 级降级.

当所有 LLM Provider 不可用时，返回基于模板的结构化结果。
降级结果包含 _degraded 标志字段，调用方可据此识别。
"""

import logging

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ── 降级文本模板 ──────────────────────────────────────────

_DEGRADATION_TEXT_TEMPLATES: dict[str, str] = {
    "finance_analysis": (
        "本轮 LLM 财务分析因服务故障未能完成。"
        "确定性规则计算已完成，您可在下方查看结构化结果。"
        "建议稍后重试以获取完整分析。"
    ),
    "equity_analysis": (
        "本轮 LLM 股权穿透分析因服务故障未能完成。"
        "图谱计算已完成，您可在下方查看股权关系。"
        "建议稍后重试以获取完整分析。"
    ),
    "events_analysis": (
        "本轮 LLM 舆情事件分析因服务故障未能完成。"
        "事件时间线已展示，但语义分析未能生成。"
        "建议稍后重试以获取完整分析。"
    ),
    "general": (
        "本轮 LLM 分析因服务故障未能完成。"
        "确定性计算和结构化数据已完成，您可在下方查看。"
        "建议稍后重试以获取完整分析。"
    ),
}


def create_degradation_response(task_type: str = "general", context: dict | None = None) -> str:
    """返回降级的文本回答.

    Args:
        task_type: 任务类型（finance_analysis / equity_analysis / events_analysis / general）
        context: 额外上下文信息（当前未使用，保留扩展接口）

    Returns:
        带降级标志的文本回答。
    """
    template = _DEGRADATION_TEXT_TEMPLATES.get(
        task_type, _DEGRADATION_TEXT_TEMPLATES["general"]
    )
    logger.warning("返回降级文本回答 (task_type=%s)", task_type)
    return template


def create_degradation_structured(
    output_schema: type[BaseModel],
    reason: str = "LLM 不可用",
) -> BaseModel:
    """返回降级的结构化结果——使用模型默认值.

    Args:
        output_schema: 目标 Pydantic 模型类
        reason: 降级原因

    Returns:
        output_schema 的实例，使用默认字段值。
    """
    logger.warning(
        "返回降级结构化结果 (schema=%s, reason=%s)",
        output_schema.__name__,
        reason,
    )
    try:
        instance = output_schema()
        # 如果模型有 _degraded 字段，设置它
        if hasattr(instance, "_degraded"):
            object.__setattr__(instance, "_degraded", True)
        return instance
    except Exception:
        # 如果默认构造函数失败，用 model_validate 空字典
        return output_schema.model_validate({})
