"""PlanModules — V12 §7.2. 根据用户问题确定执行计划。

混合路由（Phase D 增强）：
  1. 关键词强命中（财务/股权/事件/诊断词表）→ 确定性模块选择（保留）
  2. 关键词未命中（口语化/同义表达）→ LLM 意图识别兜底
     （structured_chat 输出 finance/equity/events 布尔）
  3. LLM 失败/超时/全 False → 全模块保守展开（不丢信息）
"""

import logging
import re
from datetime import date

from pydantic import BaseModel

from app.agents.state import AgentState, ExecutionPlan

logger = logging.getLogger(__name__)


def parse_query_period(query: str) -> tuple[date | None, str, str]:
    """从用户问题解析财报期/信息截止日（#5 期次解析，纯函数，无副作用）。

    Returns:
        (as_of, as_of_kind, requested_period_text)
        - as_of: 解析出的截止日（date）
        - as_of_kind: "report_period"=财报期（如 2025年报 → 20251231）
                      "as_of"=信息截止日（如 截至2025-09-30）
                      ""=未指定
        - requested_period_text: 用户原话中命中的期次文本（用于回答/API 展示）

    覆盖：2025年报/2025年数据/2025年度报告 → 20251231；
          2025Q1/一季报 → 20250331；半年报/中报 → 20250630；
          2025Q3/三季报 → 20250930；完整日期 / 截至日期 → 该日。
    """
    # 1) 完整日期 / 截至日期（优先：含年月日三段）
    m = re.search(
        r"(?:截至)?\s*(\d{4})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})\s*日?", query
    )
    if m:
        try:
            as_of = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:  # 非法日期（如 2月30日）→ 未指定
            return None, "", ""
        return as_of, "as_of", m.group(0).strip()

    # 2) 财报期关键词（按季度/半年度/年度；"2025年数据" 归入年度期）。
    #    支持 "2025年报" 与 "2025年年报" 两种写法（年字可选）；
    #    不用 \b——汉字与数字之间无单词边界。
    specs = (
        (r"(\d{4})\s*(?:年\s*)?(?:一季报|第1季度)", 3, 31),
        (r"(\d{4})\s*[qQ]1", 3, 31),
        (r"(\d{4})\s*(?:年\s*)?(?:半年报|中报|二季报|第2季度)", 6, 30),
        (r"(\d{4})\s*[qQ]2", 6, 30),
        (r"(\d{4})\s*(?:年\s*)?(?:三季报|第3季度)", 9, 30),
        (r"(\d{4})\s*[qQ]3", 9, 30),
        (r"(\d{4})\s*(?:年\s*)?(?:年报|年度报告|财报|数据)", 12, 31),
        (r"(\d{4})\s*[qQ]4", 12, 31),
    )
    for pat, month, day in specs:
        m = re.search(pat, query)
        if m:
            return date(int(m.group(1)), month, day), "report_period", m.group(0)
    return None, "", ""


class _IntentResult(BaseModel):
    """LLM 意图识别输出：三个业务模块是否需要执行。"""

    finance: bool = False
    equity: bool = False
    events: bool = False


# ── 关键词表 ──────────────────────────────────────────────

_FINANCE_KW = [
    "财务",
    "造假",
    "风险",
    "利润",
    "收入",
    "营收",
    "应收",
    "现金流",
    "负债",
    "存货",
    "毛利",
    "报表",
    "勾稽",
    "盈利",
    "舞弊",
    "异常",
]

_EQUITY_KW = [
    "股权",
    "股东",
    "控制",
    "穿透",
    "关联",
    "实控人",
    "持股",
]

_EVENTS_KW = [
    "事件",
    "舆情",
    "新闻",
    "公告",
    "处罚",
    "调查",
    "st",
    "立案",
]

# 综合诊断 — 命中任一词 → 展开三模块（"异常"不在此列，避免"应收异常吗"误扩）
_DIAGNOSIS_KW = [
    "造假",
    "风险",
    "舞弊",
    "是否有问题",
    "有没有问题",
]


def _llm_intent_fallback(user_query: str) -> _IntentResult | None:
    """关键词未命中时，用 LLM 识别意图；失败/超时 → None（调用方全模块兜底）。"""
    messages = [
        {
            "role": "system",
            "content": (
                "你是财报问答系统的意图识别器。判断用户问题需要哪些分析模块："
                "finance（财务指标/规则/报表）、equity（股权/股东/控制链）、"
                "events（舆情/公告/事件/评级）。"
                '输出 JSON：{"finance": bool, "equity": bool, "events": bool}。'
                "不确定或宽泛问题时全部设为 true（保守展开）。"
            ),
        },
        {"role": "user", "content": f"用户问题：{user_query}"},
    ]
    try:
        from app.agents.llm_sync import run_llm_structured

        return run_llm_structured(messages, _IntentResult)
    except Exception:  # noqa: BLE001 — 意图识别失败走全模块兜底
        logger.warning("plan_modules: LLM 意图识别失败，全模块兜底", exc_info=True)
        return None


# ── 闲聊/引导意图识别（同学反馈：输入"你好"答非所问） ──────
# 无公司问题分两类：
#   chitchat：纯寒暄（你好/谢谢/再见/你是谁…）→ 欢迎引导语
#   guide：想用但没给实体（帮我看看/推荐…）→ 引导提供公司名或代码
# 短而明确的表达走高置信快速路径；口语化和边界表达交给 LLM；
# 同一规则也作为 LLM 失败/超时时的确定性降级兜底。

# 闲聊意图词表（R8）：按语义拆分，全部"清理标点后精确匹配"，
# 防止"你好，康美药业怎么样"这类混合输入被问候词吞掉。
_GREETING_EXACT = (
    "你好",
    "您好",
    "嗨",
    "哈喽",
    "在吗",
    "早上好",
    "上午好",
    "中午好",
    "下午好",
    "晚上好",
    "hello",
    "hi",
)

_THANKS_EXACT = (
    "谢谢",
    "感谢",
    "多谢",
    "谢谢你",
    "谢谢您",
    "谢谢了",
)

_FAREWELL_EXACT = (
    "再见",
    "拜拜",
    "拜拜了",
    "回头见",
    "下次见",
)

_CAPABILITY_EXACT = (
    "你是谁",
    "你是什么",
    "能做什么",
    "你能做什么",
    "能帮我做什么",
    "你能帮我做什么",
    "会做什么",
    "你会做什么",
    "有什么用",
    "有什么功能",
    "介绍一下你",
    "介绍一下自己",
    "介绍一下",
)

_ENGLISH_GREETING_RE = re.compile(
    r"^(?:hi|hello)(?:\s+(?:there|truthnet))?[\s!,.?]*$", re.IGNORECASE
)
_CHITCHAT_INTENT_TIMEOUT_SECONDS = 5.0

_GUIDE_KW = (
    "帮我看看",
    "帮忙看看",
    "看看股票",
    "有什么推荐",
    "推荐股票",
    "怎么用",
    "怎么开始",
    "如何开始",
)

_UNSUPPORTED_KW = (
    "天气",
    "写代码",
    "编程",
    "翻译",
    "讲故事",
    "写诗",
)

# 公司事实轻量查询（R9）：只匹配明确模板，禁止裸"行业/股本"包含匹配
# （"康美药业行业研报""股本变化风险"不得误路由）。
_COMPANY_FACT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"属于什么行业|所属行业|什么行业|是什么行业"), "industry"),
    (
        re.compile(r"在哪个交易所上市|在哪个市场上市|在哪上市|上市交易所|什么交易所"),
        "exchange",
    ),
    (re.compile(r"上市日期|上市时间|什么时候上市|何时上市"), "listing_date"),
    (re.compile(r"企业类型|公司类型|是什么类型|什么企业类型"), "comp_type"),
    (re.compile(r"主营业务|主要业务|是做什么的|做什么的|主营产品"), "business"),
    (re.compile(r"总股本|股本总额"), "total_shares"),
]

_COMPANY_FACT_TEMPLATES = (
    "属于什么行业",
    "所属行业",
    "在哪个交易所上市",
    "上市日期",
    "企业类型",
    "公司类型",
    "主营业务",
    "总股本",
    "股本总额",
)

_UNSUPPORTED_INDICATOR_PATTERNS = (
    "应收账款周转率",
    "存货周转率",
    "总资产周转率",
)
_INDICATOR_PATTERNS: list[tuple[str, str]] = [
    ("资产负债率", "debt_to_assets"),
    ("应收账款余额", "accounts_receivable"),
    ("应收账款", "accounts_receivable"),
    ("经营活动现金流", "operating_cash_flow"),
    ("经营现金流", "operating_cash_flow"),
    ("营业收入", "operating_revenue"),
    ("总资产", "total_assets"),
    ("总负债", "total_liabilities"),
    ("净利润", "net_profit"),
    ("存货", "inventories"),
]
_INDICATOR_DIAGNOSIS_CUES = (
    "分析",
    "风险",
    "造假",
    "舞弊",
    "异常",
    "诊断",
    "有问题",
)

_ANALYSIS_CUES = (
    "分析",
    "财务",
    "报表",
    "营收",
    "利润",
    "现金流",
    "存货",
    "应收",
    "股权",
    "股东",
    "实控人",
    "公告",
    "评级",
    "舆情",
    "风险",
    "造假",
    "舞弊",
    "研报",
    "行业",
    "公司",
)

_RESEARCH_CUES = ("研报", "行业", "板块", "观点")
_CONTEXT_CUES = ("它", "该公司", "这家公司", "继续", "再看", "刚才", "前面")


class _ChitchatResult(BaseModel):
    """无公司问题的意图分类（LLM 结构化输出）。"""

    intent: str = "analysis"  # chitchat / guide / analysis / research / unsupported


def _chitchat_messages(user_query: str) -> list[dict]:
    """闲聊意图识别的提示词（LLM 主路径）。"""
    return [
        {
            "role": "system",
            "content": (
                "你是财报问答系统的意图识别器。用户问题未包含公司名称，"
                "请判断其真实意图，输出 JSON："
                '{"intent": "chitchat" | "guide" | "analysis" | "research" | "unsupported"}。'
                "- chitchat：纯寒暄/问候/感谢/闲聊/自我介绍询问"
                '（如"你好""在吗""你是谁""谢谢""随便聊聊"）；'
                "- guide：想进行分析但没提供公司或实体"
                '（如"帮我看看股票""推荐一只股票""怎么用"）；'
                '- research：行业/研报/观点类查询（如"白酒行业近期观点"）；'
                "- analysis：需要分析具体公司，但公司名称可能缺失或未识别；"
                "- unsupported：与上市公司财务、股权、公告或行业研报无关的问题"
                "（如天气、翻译、写代码）。"
                '注意：问候语后跟真实查询（如"你好，分析康美药业"）属于'
                "analysis 而不是 chitchat，不要因为出现问候词就分类为闲聊。"
            ),
        },
        {"role": "user", "content": f"用户问题：{user_query}"},
    ]


def _strip_punct(s: str) -> str:
    """清理中文/英文标点与空白，用于问候词精确匹配。"""
    return re.sub(r"[，。！？、,.!?;\s]+", "", s)


def detect_company_fact(user_query: str) -> str | None:
    """公司事实查询精确模板匹配（R9，纯函数）。

    只命中明确模板（属于什么行业/在哪个交易所上市/上市日期/企业类型/
    主营业务/总股本等），返回 fact_key；无命中返回 None。
    不匹配裸"行业""股本"（避免误路由"行业研报""股本变化风险"）。
    """
    ql = user_query or ""
    for pattern, key in _COMPANY_FACT_PATTERNS:
        if pattern.search(ql):
            return key
    return None


def detect_indicator(user_query: str) -> str | None:
    """识别可确定性短答的基础财务指标（Phase D #3A）。"""
    query = user_query or ""
    if any(cue in query for cue in _INDICATOR_DIAGNOSIS_CUES):
        return None
    if any(pattern in query for pattern in _UNSUPPORTED_INDICATOR_PATTERNS):
        return "unsupported"
    for pattern, indicator in _INDICATOR_PATTERNS:
        if pattern in query:
            return indicator
    return None


def detect_chitchat_intent(user_query: str) -> str | None:
    """高置信寒暄/引导识别（LLM 失败兜底，纯函数）。

    Returns:
        chitchat / guide / unsupported / None（正常或需 LLM 判断）

    R8 规则：
      1. unsupported（天气等）先于闲聊宽松判定；
      2. 问候/感谢/道别/能力询问 = 清理标点后"精确匹配"（fullmatch），
         "你好，康美药业怎么样"清理后 ≠ 任何问候词 → 不判闲聊，交实体解析；
      3. 业务分析信号（_ANALYSIS_CUES / 6 位代码）始终返回 None。
    """
    ql = (user_query or "").lower().strip()
    if not ql:
        return "chitchat"  # 空问题按寒暄引导

    # 范围外问题（天气/编程/翻译等）先于问候宽松判定：
    # "你好，今天天气怎么样"应归 unsupported，而非被"你好"抢先为 chitchat。
    if any(kw in ql for kw in _UNSUPPORTED_KW):
        return "unsupported"

    # 无实体荐股/使用请求优先归 guide；系统只分析用户指定的公司，不荐股。
    if any(kw in ql for kw in _GUIDE_KW) and not any(
        cue in ql for cue in _ANALYSIS_CUES if cue not in ("公司",)
    ):
        return "guide"

    # 问候后跟真实查询时绝不按闲聊处理。
    if any(cue in ql for cue in _ANALYSIS_CUES) or re.search(r"\d{6}", ql):
        return None

    # 精确匹配（清理标点后全文相等）——混合输入不命中
    ql_clean = _strip_punct(ql)
    # 剥离句末语气词（你好呀/谢谢啦）后仍按精确词匹配，避免缩窄词表
    for particle in ("呀", "啊", "哦", "呢", "啦", "嘛", "吧"):
        if ql_clean.endswith(particle):
            ql_clean = ql_clean[: -len(particle)]
            break
    if (
        ql_clean in _GREETING_EXACT
        or ql_clean in _THANKS_EXACT
        or ql_clean in _FAREWELL_EXACT
        # 英文问候用未剥离标点的原文匹配（"hi there!" 含空格）
        or _ENGLISH_GREETING_RE.fullmatch(ql)
    ):
        return "chitchat"
    if ql_clean in _CAPABILITY_EXACT:
        return "chitchat"  # "你是谁/能做什么" → 能力引导
    return None


def _detect_chitchat_with_llm(user_query: str) -> str | None:
    """LLM 意图识别；保留所有合法分类，失败/非法时返回 None。"""
    try:
        from app.agents.llm_sync import run_llm_structured

        result = run_llm_structured(
            _chitchat_messages(user_query),
            _ChitchatResult,
            timeout=_CHITCHAT_INTENT_TIMEOUT_SECONDS,
        )
        if result is not None and result.intent in (
            "chitchat",
            "guide",
            "analysis",
            "research",
            "unsupported",
        ):
            return result.intent
    except Exception:  # noqa: BLE001 — LLM 失败走关键词兜底，不阻塞
        logger.warning("plan_modules: 闲聊意图 LLM 识别失败，关键词兜底", exc_info=True)
    return None


def _fallback_no_company_intent(user_query: str) -> str | None:
    """LLM 失败后的无实体语义兜底，不重新覆盖成功的 LLM 判定。"""
    ql = (user_query or "").lower()
    if any(cue in ql for cue in _RESEARCH_CUES):
        return "research"
    if any(cue in ql for cue in _ANALYSIS_CUES) or any(
        cue in ql for cue in _CONTEXT_CUES
    ):
        return "guide"
    return None


def plan_modules_node(state: AgentState) -> dict:
    user_query = state.get("user_query", "")

    # #5 期次解析：必须在 company 判断之前执行（行业研报查询同样需要截止日）
    as_of, as_of_kind, period_text = parse_query_period(user_query)
    request_context = state.get("request_context")
    if request_context is not None and request_context.as_of is not None:
        as_of = request_context.as_of
        as_of_kind = request_context.as_of_kind or "as_of"
        period_text = request_context.requested_period_text

    company = state.get("company")

    # P2-2：多公司比较引导——comparison_requested 标志恒 True 时即进入
    # comparison_guide（0/1/≥2 家候选都算），不复用 company_disambiguation 的
    # "请选择一家"文案；文案差异由 generate_answer 按候选数处理。
    comparison_targets = state.get("comparison_targets") or []
    if state.get("comparison_requested") or len(comparison_targets) >= 2:
        return {
            "plan": ExecutionPlan(
                intent="comparison_guide",
                requested_modules=[],
                cross_checks=[],
                as_of=as_of,
                as_of_kind=as_of_kind,
                requested_period_text=period_text,
            )
        }

    # R9：公司事实轻量查询——只匹配明确模板（属于什么行业/上市日期等），
    # 直接进 generate_answer，不执行 finance/equity/events/risk。
    if company is not None:
        indicator = detect_indicator(user_query)
        if indicator:
            return {
                "plan": ExecutionPlan(
                    intent="indicator",
                    requested_modules=[],
                    cross_checks=[],
                    indicator=indicator,
                    as_of=as_of,
                    as_of_kind=as_of_kind,
                    requested_period_text=period_text,
                )
            }

        fact_key = detect_company_fact(user_query)
        if fact_key:
            return {
                "plan": ExecutionPlan(
                    intent="company_fact",
                    requested_modules=[],
                    cross_checks=[],
                    fact_key=fact_key,
                    as_of=as_of,
                    as_of_kind=as_of_kind,
                    requested_period_text=period_text,
                )
            }

    if company is None:
        if state.get("company_candidates"):
            return {
                "plan": ExecutionPlan(
                    intent="company_disambiguation",
                    requested_modules=[],
                    cross_checks=[],
                    as_of=as_of,
                    as_of_kind=as_of_kind,
                    requested_period_text=period_text,
                )
            }
        # 短而明确的寒暄/引导走快速路径；口语化和边界表达交给 LLM。
        # LLM 失败后再用同一高置信规则兜底，绝不阻塞正常查询。
        detected = detect_chitchat_intent(user_query)
        if detected is None:
            detected = _detect_chitchat_with_llm(user_query)
        if detected is None:
            detected = _fallback_no_company_intent(user_query)
        if detected == "analysis":
            # 已确认是公司分析诉求但实体缺失，转为可执行引导。
            detected = "guide"
        return {
            "plan": ExecutionPlan(
                intent=detected or "simple_query",
                requested_modules=[],
                cross_checks=[],
                as_of=as_of,
                as_of_kind=as_of_kind,
                requested_period_text=period_text,
            )
        }

    ql = user_query.lower()

    need_finance = any(kw in ql for kw in _FINANCE_KW)
    need_equity = any(kw in ql for kw in _EQUITY_KW)
    need_events = any(kw in ql for kw in _EVENTS_KW)

    # 综合诊断 → 展开全部模块
    if any(kw in ql for kw in _DIAGNOSIS_KW):
        need_finance = need_equity = need_events = True

    # 关键词未命中 → LLM 语义识别兜底（口语化/同义表达）
    if not need_finance and not need_equity and not need_events:
        intent = _llm_intent_fallback(user_query)
        if intent is not None:
            need_finance = intent.finance
            need_equity = intent.equity
            need_events = intent.events
        # intent 为 None（LLM 失败）或全 False → 走下方全模块兜底

    # 宽泛问题/LLM 未识别 → 默认全模块
    if not need_finance and not need_equity and not need_events:
        need_finance = need_equity = need_events = True

    modules = []
    if need_finance:
        modules.append("finance")
    if need_equity:
        modules.append("equity")
    if need_events:
        modules.append("events")

    cross_checks = []
    if need_equity and need_events:
        cross_checks.append("equity_vs_events")
    if need_finance and len(modules) >= 2:
        cross_checks.append("financial_vs_cashflow")

    return {
        "plan": ExecutionPlan(
            intent="diagnose" if len(modules) >= 2 else "simple_query",
            requested_modules=modules,
            cross_checks=cross_checks,
            as_of=as_of,
            as_of_kind=as_of_kind,
            requested_period_text=period_text,
        )
    }
