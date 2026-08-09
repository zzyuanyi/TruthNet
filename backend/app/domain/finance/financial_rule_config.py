"""Strict runtime configuration for financial warning rules R1-R7."""

from __future__ import annotations

from pathlib import Path
from threading import RLock
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from app.domain.finance.models import RuleResult

_FINANCIAL_RULES_FILE = Path(__file__).resolve().parent / "financial_rules.yaml"
_CACHE_LOCK = RLock()
_CACHE: tuple[Path, int, FinancialRulesConfig] | None = None


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


class FinancialRulesConfig(_StrictModel):
    version: str = Field(min_length=1)
    rules: FinancialRuleDefinitions


RuleConfig = (
    R1RuleConfig
    | R2RuleConfig
    | R3RuleConfig
    | R4RuleConfig
    | R5RuleConfig
    | R6RuleConfig
    | R7RuleConfig
)


def load_financial_rules(path: Path | None = None) -> FinancialRulesConfig:
    """Load and validate configuration, reloading after a file mtime change."""
    global _CACHE

    config_path = (path or _FINANCIAL_RULES_FILE).resolve()
    mtime_ns = config_path.stat().st_mtime_ns
    with _CACHE_LOCK:
        if _CACHE and _CACHE[0] == config_path and _CACHE[1] == mtime_ns:
            return _CACHE[2]
        with config_path.open("r", encoding="utf-8") as stream:
            raw = yaml.safe_load(stream)
        config = FinancialRulesConfig.model_validate(raw)
        _CACHE = (config_path, mtime_ns, config)
        return config


def clear_financial_rule_config_cache() -> None:
    """Clear the loader cache for tests and administrative reloads."""
    global _CACHE
    with _CACHE_LOCK:
        _CACHE = None


def get_rule_config(
    rule_id: Literal["R1", "R2", "R3", "R4", "R5", "R6", "R7"],
) -> RuleConfig:
    config = load_financial_rules()
    return getattr(config.rules, rule_id.lower())


def disabled_rule_result(rule_id: str, rule_name: str) -> RuleResult:
    """Return an explicit result when an administrator disables a rule."""
    version = load_financial_rules().version
    return RuleResult(
        rule_id=rule_id,
        rule_version=version,
        rule_name=rule_name,
        status="not_applicable",
        severity="unknown",
        explanation=f"{rule_id} 已在 financial_rules.yaml 中关闭",
        warnings=["RULE_DISABLED"],
    )
