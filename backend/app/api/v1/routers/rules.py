"""规则定义接口 — D2（2026-08-11）+ 会7 深化（8/23）.

GET    /api/v1/rules/definitions — R1-R7 展示元数据 + 实际阈值 + 双 hash + is_overridden
PUT    /api/v1/rules/config       — 覆盖保存阈值（完整 rules 结构，strict 校验，
                                     写入 override 文件；风险缓存经 hash 自动失效）
DELETE /api/v1/rules/config       — 删除 override，恢复默认配置
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
    FinancialRuleDefinitions,
    load_financial_rules,
    override_active,
    reset_rule_config,
    rule_hashes,
    save_rule_config,
)

router = APIRouter(prefix="/rules", tags=["rules"])

_RULE_IDS = ("R1", "R2", "R3", "R4", "R5", "R6", "R7")


def _build_rules_data() -> RulesDefinitionsData:
    config = load_financial_rules()
    eval_hash, definition_hash = rule_hashes()
    overridden = override_active()
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
    return RulesDefinitionsData(
        version=config.version,
        execution_version=config.execution_version,
        rules=rules,
        evaluation_config_hash=eval_hash,
        definition_hash=definition_hash,
        source=(
            "financial_rules.yaml + override" if overridden else "financial_rules.yaml"
        ),
        is_overridden=overridden,
    )


def _response(data: RulesDefinitionsData) -> V12Response[RulesDefinitionsData]:
    return V12Response(
        data=data,
        meta=ApiMeta(
            request_id=str(uuid.uuid4()),
            trace_id=str(uuid.uuid4()),
            data_as_of="",
        ),
        warnings=[],
    )


@router.get(
    "/definitions",
    response_model=V12Response[RulesDefinitionsData],
    responses={500: {"model": dict}},
)
async def get_rule_definitions() -> V12Response[RulesDefinitionsData]:
    """规则定义（只读）。"""
    return _response(_build_rules_data())


@router.put(
    "/config",
    response_model=V12Response[RulesDefinitionsData],
    responses={422: {"model": dict}, 500: {"model": dict}},
)
async def update_rule_config(
    body: FinancialRuleDefinitions,
) -> V12Response[RulesDefinitionsData]:
    """覆盖保存阈值配置（会7 深化，8/23）。

    body 为完整 rules 结构（R1..R7 大写键，strict 校验：未知键/越界值
    → 422）。保存后 risk/finance 缓存经 evaluation_config_hash 自动失效，
    重新请求即按新阈值计算。
    """
    save_rule_config(body.model_dump(by_alias=True))
    return _response(_build_rules_data())


@router.delete(
    "/config",
    response_model=V12Response[RulesDefinitionsData],
    responses={500: {"model": dict}},
)
async def delete_rule_config() -> V12Response[RulesDefinitionsData]:
    """删除用户覆盖，恢复默认阈值配置。"""
    reset_rule_config()
    return _response(_build_rules_data())
