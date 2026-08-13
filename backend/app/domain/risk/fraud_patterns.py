"""造假手法模式库加载与匹配 — Phase C 数据任务 2 / 后端任务 6.

模式定义唯一来源：`fraud_patterns.yaml`（机器可读，与 docs/FRAUD_PATTERNS.md 同步）。
风险 Router / comparisons / risk_scoring_service 一律调用 `match_patterns()`，
禁止在代码中内联第二套 pattern map。

匹配输出仅表示"风险信号/疑似模式"，不构成造假认定。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

_PATTERNS_FILE = Path(__file__).resolve().parent / "fraud_patterns.yaml"

# 规则 status 值
_TRIGGERED = "triggered"
_NOT_TRIGGERED = "not_triggered"
_UNAVAILABLE = {"insufficient_data", "not_applicable"}


@dataclass
class PatternDefinition:
    """从 yaml 加载的模式定义."""

    pattern_id: str
    pattern_name: str
    applicable_company_types: list[int]
    required_rules: list[str]
    optional_rules: list[str]
    core_logic: str
    confidence_rules: list[dict]
    exclusion_conditions: list[str] = field(default_factory=list)
    supporting_signals: list[str] = field(default_factory=list)
    typical_companies: list[str] = field(default_factory=list)
    evidence_requirements: list[str] = field(default_factory=list)
    limitations: str = ""
    partial_coverage_supported: bool = True
    # Phase D #16 模式三要素（可审计基础定义，供 REST/WS 一致透出）
    phase: str = ""  # 风险模式当前表现阶段（受控字符串）
    alternative_explanation: str = ""  # 非舞弊解释
    regulatory_hint: str = ""  # 监管核查提示（非法律定罪结论）


@dataclass
class PatternMatch:
    """单条模式匹配结果."""

    pattern_id: str
    pattern_name: str
    triggered_rules: list[str]
    confidence: str  # high / medium / low
    reasoning: str
    partial_coverage: bool = False
    unavailable_rules: list[str] = field(default_factory=list)
    # Phase D #16 三要素（匹配时透出；未定义时由调用方补充审慎默认值）
    phase: str = ""
    alternative_explanation: str = ""
    regulatory_hint: str = ""


def load_patterns() -> dict[str, PatternDefinition]:
    """从 yaml 加载全部模式定义（确定性顺序，缓存）."""
    if not _PATTERNS_FILE.exists():
        raise FileNotFoundError(f"模式定义文件不存在: {_PATTERNS_FILE}")
    with _PATTERNS_FILE.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    patterns: dict[str, PatternDefinition] = {}
    for item in data.get("patterns", []):
        p = PatternDefinition(**item)
        patterns[p.pattern_id] = p
    return patterns


def _is_triggered(result: dict) -> bool:
    """规则是否触发.

    规则引擎语义: status == "triggered" ⟺ severity 非 green。
    以 status 为准（severity 缺失/未知时不影响触发判定）。
    """
    if result.get("status") != _TRIGGERED:
        return False
    sev = result.get("severity")
    # 显式 green/not_triggered 即使 status 异常也不视为触发
    if sev in ("green", _NOT_TRIGGERED, "unknown"):
        return False
    return True


def _count_triggered(results: dict[str, dict]) -> int:
    """统计触发规则数（排除 unavailable）。"""
    return sum(1 for r in results.values() if _is_triggered(r))


def _unavailable_rules(results: dict[str, dict], all_rules: list[str]) -> list[str]:
    """返回 unavailable 规则（insufficient_data / not_applicable）。"""
    return [
        rid for rid in all_rules if results.get(rid, {}).get("status") in _UNAVAILABLE
    ]


def _triad_fallback(pid: str, p: PatternDefinition) -> tuple[str, str, str]:
    """Phase D #16：三要素审慎默认值（yaml 未定义时补充，不编造法规条款）。

    返回 (phase, alternative_explanation, regulatory_hint)。
    不得捏造条款编号；regulatory_hint 是监管核查提示，不是法律定罪结论。
    """
    phase = p.phase
    alt = p.alternative_explanation
    hint = p.regulatory_hint

    if not phase:
        phase = "signal_detected"  # 受控字符串：检测到信号
    if not alt:
        alt = "该信号可能存在非舞弊的业务解释，需结合业务周期、结算节奏、行业特性进一步核验"
    if not hint:
        hint = "建议结合公告、审计意见和监管文件进一步核验该信号，" "不构成法律定罪结论"
    return phase, alt, hint


def match_patterns(
    results: dict[str, dict],
    *,
    has_related_party: bool = False,
) -> list[PatternMatch]:
    """按模式定义匹配规则结果。

    Args:
        results: {rule_id: {"status": ..., "severity": ...}}
        has_related_party: 是否存在关联方图谱信号（P2 high 判定）
    """
    patterns = load_patterns()
    triggered_ids = [rid for rid, r in results.items() if _is_triggered(r)]
    triggered_set = set(triggered_ids)
    matches: list[PatternMatch] = []
    all_rules = [f"R{i}" for i in range(1, 8)]

    for pid, p in patterns.items():
        phase, alt, hint = _triad_fallback(pid, p)
        # P5 综合粉饰型：按触发总数
        if pid == "P5":
            count = _count_triggered(results)
            if count >= 5:
                matches.append(
                    PatternMatch(
                        pattern_id=pid,
                        pattern_name=p.pattern_name,
                        triggered_rules=list(triggered_set),
                        confidence="high",
                        reasoning=f"{count} 条规则同时触发，系统性粉饰嫌疑",
                        phase=phase,
                        alternative_explanation=alt,
                        regulatory_hint=hint,
                    )
                )
            elif count >= 3:
                matches.append(
                    PatternMatch(
                        pattern_id=pid,
                        pattern_name=p.pattern_name,
                        triggered_rules=list(triggered_set),
                        confidence="medium",
                        reasoning=f"{count} 条规则触发，多维度信号叠加",
                        phase=phase,
                        alternative_explanation=alt,
                        regulatory_hint=hint,
                    )
                )
            continue

        # P1-P4：required 全部触发才考虑
        if not p.required_rules or not set(p.required_rules) <= triggered_set:
            continue
        required = p.required_rules
        optional = p.optional_rules
        matched_required = [r for r in required if r in triggered_set]
        matched_optional = [r for r in optional if r in triggered_set]

        # 判定置信度
        all_required_and_optional = (
            optional and set(required) | set(optional) <= triggered_set
        )
        all_required = len(required) == len(matched_required)
        reasoning = f"{len(triggered_ids)}/{len(all_rules)} 条规则触发"

        confidence = "medium"
        if pid == "P2" and all_required and has_related_party:
            confidence = "high"
            reasoning = "R3+R6 触发且存在关联方信号，逻辑链完整"
        elif all_required_and_optional:
            confidence = "high"
            reasoning = "必需+增强规则全部触发，跨报表交叉印证"
        elif all_required:
            confidence = "medium"
            reasoning = "必需规则触发"

        match = PatternMatch(
            pattern_id=pid,
            pattern_name=p.pattern_name,
            triggered_rules=matched_required + matched_optional,
            confidence=confidence,
            reasoning=reasoning,
            phase=phase,
            alternative_explanation=alt,
            regulatory_hint=hint,
        )

        # partial coverage 标记
        unavailable = _unavailable_rules(results, all_rules)
        if unavailable:
            match.partial_coverage = True
            match.unavailable_rules = unavailable
        matches.append(match)

    return matches
