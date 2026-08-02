"""母公司报表口径共享模块 — Phase C 固定分析口径.

本模块是全项目唯一的口径说明 / quality 构建 / 公司类型 Gate 来源：
  - 口径与文案常量（finance_node、generate_answer、REST/WS 统一引用，禁止各节点重写）；
  - build_parent_scope_quality(): 所有规则状态（triggered/not_triggered/not_applicable/
    insufficient_data）统一携带母公司口径质量信息；
  - check_company_type() + build_gate_result(): R1–R7 唯一的公司类型适用性 Gate，
    NULL/非法类型一律视为 unknown（insufficient_data），禁止默认当作非金融企业。
"""

from dataclasses import dataclass
from typing import Literal

from app.domain.finance._fetch import fetch_company_field
from app.domain.finance.models import RuleResult
from app.domain.finance.statement_type import (
    PARENT_STATEMENT_SCOPE,
    PARENT_STATEMENT_TYPE,
)

# ── 统一口径说明（全局唯一文案）───────────────────────────
SCOPE_NOTE = "本次财务分析采用母公司报表口径，不包含合并范围内子公司数据。"
NO_SIGNAL_IN_SCOPE = "在母公司报表及当前数据覆盖范围内，未发现明显异常信号。"
RISK_SIGNAL_IN_SCOPE = "基于母公司报表及当前数据覆盖，共检测到 {n} 项风险信号。"
MISSING_PARENT_STATEMENT = "当前数据中缺少该公司的母公司报表，无法完成财务规则分析。"

# 财务 Claim 统一限制说明
CLAIM_PARENT_SCOPE_LIMITATION = "结论仅基于母公司报表，不包含合并范围内子公司。"

# 稳定 warning code
W_COMPANY_TYPE_UNKNOWN = "COMPANY_TYPE_UNKNOWN"
W_COMPANY_TYPE_FINANCIAL_EXCLUDED = "COMPANY_TYPE_FINANCIAL_EXCLUDED"


def build_parent_scope_quality(
    coverage: float = 0.0,
    data_completeness: float = 0.0,
    missing_periods: int = 0,
    company_type_status: str = "known_non_financial",
    extra: dict | None = None,
) -> dict:
    """构建所有规则状态通用的母公司口径质量信息.

    最低字段:
      statement_scope = "parent_company"
      statement_type  = "408006000"
      coverage / data_completeness / missing_periods
      company_type_status = known_non_financial | excluded_financial | unknown

    extra 用于追加各规则特有字段（如 turnover_calculable）。
    """
    base = {
        "statement_scope": PARENT_STATEMENT_SCOPE,
        "statement_type": PARENT_STATEMENT_TYPE,
        "coverage": coverage,
        "data_coverage": coverage,  # 兼容旧字段（旧规则使用 data_coverage）
        "data_completeness": data_completeness,
        "missing_periods": missing_periods,
        "company_type_status": company_type_status,
    }
    if extra:
        base.update(extra)
    return base


@dataclass
class CompanyTypeGate:
    """公司类型适用性判定结果."""

    status: Literal["eligible", "excluded_financial", "unknown"]
    comp_type_code: int | None
    explanation: str = ""


def check_company_type(company_code: str) -> CompanyTypeGate:
    """统一公司类型 Gate — 所有 R1–R7 必须调用，禁止各规则自写判断.

    - comp_type_code == 1           → eligible（非金融，允许执行）
    - comp_type_code in (2, 3, 4)   → excluded_financial（银行/保险/证券，不适用非金融规则）
    - NULL / 非法 / 未知             → unknown（数据不足，不得默认当作非金融）
    """
    comp_type = fetch_company_field(company_code, "comp_type_code")
    if comp_type is None or comp_type not in (1, 2, 3, 4):
        return CompanyTypeGate(
            status="unknown",
            comp_type_code=comp_type,
            explanation="公司类型缺失，无法判断是否适用非金融企业规则",
        )
    if comp_type == 1:
        return CompanyTypeGate(
            status="eligible",
            comp_type_code=1,
            explanation="非金融企业，允许执行非金融财务规则",
        )
    return CompanyTypeGate(
        status="excluded_financial",
        comp_type_code=comp_type,
        explanation=(f"金融企业不适用非金融财务规则（comp_type_code={comp_type}）"),
    )


def build_gate_result(
    rule_id: str, rule_name: str, gate: CompanyTypeGate
) -> RuleResult:
    """根据 Gate 结果构造统一的不适用 / 数据不足 RuleResult.

    - unknown:           status=insufficient_data, severity=unknown, warning=COMPANY_TYPE_UNKNOWN
    - excluded_financial: status=not_applicable,    severity=unknown, warning=COMPANY_TYPE_FINANCIAL_EXCLUDED
    """
    if gate.status == "unknown":
        return RuleResult(
            rule_id=rule_id,
            rule_version="1.0.0",
            rule_name=rule_name,
            status="insufficient_data",
            severity="unknown",
            explanation=gate.explanation,
            quality=build_parent_scope_quality(company_type_status="unknown"),
            warnings=[W_COMPANY_TYPE_UNKNOWN],
        )
    return RuleResult(
        rule_id=rule_id,
        rule_version="1.0.0",
        rule_name=rule_name,
        status="not_applicable",
        severity="unknown",
        explanation=gate.explanation,
        quality=build_parent_scope_quality(company_type_status="excluded_financial"),
        warnings=[W_COMPANY_TYPE_FINANCIAL_EXCLUDED],
    )
