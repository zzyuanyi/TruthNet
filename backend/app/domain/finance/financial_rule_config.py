"""Strict runtime configuration for financial warning rules R1-R7."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from threading import RLock
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from app.domain.finance.models import RuleResult

_FINANCIAL_RULES_FILE = Path(__file__).resolve().parent / "financial_rules.yaml"
# 8/23 会7 深化：用户可配置阈值 → 写入独立 override 文件（不入库、不污染
# 源码 YAML），load 时合并；DELETE 重置删除该文件恢复默认。
_OVERRIDE_FILE = Path(__file__).resolve().parent / "financial_rules.override.yaml"
_RULE_IDS = ("R1", "R2", "R3", "R4", "R5", "R6", "R7")
_CACHE_LOCK = RLock()
# 缓存键：((base_path, base_mtime), (override_path_or_None, override_mtime_or_None))
_CACHE: (
    tuple[
        tuple[tuple[Path, int], tuple[Path | None, int | None]],
        FinancialRulesConfig,
    ]
    | None
) = None


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class R1Thresholds(_StrictModel):
    red_consecutive_gap_pp: float = Field(ge=0)
    red_previous_gap_pp: float = Field(ge=0)
    red_declining_revenue_gap_pp: float = Field(ge=0)
    red_receivable_growth_pct: float = Field(ge=0)
    orange_gap_pp: float = Field(ge=0)
    orange_consecutive_gap_pp: float = Field(ge=0)
    orange_previous_gap_pp: float = Field(ge=0)
    yellow_gap_pp: float = Field(ge=0)


class R2Thresholds(_StrictModel):
    red_consecutive_negative_cashflow_periods: int = Field(ge=1)
    red_growth_consecutive_periods: int = Field(ge=1)
    red_profit_yoy_pct: float = Field(ge=0)
    orange_consecutive_negative_cashflow_periods: int = Field(ge=1)
    orange_cashflow_profit_ratio: float = Field(ge=0)
    yellow_cashflow_profit_ratio: float = Field(ge=0)


class R3Thresholds(_StrictModel):
    dual_high_cash_pct: float = Field(ge=0)
    dual_high_debt_pct: float = Field(ge=0)
    red_cash_pct: float = Field(ge=0)
    red_debt_pct: float = Field(ge=0)
    red_implied_interest_rate_pct: float = Field(ge=0)
    yellow_cash_pct: float = Field(ge=0)


class R4Thresholds(_StrictModel):
    red_growth_gap_pp: float = Field(ge=0)
    red_inventory_growth_pct: float = Field(ge=0)
    red_revenue_growth_max_pct: float
    red_turnover_change_pct: float = Field(ge=0)
    red_turnover_days: float = Field(ge=0)
    orange_growth_gap_pp: float = Field(ge=0)
    orange_turnover_change_pct: float = Field(ge=0)
    yellow_growth_gap_pp: float = Field(ge=0)
    yellow_turnover_change_pct: float = Field(ge=0)


class R5Thresholds(_StrictModel):
    gross_margin_deviation_pct: float = Field(ge=0)
    red_gross_margin_deviation_pct: float = Field(ge=0)
    red_expense_rate_drop_pct: float = Field(ge=0)
    expense_rate_drop_pct: float = Field(ge=0)
    combined_deviation_pct: float = Field(ge=0)


class R6Thresholds(_StrictModel):
    large_amount: float = Field(ge=0)
    red_assets_ratio_pct: float = Field(ge=0)
    red_yoy_pct: float = Field(ge=0)
    red_receivable_ratio: float = Field(ge=0)
    orange_assets_ratio_pct: float = Field(ge=0)
    orange_yoy_pct: float = Field(ge=0)
    orange_receivable_ratio: float = Field(ge=0)
    yellow_assets_ratio_pct: float = Field(ge=0)
    yellow_secondary_assets_ratio_pct: float = Field(ge=0)
    yellow_yoy_pct: float = Field(ge=0)


class R7Thresholds(_StrictModel):
    red_core_profit_ratio: float = Field(ge=0)
    weak_core_profit_ratio: float = Field(ge=0)
    quality_divergence_pp: float = Field(ge=0)
    revenue_divergence_pp: float = Field(ge=0)
    cash_divergence_pp: float = Field(ge=0)
    orange_non_operating_ratio_pct: float = Field(ge=0)
    yellow_non_operating_ratio_pct: float = Field(ge=0)


class R1RuleConfig(_StrictModel):
    enabled: bool
    thresholds: R1Thresholds


class R2RuleConfig(_StrictModel):
    enabled: bool
    thresholds: R2Thresholds


class R3RuleConfig(_StrictModel):
    enabled: bool
    thresholds: R3Thresholds


class R4RuleConfig(_StrictModel):
    enabled: bool
    thresholds: R4Thresholds


class R5RuleConfig(_StrictModel):
    enabled: bool
    thresholds: R5Thresholds


class R6RuleConfig(_StrictModel):
    enabled: bool
    thresholds: R6Thresholds


class R7RuleConfig(_StrictModel):
    enabled: bool
    thresholds: R7Thresholds


class FinancialRuleDefinitions(_StrictModel):
    r1: R1RuleConfig = Field(alias="R1")
    r2: R2RuleConfig = Field(alias="R2")
    r3: R3RuleConfig = Field(alias="R3")
    r4: R4RuleConfig = Field(alias="R4")
    r5: R5RuleConfig = Field(alias="R5")
    r6: R6RuleConfig = Field(alias="R6")
    r7: R7RuleConfig = Field(alias="R7")


# ── 展示元数据（v1.1.0，D2 规则定义接口）────────────────
# 与 financial_rules.yaml metadata 段一一对应；conditions 为人工维护的
# 判定说明文本（不尝试从代码反推）。展示元数据不参与规则执行。

_RISK_DIRECTIONS = ("higher_is_riskier", "lower_is_riskier", "neutral")


class RuleMetricMeta(_StrictModel):
    key: str
    label: str
    unit: str = ""
    formula: str = ""
    risk_direction: Literal[_RISK_DIRECTIONS] = "neutral"


class RuleParameterMeta(_StrictModel):
    unit: str = ""
    description: str = ""


class RuleConditionsMeta(_StrictModel):
    red: str = ""
    orange: str = ""
    yellow: str = ""


class RuleMetadata(_StrictModel):
    name: str
    description: str = ""
    metrics: list[RuleMetricMeta] = Field(default_factory=list)
    parameters: dict[str, RuleParameterMeta] = Field(default_factory=dict)
    conditions: RuleConditionsMeta = Field(default_factory=RuleConditionsMeta)


class FinancialRulesConfig(_StrictModel):
    version: str = Field(min_length=1)  # 展示元数据版本（D2 规则页）
    execution_version: str = Field(default="1.0.0", min_length=1)  # 规则执行版本
    rules: FinancialRuleDefinitions
    # 键为 R1..R7；缺省空 dict 兼容旧版本文件（无展示元数据）
    metadata: dict[str, RuleMetadata] = Field(default_factory=dict)


RuleConfig = (
    R1RuleConfig
    | R2RuleConfig
    | R3RuleConfig
    | R4RuleConfig
    | R5RuleConfig
    | R6RuleConfig
    | R7RuleConfig
)


def _load_raw_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


def load_financial_rules(path: Path | None = None) -> FinancialRulesConfig:
    """Load and validate configuration, reloading after file mtime changes.

    8/23 会7 深化：base YAML 加载后合并 override 文件（存在时）——
    override 的 rules 段按规则全量覆盖 base（enabled + thresholds）；
    metadata/version 以 base 为准。缓存键同时覆盖两个文件的 mtime。
    """
    global _CACHE

    base_path = (path or _FINANCIAL_RULES_FILE).resolve()
    override_path = _OVERRIDE_FILE.resolve() if _OVERRIDE_FILE.exists() else None
    base_mtime = base_path.stat().st_mtime_ns
    ov_mtime = override_path.stat().st_mtime_ns if override_path else None
    key = ((base_path, base_mtime), (override_path, ov_mtime))
    with _CACHE_LOCK:
        if _CACHE and _CACHE[0] == key:
            return _CACHE[1]
        raw = _load_raw_yaml(base_path)
        if override_path is not None:
            over = _load_raw_yaml(override_path)
            over_rules = over.get("rules") or {}
            base_rules = raw.setdefault("rules", {})
            for rid in _RULE_IDS:
                if rid in over_rules:
                    base_rules[rid] = over_rules[rid]
        config = FinancialRulesConfig.model_validate(raw)
        _CACHE = (key, config)
        return config


def save_rule_config(rules: dict) -> None:
    """覆盖保存阈值配置（8/23 会7 深化）。

    rules 为 FinancialRuleDefinitions.model_dump(by_alias=True) 结果
    （{R1..R7: {enabled, thresholds}}，由路由层严格校验）。
    原子写（tmp + replace）；写入后清缓存，mtime 变化自动重载。
    """
    payload = {"rules": rules}
    tmp = _OVERRIDE_FILE.with_suffix(".override.yaml.tmp")
    tmp.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    tmp.replace(_OVERRIDE_FILE)
    clear_financial_rule_config_cache()


def reset_rule_config() -> None:
    """删除 override 文件，恢复默认配置（8/23 会7 深化）。"""
    for _attempt in range(3):
        try:
            if _OVERRIDE_FILE.exists():
                _OVERRIDE_FILE.unlink()
            break
        except OSError:  # Windows Defender 实时扫描短暂锁文件 → 重试
            import time

            time.sleep(0.3)
    clear_financial_rule_config_cache()


def override_active() -> bool:
    """是否存在用户覆盖配置（is_overridden 展示 + 重置按钮可用性）。"""
    return _OVERRIDE_FILE.exists()


def clear_financial_rule_config_cache() -> None:
    """Clear the loader cache for tests and administrative reloads."""
    global _CACHE
    with _CACHE_LOCK:
        _CACHE = None


def rule_hashes() -> tuple[str, str]:
    """双 hash（D2，v3.1）：
    - evaluation_config_hash：仅覆盖 enabled + thresholds（风险缓存失效键）；
    - definition_hash：完整展示元数据（规则页版本识别）。
    均基于规范化 JSON（sort_keys），同内容稳定、任意字段变化即变。
    """
    config = load_financial_rules()
    rules_dump = config.rules.model_dump(by_alias=True)
    eval_part = {  # v3.4：展示元数据升级（version）不使执行缓存失效
        "rules": {
            rid: {"enabled": cfg["enabled"], "thresholds": cfg["thresholds"]}
            for rid, cfg in rules_dump.items()
        },
    }
    def_part = config.model_dump(by_alias=True, exclude_none=True)
    return (
        hashlib.sha256(
            json.dumps(eval_part, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16],
        hashlib.sha256(
            json.dumps(def_part, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16],
    )


def get_rule_config(
    rule_id: Literal["R1", "R2", "R3", "R4", "R5", "R6", "R7"],
) -> RuleConfig:
    config = load_financial_rules()
    return getattr(config.rules, rule_id.lower())


def get_execution_version() -> str:
    """规则执行版本（v3.4：R1-R7 输出/Claim/缓存键统一来源）。"""
    return load_financial_rules().execution_version


def disabled_rule_result(rule_id: str, rule_name: str) -> RuleResult:
    """Return an explicit result when an administrator disables a rule."""
    version = get_execution_version()
    return RuleResult(
        rule_id=rule_id,
        rule_version=version,
        rule_name=rule_name,
        status="not_applicable",
        severity="unknown",
        explanation=f"{rule_id} 已在 financial_rules.yaml 中关闭",
        warnings=["RULE_DISABLED"],
    )
