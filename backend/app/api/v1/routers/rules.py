"""规则定义只读接口 — D2（2026-08-11）.

GET /api/v1/rules/definitions — 返回 R1-R7 展示元数据 + 实际阈值 + 双 hash。
只读：不做匿名 PUT（阈值编辑需鉴权+审计后另行设计）。
"""

import uuid

from fastapi import APIRouter

from app.api.v1.schemas.common import ApiMeta, V12Response
from app.api.v1.schemas.rules import (
    RuleConditionsDTO,
    RuleDefinitionDTO,
    RuleMetricMetaDTO,
    RuleParameterMetaDTO,
    RulesDefinitionsData,
)
from app.domain.finance.financial_rule_config import (
    load_financial_rules,
    rule_hashes,
)

router = APIRouter(prefix="/rules", tags=["rules"])

_RULE_IDS = ("R1", "R2", "R3", "R4", "R5", "R6", "R7")


@router.get(
    "/definitions",
    response_model=V12Response[RulesDefinitionsData],
    responses={500: {"model": dict}},
)
async def get_rule_definitions() -> V12Response[RulesDefinitionsData]:
    """规则定义（只读）。"""
    config = load_financial_rules()
    eval_hash, definition_hash = rule_hashes()
    rules: list[RuleDefinitionDTO] = []
    for rid in _RULE_IDS:
        rule_cfg = getattr(config.rules, rid.lower())
        meta = config.metadata.get(rid)
        thresholds_dump = rule_cfg.thresholds.model_dump()
        rules.append(
            RuleDefinitionDTO(
                rule_id=rid,
                name=meta.name if meta else rid,
                description=meta.description if meta else "",
                enabled=rule_cfg.enabled,
                thresholds=thresholds_dump,
                metrics=(
                    [RuleMetricMetaDTO(**m.model_dump()) for m in meta.metrics]
                    if meta and meta.metrics
                    else []
                ),
                parameters=(
                    [
                        RuleParameterMetaDTO(
                            key=key,
                            value=thresholds_dump.get(key),
                            **param.model_dump(),
                        )
                        for key, param in meta.parameters.items()
                    ]
                    if meta and meta.parameters
                    else []
                ),
                conditions=(
                    RuleConditionsDTO(**meta.conditions.model_dump())
                    if meta and meta.conditions
                    else RuleConditionsDTO()
                ),
            )
        )
    data = RulesDefinitionsData(
        version=config.version,
        execution_version=config.execution_version,
        rules=rules,
        evaluation_config_hash=eval_hash,
        definition_hash=definition_hash,
    )
    return V12Response(
        data=data,
        meta=ApiMeta(
            request_id=str(uuid.uuid4()),
            trace_id=str(uuid.uuid4()),
            data_as_of="",
        ),
        warnings=[],
    )
