"""最终续审 §5 B3：canonical 业务术语注册表.

数据源只能是 financial_rules.yaml 的规则元数据（复用
load_financial_rules 的缓存与 mtime 失效），不新增金融词表、
不复制指标同义词到常量表。

8/23 扩展：业务追问词注册表（封闭集合）——"实际控制人是谁"
"最近有什么负面消息吗"等省略主语的业务追问，其 not_found span
（实际控制人/负面消息）需可解释为业务词才能延续历史主体，否则
防串阻断（entity_error）。业务追问词是**语义封闭**集合（业务域
名词），与用户句式开放集不同；防串依然安全：真公司名（台泥/
小米等）不在表内 → 不可解释 → 照常阻断。
"""

from __future__ import annotations

from app.domain.finance.financial_rule_config import load_financial_rules

# 语法/请求残留字符（封闭、句法性）：canonical 术语剥离后仅允许
# 这些字符残留，防止演化成业务同义词库。
_GRAMMAR_RESIDUE_CHARS = frozenset(
    "的呢吗了是有没有否会为什么如何问一下看看查查说说介绍"
)

# 8/23 业务追问词注册表（封闭集合，语义域名词）：
# 股权/治理/事件/舆情/总结等追问的高频业务名词。只收「名词性业务
# 词」，不收动词句式（"怎么样""是什么"由语法残留字符覆盖）。
_BUSINESS_QUERY_WORDS: frozenset[str] = frozenset(
    {
        # 股权/治理
        "实际控制人",
        "实控人",
        "控股股东",
        "第一大股东",
        "最大股东",
        "持股比例",
        "股权结构",
        "股权",
        "股东",
        "控制权",
        "管理层",
        "董事会",
        "高管",
        "股权质押",
        "质押",
        "减持",
        "增持",
        # 事件/舆情
        "负面消息",
        "负面新闻",
        "负面事件",
        "消息",
        "新闻",
        "公告",
        "舆情",
        "处罚",
        "立案",
        "调查",
        "风险",
        "问题",
        "异常",
        "违规",
        "造假",
        "舞弊",
        # 总结/评价
        "总结",
        "概括",
        "综述",
        "整体情况",
        "整体",
        "综合",
        "评价",
        "表现",
        "情况",
        "现状",
        "怎么样",
        "如何",
        "怎样",
        "看法",
        "意见",
    }
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

    8/23 扩展：术语 = 规则名 ∪ 业务追问词；"实际控制人"由业务追问
    词解释（延续历史主体），"台泥"不可解释（防串阻断）。
    防串保证：只要残留疑似新公司证据（如"台泥""小米"），返回 False，
    不得借此沿用旧主体。
    """
    terms = (
        canonical
        if canonical is not None
        else frozenset(canonical_business_names()) | _BUSINESS_QUERY_WORDS
    )
    remaining = text or ""
    for term in sorted(terms, key=len, reverse=True):
        remaining = remaining.replace(term, "")
    return all(ch in _GRAMMAR_RESIDUE_CHARS for ch in remaining)
