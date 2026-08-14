"""最终续审 §5 B3：canonical 业务术语注册表.

数据源只能是 financial_rules.yaml 的规则元数据（复用
load_financial_rules 的缓存与 mtime 失效），不新增金融词表、
不复制指标同义词到常量表。
"""

from __future__ import annotations

from app.domain.finance.financial_rule_config import load_financial_rules

# 语法/请求残留字符（封闭、句法性）：canonical 术语剥离后仅允许
# 这些字符残留，防止演化成业务同义词库。
_GRAMMAR_RESIDUE_CHARS = frozenset(
    "的呢吗了是有没有否会为什么如何问一下看看查查说说介绍"
)


def canonical_business_names() -> frozenset[str]:
    """规则 canonical name 集合（如 R3=存贷双高）。

    加载失败（yaml 缺失/校验错误）返回空集——不阻断主流程，
    只是不提供 context 解释。
    """
    try:
        config = load_financial_rules()
    except Exception:  # noqa: BLE001 — registry 失败降级为空集
        return frozenset()
    return frozenset(str(meta.name) for meta in config.metadata.values() if meta.name)


def explainable_as_canonical_context(
    text: str, canonical: frozenset[str] | None = None
) -> bool:
    """文本是否可完全由已知业务术语 + 有限语法字符解释。

    防串保证：只要残留疑似新公司证据（如"台泥""小米"），返回 False，
    不得借此沿用旧主体。
    """
    terms = canonical if canonical is not None else canonical_business_names()
    remaining = text or ""
    for term in sorted(terms, key=len, reverse=True):
        remaining = remaining.replace(term, "")
    return all(ch in _GRAMMAR_RESIDUE_CHARS for ch in remaining)
