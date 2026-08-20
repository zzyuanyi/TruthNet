"""最终续审 §7 D1：response_meta 共享解析与 effective active code.

load_context（近期配置窗口回放）与 memory_distillation（长程摘要）
使用同一口径，避免两处各写一份 parser 导致口径漂移。
"""

from __future__ import annotations

import json


def parse_response_meta(value) -> dict:
    """response_meta 多形态解析：dict 直返、JSON 字符串解析、
    坏 JSON/None 回退空 dict。"""
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def effective_active_code(response_meta: dict, company_code: str) -> str:
    """本轮有效活跃主体（最终续审 §7 D1）。

    必须区分「新数据显式写了空 active subject」与「旧数据根本没有该
    字段」——新数据空值表示本轮未产生新 active subject，应跳过本轮
    继续回溯，不得回退可能陈旧的顶层 company_code。
    """
    if "active_company_code" in response_meta:
        return str(response_meta.get("active_company_code") or "")
    return str(company_code or "")
