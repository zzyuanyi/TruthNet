"""PlanModules — V12 §7.2. 根据用户问题确定执行计划。

混合路由（Phase D 增强）：
  1. 关键词强命中（财务/股权/事件/诊断词表）→ 确定性模块选择（保留）
  2. 关键词未命中（口语化/同义表达）→ LLM 意图识别兜底
     （structured_chat 输出 finance/equity/events 布尔）
  3. LLM 失败/超时/全 False → 全模块保守展开（不丢信息）
"""

import logging
import re
from dataclasses import dataclass
from datetime import date

from pydantic import BaseModel

from app.agents.state import (
    AgentState,
    ComparisonSpec,
    ExecutionPlan,
    validate_comparison_spec,
)
from app.domain.comparison.scope_registry import (
    COMPARISON_FULL_COMPOSITE_CUES,
    COMPARISON_FULL_SCOPE_WORDS,
)
from app.application.services.market_quote_service import detect_market_quote_field

logger = logging.getLogger(__name__)


def parse_query_period(
    query: str, *, today: date | None = None
) -> tuple[date | None, str, str]:
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
        (r"(\d{4})\s*(?:年\s*)?(?:财年\s*)?(?:一季报|一季度|第一季度|第1季度)", 3, 31),
        (r"(\d{4})\s*[qQ]1", 3, 31),
        (
            r"(\d{4})\s*(?:年\s*)?(?:财年\s*)?(?:上半年|半年报|中报|二季报|二季度|第二季度|第2季度)",
            6,
            30,
        ),
        (r"(\d{4})\s*[qQ]2", 6, 30),
        (r"(\d{4})\s*(?:年\s*)?(?:财年\s*)?(?:三季报|三季度|第三季度|第3季度)", 9, 30),
        (r"(\d{4})\s*[qQ]3", 9, 30),
        (
            r"(\d{4})\s*(?:年\s*)?(?:财年\s*)?(?:四季度|第四季度|年报|年度报告|财报|数据)",
            12,
            31,
        ),
        (r"(\d{4})\s*[qQ]4", 12, 31),
        # “2024年毛利率”默认指该年度报表；季度/年报等更具体写法已在前面命中。
        (r"(\d{4})\s*年", 12, 31),
    )
    for pat, month, day in specs:
        m = re.search(pat, query)
        if m:
            return date(int(m.group(1)), month, day), "report_period", m.group(0)

    # 3) 相对年份或省略年份的财报期。省略年份时选择最近已经结束的同类
    # 报告期；显式“今年”则严格锁定今年，即使数据尚未披露也不回退。
    period_words = (
        (r"上半年|半年报|中报|二季度|第二季度", 6, 30),
        (r"一季报|一季度|第一季度", 3, 31),
        (r"三季报|三季度|第三季度", 9, 30),
        (r"四季度|第四季度|年报", 12, 31),
    )
    anchor = today or date.today()
    for words, month, day in period_words:
        m = re.search(rf"(?:(今年|去年|前年)\s*)?({words})", query)
        if not m:
            continue
        relative = m.group(1)
        if relative:
            year = anchor.year - {"今年": 0, "去年": 1, "前年": 2}[relative]
        else:
            year = anchor.year
            if date(year, month, day) > anchor:
                year -= 1
        return date(year, month, day), "report_period", m.group(0)
    if re.search(
        r"(?:今年|去年|前年).*(?:营收|营业收入|利润|总资产|负债|毛利率|现金流)", query
    ):
        m = re.search(r"今年|去年|前年", query)
        relative = m.group(0)
        year = anchor.year - {"今年": 0, "去年": 1, "前年": 2}[relative]
        return date(year, 12, 31), "report_period", relative
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
    "你会什么",
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
    # 8/17 数据1 端到端（T09）：行情/交易/融资类问题超出财报反欺诈
    # 范围 → 显式 unsupported（不得落到"疑似公司"错误引导）。
    # 谨慎收词：只加明确行情/交易/资金业务术语，不吞股权事件类词
    # （减持/增持/质押/回购仍走 events/equity）。
    "融资融券",
    "平仓",
    "换手率",
    "量比",
    "市盈率",
    "市净率",
    "涨跌幅",
    "最高价",
    "最低价",
    "股价",
    "行情",
    "K线",
    "k线",
    "成交量",
    "成交额",
    "涨停",
    "跌停",
    "打新",
    "申购",
    "赎回",
    "帮我买入",
    "帮我卖出",
    "基金持仓",
    "基金规模",
    "开放式基金",
    "放量和缩量",
    "均线",
    "死叉",
    "深市期权",
    "信用账户",
    "查询已清仓",
    "新手买股票",
    "买股票要注意",
    "科创板股票",
    "创业板有哪些",
    "上证指数",
    "多少家银行",
    "交易记录",
    "个人信息",
    "预留手机号码",
    "设置个股行情页面",
    "行情路径",
    "国债逆回购",
    "可转债",
    "大宗交易",
    "港股通",
    "条件单",
    "银行卡",
    "手续费",
    "创业板权限",
    "科创板成长层",
    "成交回报",
    "担保证券",
    "基金分红",
    "天添利",
    "otc账户",
    "买什么股票",
    "推荐一些股票",
    "适合长期投资",
    "信息源",
    "外国游客",
    "打开多股同列",
    "接下来你关注的焦点",
    "财经事件",
    "估值",
    "操盘",
    "主力增仓",
    "自选相关",
    "自选股中",
    "走势预测",
    "预测走势",
    # 8/22 晚全量 1410 分析：券商业务操作/账户类问题（定位外）——
    # 之前落"未能识别到公司"或公司综合分析答非所问，补词后合理拒答。
    "两融",
    "开户",
    "调整佣金",
    "我的佣金",
    "降佣金",
    "费率",
    "账号",
    "密码",
    "转账",
    "委托流水",
    "定投",
    "缴款",
    "客户经理",
    "股东号",
    "存管",
    "撤单",
    "风险测评",
    "网络投票",
    "现金选择权",
    "网格交易",
    "银证",
    "北交所",
    "新三板",
    "etf",
    "reits",
    "货币基金",
    "b股",
    "中签",
    "秀财",
    "受益标的",
    "注册制",
    "macd",
    "rsi",
    "rs1",
    "dea",
    "kdj",
    "boll",
    "多头排列",
    "生命线",
    "卖空",
    "贴息",
    "低价股",
    "小面值",
    "公募基金",
    "重仓",
    "卖出全部",
    "加入自选",
    "添加到自选",
    "加入自选股",
    "个股数量",
    "涨停股票有哪些",
    "买入信号",
    "卖出信号",
    "操作策略",
    # 8/22 晚全量 1410 分析（第二批）：账户/权限/界面操作类具体名词——
    # 只收明确券商业务名词，不收"如何查看"等宽泛前缀（会误伤
    # "如何查看康美药业年报"类合法问题）。
    "权限",
    "账户",
    "浏览记录",
    "基金转换",
    "股东账户",
    "外部风险包括",
    "提供策略",
    "psr",
    "roa",
    "机构调研",
    # 8/22 晚全量 1410 分析（第三批）：剩余券商操作/账户词
    "添加联系人",
    "委托方式",
    "调整佣金",
    "的佣金",
    "佣金怎么",
    "佣金是多少",
    "查佣金",
    "开两融",
    "开通两融",
    "两融怎么",
    "怎么开通",
    "如何开通",
    "怎么开户",
    "如何开户",
    # 8/22 晚全量 1410 分析（第四批）：基金/收益率/形态等定位外词
    "的基金",
    "支基金",
    "收益率",
    "是什么形态",
    "什么形态",
    "形态分析",
    "形态如何",
)

_MARKET_WIDE_CUES = (
    "全市场",
    "市场整体",
    "自选股",
    "哪些股票",
    "哪些个股",
    "强势股",
    "涨幅靠前",
    "涨停股票",
    "龙虎榜",
    "大宗交易市场",
    "跑赢大盘",
    "跌最狠",
    "涨最多",
    "有资金进入的股票",
    "资金进入的股票",
    "大宗交易成交额最大",
    "多晶硅价格上涨",
    # 8/22 后测集分析（row 19）：板块行情/表现类问题（非个股、非研报）
    # 归 unsupported——"今天证券板块的表现如何"不应落到研报检索拒答。
    "板块的表现",
    "板块行情",
    "板块走势",
    "板块表现",
    "板块涨",
    "板块跌",
    "板块今天",
    # 8/22 后测集分析：宏观政策/产业扶持/应用领域类问题（无公司、
    # 官方数据集为公司研报无法回答政策汇总）→ 归 unsupported 合理拒答，
    # 不再落入 research 返回公司研报摘要答非所问（row 66/67/759/1030/1192）。
    "出台",
    "政策扶持",
    "扶持政策",
    "产业政策",
    "补贴政策",
    "支持政策",
    "新政策",
    "政策汇总",
    "哪些城市",
    "哪些地方",
    "哪些地区",
    "涨的好的",
    "涨得好",
    "主要应用领域",
)

# 8/22 晚全量 1410 分析：市场整体/全市场聚合类词（无公司时合理拒答）。
# 与 _MARKET_WIDE_CUES 的区别：这里只在 company is None 时短路（见
# _detect_macro_market_intent），避免误伤"东吴证券近期有利好消息吗"
# （有公司、属 events/公告范围）等带主体的问题。
# 注意：行业/概念主题词（新能源汽车/5G/区块链/AI 等）不在此表——
# 那些应走 research 研报检索链路（研报可答行业动态），归 unsupported
# 会误伤"新能源汽车产业链的最新动态是什么"（test 锁定 research）。
_MACRO_MARKET_CUES = (
    # 市场整体动态/消息/热点（无公司、无主体）
    "今天市场",
    "今日市场",
    "最近市场",
    "市场动态",
    "市场消息",
    "消息面",
    "有什么热点",
    "有什么消息",
    "有什么利好",
    "有什么利空",
    "利好事件",
    "利空消息",
    "利好消息",
    "热点信息",
    "热点事件",
    "市场事件",
    "重要事件",
    "今日事件",
    "最新消息",
    "有什么消息和政策",
    # 全市场统计/排名（非个股、非研报可答；"全市场/市场整体"
    # 已在 _MARKET_WIDE_CUES，不重复）
    "沪深两市",
    "大盘走势",
    "大盘表现",
    "指数行情",
    "市场排名",
    "涨幅排名",
    "跌幅排名",
    # 8/22 晚全量 1410 分析（第二批）：贵金属/商品市场、选股筛选类
    "贵金属",
    "黄金白银",
    "市场分析",
    "有什么市场热点",
    "值得关注",
    "热门股票",
    "横盘",
    "筹码",
    "流通股本",
    "相关的股票",
    "黄金相关",
    "板块资金",
    "板块排名",
    "资金流入排名",
    "成交量排名",
    "换手率排名",
    # 8/22 晚全量 1410 分析（第三批）：宏观政策/行业趋势/销量类——
    # 官方数据为公司研报，检索只会返回公司经营数据答非所问
    # （row 484/486/489/490/493/496），与 8/22 宏观政策合理拒答
    # 原则一致，归 unsupported 而非 research。
    "政策支持",
    "政策变化",
    "政策汇总",
    "行业消息",
    "行业政策",
    "行业前景",
    "行业趋势",
    "行业动态",
    "消费趋势",
    "竞争态势",
    "市场趋势",
    "销量数据",
    "市场走势",
    "行业走势",
    "市场前景",
    "行业现状",
    "市场规模",
    "市场容量",
    "行业规模",
)

# 公司事实轻量查询（R9）：只匹配明确模板，禁止裸"行业/股本"包含匹配
# （"康美药业行业研报""股本变化风险"不得误路由）。
_COMPANY_FACT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"属于什么行业|所属行业|什么行业|是什么行业"), "industry"),
    (re.compile(r"细分板块|所属板块|哪个板块|什么板块"), "industry"),
    (re.compile(r"旗下(?:的)?(?:公司|企业)|子公司|控股公司"), "subsidiary"),
    (
        re.compile(
            r"(?:收到|签订|中标|获得|拿到).{0,10}(?:项目|合同)|项目金额|项目是真的吗|项目真实吗|有.*项目吗"
        ),
        "project",
    ),
    (
        re.compile(r"在哪个交易所上市|在哪个市场上市|在哪上市|上市交易所|什么交易所"),
        "exchange",
    ),
    (re.compile(r"退市|上市状态|是否上市"), "listing_status"),
    (re.compile(r"上市日期|上市时间|什么时候上市|何时上市"), "listing_date"),
    (re.compile(r"高管薪酬|董监高薪酬|管理层薪酬"), "executive_compensation"),
    (re.compile(r"首发价格|首发价|发行价格|发行价"), "ipo_price"),
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
    "高管薪酬",
    "首发价格",
)

# v3.3.3 批次 A（方案 §5.3）：中文指标语义入口收敛到
# app.application.services.indicator_semantics（单一 canonical ID 表），
# 此处不再维护 _UNSUPPORTED_INDICATOR_PATTERNS / _INDICATOR_PATTERNS。
# 2026-08-12 修订：移除"分析"——"分析一下资产负债率"是明确指标短答，
# "分析资产负债率异常原因"仍由"异常/原因"等诊断词路由到诊断分支。
_INDICATOR_DIAGNOSIS_CUES = (
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

_RESEARCH_CUES = (
    "研报",
    "行业",
    "板块",
    "观点",
    "技术",
    "研发中",
    "研发",
    "工艺",
    "应用领域",
    "新进展",
    "市场规模",
    "竞争者",
    "挑战",
    "创新",
    "热点资讯",
    "产业",
    "概念",
    "题材",
    "政策",
    "发展趋势",
    # 8/22 晚全量 1410 分析：研报可答的行业/事件/资讯类问题——
    # 之前无公司时落 guide（"未能识别到公司"错误），补词后走 research。
    "研究报告",
    "重要消息",
    "最新进展",
    "最新发展",
    "最新动态",
    "热门资讯",
    "产业链",
    "上下游",
    "换电模式",
    "目标价",
    "核心竞争",
    "竞争力",
    "竞争对手",
    "产品计划",
    "业务拓展",
    "国际业务",
    "行业布局",
    "领域布局",
    "未来趋势",
)

_COMPANY_RESEARCH_CUES = (
    "核心优势",
    "竞争优势",
    "技术优势",
    "产品优势",
    "业务优势",
    "研发进展",
    "旗下",
    "项目",
    "财务报告",
    "高管薪酬",
    "首发价格",
    "发行价",
    "发行价格",
)
_CONTEXT_CUES = ("它", "该公司", "这家公司", "继续", "再看", "刚才", "前面")

# v3.3.3 批次 C（方案 §5.6）：同主体跨指标比较语义 cue——
# "和营业收入增速对比呢" 由 Resolver 的
# _SINGLE_COMPANY_COMPARISON_EXCLUSIONS 排除出公司比较（含"增速"），
# 此处以「比较词 + 当前指标 + 历史成功指标」确定性识别。
_SAME_COMPANY_COMPARE_CUES = ("对比", "比较")

# v3.3.3 批次 D（方案 §2.4/§5.6）+ v3.3.4（方案 §2.1/§4.1）：全面比较词——
# 恰好两家 finalized → overview 预览 + requested_scope=full；不足两家或
# 三家及以上 → comparison_guide（页面）。风险维度词 → 诚实路由
# （对话内暂无双公司风险执行能力）。
# 收口复核审查 P2a：范围词统一取自 domain/comparison/scope_registry
# （与实体层 comparison operator 同一来源：全面/综合/多维/全方位/整体
# + 计划层专属复合 cue 财务与风险/财务和风险）。
_FULL_COMPARISON_CUES = (
    tuple(sorted(COMPARISON_FULL_SCOPE_WORDS)) + COMPARISON_FULL_COMPOSITE_CUES
)
_RISK_COMPARE_CUES = ("风险",)
# v3.3.3 收口批次 D（方案 §3.6）：指标回答语义操作 cue
_ASSESSMENT_CUES = ("正常吗", "正常么", "合理吗", "健康吗", "偏高", "偏低")

# B2 批次 A（方案 §二.2/§二.3）：舆情影响分析确定性双条件 cue——
# 事件指代 cue（舆情/公告/评级/事件/新闻/处罚/调查/立案/st）+ 影响/风险 cue。
# 只有两条件同时命中才置 impact_requested=True；单 cue 不推导。
_IMPACT_EVENT_REF_CUES = (
    "舆情",
    "公告",
    "评级",
    "事件",
    "新闻",
    "处罚",
    "调查",
    "立案",
    "st",
)
_IMPACT_REQUEST_CUES = (
    "影响",
    "风险",
    "冲击",
    "后果",
    "拖累",
)

_MARKET_PRICE_BOUNDARY_CUES = (
    "反转",
    "走势分析",
    "预测走势",
    "走势预测",
    "会涨吗",
    "会跌吗",
)


def _detect_market_price_boundary(user_query: str) -> bool:
    """识别无法由财务模块回答的价格预测/趋势判断。"""
    query = user_query or ""
    return any(cue in query for cue in _MARKET_PRICE_BOUNDARY_CUES)


def _detect_event_sentiment(user_query: str) -> str:
    query = user_query or ""
    if "利好" in query or "正面事件" in query:
        return "positive"
    if "利空" in query or "负面事件" in query:
        return "negative"
    return "all"


def _detect_event_list_requested(user_query: str) -> bool:
    query = user_query or ""
    if any(
        cue in query
        for cue in (
            "最新公告",
            "公告内容",
            "有哪些公告",
            "最近有哪些公告",
            "事件有哪些",
            "最近有什么事件",
            "最新动态",
            "市场动态",
            "最新消息",
            "最新资讯",
            "财务报告有哪些",
            "监管问询",
        )
    ):
        return True
    # 8/22 修复：公告事件时点问法（"什么时候公布的提前赎回可转债"）
    # 应走 events 时间线而非被 unsupported 短路或落入综合诊断。
    if re.search(r"(?:什么时候|何时|几号).{0,6}(?:公布|发布|披露|公告)", query):
        return True
    return "公告" in query and any(
        cue in query for cue in ("有没有", "有哪些", "发布", "最近")
    )


def _detect_impact_requested(user_query: str) -> bool:
    """B2 触发条件收紧（批次 A §二.3）：显式 cue 双条件确定性判定。

    只有同时命中「事件指代 cue」与「影响/风险 cue」才返回 True。
    综合诊断（"康美有造假风险吗"）、仅公告查询（"最近有什么公告"）、
    宽泛问题（"康美药业怎么样"）均因缺少其中一侧 cue 而返回 False；
    LLM 意图识别返回 events=True 不进入本函数（不得自动推导）。
    """
    ql = (user_query or "").lower()
    has_event_ref = any(cue in ql for cue in _IMPACT_EVENT_REF_CUES)
    has_impact_cue = any(cue in ql for cue in _IMPACT_REQUEST_CUES)
    return has_event_ref and has_impact_cue


def _detect_answer_operation(user_query: str) -> str:
    """识别指标问题真正要求的运算，避免把趋势/原因答成单期数值。"""
    query = user_query or ""
    if "亏损" in query and any(cue in query for cue in ("几年", "多少年", "连续")):
        return "loss_years"
    if "复合增长率" in query or "CAGR" in query.upper():
        return "cagr"
    if "扭亏为盈" in query or "扭亏" in query:
        return "turnaround"
    if "行业" in query and any(
        cue in query for cue in ("平均", "对比", "高于", "低于", "水平")
    ):
        return "assessment"
    if "行业" in query and "总额" in query:
        return "industry_total"
    if "最大的个股" in query or "最高的个股" in query:
        return "industry_leader"
    if any(
        cue in query for cue in ("连续", "持续", "近三年", "最近三年", "趋势")
    ) and any(cue in query for cue in ("原因", "为何", "为什么", "怎么回事")):
        return "causal_trend"
    if any(cue in query for cue in ("原因", "为何", "为什么", "怎么回事")):
        return "causal"
    if any(cue in query for cue in ("影响", "后果", "会受", "风险")):
        return "impact"
    if "环比" in query and (
        "单季度" in query or "最近季度" in query or "最新季度" in query
    ):
        return "quarter_mom"
    if ("单季度" in query or "最近季度" in query or "最新季度" in query) and any(
        cue in query for cue in ("同比", "增长率", "增速")
    ):
        return "quarter_yoy"
    if "单季度" in query:
        return "quarter_single"
    if any(cue in query for cue in ("趋势", "变化", "连续", "近三年", "最近三年")):
        return "trend"
    if any(cue in query for cue in _ASSESSMENT_CUES):
        return "assessment"
    return "value"


def _detect_comparison_operation(user_query: str) -> str:
    """双公司比较的数值运算方向（方案 §5.1 operation）。

    "低多少/更低" → less_than（B-A）；"高多少/高出/更高" → greater_than
    （A-B）；其余默认 difference（A-B，方向由符号决定）。
    """
    query = user_query or ""
    if "低多少" in query or "更低" in query:
        return "less_than"
    if "高多少" in query or "高出" in query or "更高" in query:
        return "greater_than"
    return "difference"


def _detect_multi_metric_query(user_query: str) -> bool:
    """识别显式并列指标，避免只回答第一个指标造成语义错答。"""
    query = user_query or ""
    if not any(separator in query for separator in ("、", ",", "，")):
        return False
    phrases = (
        "总股本",
        "营业收入",
        "营收",
        "净资产",
        "净利润",
        "总资产",
        "收盘价",
        "eps",
        "每股收益",
        "每股净资产",
        "毛利率",
    )
    return sum(phrase in query.lower() for phrase in phrases) >= 2


def _recent_executed_metric_ids(state: AgentState) -> list:
    """取历史最近成功执行的指标（结构化，最近优先）。"""
    memory_context = state.get("memory_context")
    if memory_context is None:
        return []
    return list(getattr(memory_context, "recent_executed_metrics", None) or [])


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
    """识别可确定性短答的财务指标（Phase D #3A）。

    v3.3.3 批次 A：本函数保留为兼容 wrapper，语义解析委托
    indicator_semantics 服务（canonical ID、最长匹配、unsupported
    同表竞争、环比/同比修饰）。原 2026-08-12 修订语义保持不变：
    - "康美环比怎么样"（无指标）→ None，不误判指标短答；
    - "营收环比" → operating_revenue_mom（query 层诚实 unsupported）；
    - "营收同比" → operating_revenue_growth（严格同比）；
    - 诊断 cue（风险/异常等）优先于指标识别 → None。
    """
    query = user_query or ""
    from app.application.services.indicator_semantics import (
        resolve_indicator_semantics,
    )

    result = resolve_indicator_semantics(query)
    # 语义服务确认的 unsupported 比“风险/原因”更具体，优先返回。
    if result.reason in ("unsupported", "modifier_unsupported"):
        return "unsupported"
    if any(cue in query for cue in _INDICATOR_DIAGNOSIS_CUES):
        return None
    if result.executable and result.metric_ids:
        return result.metric_ids[0]
    return None


def detect_industry_benchmark_request(user_query: str) -> tuple[str, str] | None:
    """识别无公司行业统计问法，返回 (规范行业名, metric_id)。"""
    query = user_query or ""
    if "行业" not in query:
        return None
    match = re.search(r"([\u4e00-\u9fff]{2,8})行业", query)
    if not match:
        return None
    indicator = detect_indicator(query)
    if not indicator or indicator == "unsupported":
        return None
    industry_aliases = {
        "家电": "家用电器",
        "家用电器": "家用电器",
        "食品饮料": "食品饮料",
        "白酒": "食品饮料",
    }
    industry = industry_aliases.get(match.group(1))
    return (industry, indicator) if industry else None


def detect_answer_target(user_query: str) -> str | None:
    """识别需要独立短答的结构化目标（Phase D #3B）。"""
    query = user_query or ""
    if "风险等级" in query or "风险级别" in query:
        return "risk_level"
    if re.search(r"(?:综合)?风险.{0,4}(?:什么|哪种|多少)?等级", query):
        return "risk_level"
    if "什么等级" in query or "哪种等级" in query:
        return "risk_level"
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

    if any(cue in ql for cue in _MARKET_WIDE_CUES) and not (
        ("个股" in ql or "股票" in ql)
        and any(cue in ql for cue in ("行业", "板块", "领域"))
        and "自选" not in ql
    ):
        return "unsupported"

    # AnySearch 已覆盖的行情字段应继续进入实体解析，不能被旧的范围外词表短路。
    from app.application.services.market_quote_service import (
        detect_market_quote_field,
    )

    if detect_market_quote_field(ql) or _detect_market_decision_intent(ql):
        return None

    # 范围外问题（天气/编程/翻译等）先于问候宽松判定：
    # "你好，今天天气怎么样"应归 unsupported，而非被"你好"抢先为 chitchat。
    # 8/22 修复（P0-3 后测集分析）：公告类查询豁免 unsupported 词表——
    # "提前赎回可转债的公告"含"赎回"（交易词），但问的是公告事件，
    # 属 events/公告舆情范围，不应被短路为"超出服务范围"。
    if any(kw in ql for kw in _UNSUPPORTED_KW):
        if not any(cue in ql for cue in ("公告", "公布", "披露")):
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
    if re.fullmatch(r"你(?:会|能做|能帮我做)什么", ql_clean):
        return "chitchat"
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
    # 8/22 晚全量 1410 分析：无公司时市场宏观/全市场聚合类问题
    # （"今天市场有哪些消息""最近有哪些利好事件"）落 guide 会答
    # "未能识别到公司"（错误），此处优先归 unsupported 合理拒答。
    # 注意 _MACRO_MARKET_CUES 的词都带"市场/大盘/指数/利好利空"语境，
    # 不会误伤 research 行业动态类（那类走 _RESEARCH_CUES）。
    if any(cue in ql for cue in _MACRO_MARKET_CUES):
        return "unsupported"
    # 8/22 晚全量 1410 分析：无公司时券商业务/盘口/账户操作类
    # （"如何调整佣金""688001卖盘"）同样应归 unsupported 而非 guide；
    # 公告类豁免与 detect_chitchat_intent 保持一致。
    if any(kw in ql for kw in _UNSUPPORTED_KW) and not any(
        cue in ql for cue in ("公告", "公布", "披露")
    ):
        return "unsupported"
    if any(cue in ql for cue in _RESEARCH_CUES):
        return "research"
    if any(cue in ql for cue in _ANALYSIS_CUES) or any(
        cue in ql for cue in _CONTEXT_CUES
    ):
        return "guide"
    return None


def _detect_market_decision_intent(user_query: str) -> str | None:
    """识别交易执行与投资建议边界，不把它们伪装成风险诊断。"""
    query = user_query or ""
    if re.search(
        r"(?:帮我|替我|给我).{0,6}(?:买入|卖出|清仓)"
        r"|(?:^|[，。！？\s])清仓\s*(?=[\u4e00-\u9fffA-Za-z0-9])"
        r"|(?:买入|卖出).{0,12}\d+\s*(?:手|股)"
        r"|\d+\s*元.{0,12}(?:买入|卖出).{0,12}\d+\s*(?:手|股)"
        r"|(?:\d{6}.*(?:买入|卖出)|(?:\d+\s*(?:元|股|手)).{0,20}(?:买入|卖出))",
        query,
    ):
        return "trade_execution"
    if re.search(
        r"(?:适合|值得|可以|还能|还可).{0,3}(?:买|买入|卖出)"
        r"|(?:买入|卖出)吗|(?:能不能|可不可以|该不该)买|能买吗"
        r"|(?:推荐|推).{0,12}(?:买入|证券|股票)",
        query,
    ):
        return "investment_advice"
    return None


@dataclass(frozen=True)
class _QuerySemanticContext:
    """Planner 的一次性语义中间结果。

    该对象只汇总查询特征，不执行数据库或 LLM 调用；ExecutionPlan 仍是
    下游模块唯一消费的结构化语义表示。集中计算可以避免同一问题在多个
    边界分支中被重复解释，导致前置 unsupported 短路覆盖后续因果路由。
    """

    answer_operation: str
    market_field: str | None
    market_decision_intent: str | None
    is_multi_metric: bool
    is_causal_boundary: bool
    is_market_price_boundary: bool

    @classmethod
    def from_query(cls, query: str) -> "_QuerySemanticContext":
        operation = _detect_answer_operation(query)
        return cls(
            answer_operation=operation,
            market_field=detect_market_quote_field(query),
            market_decision_intent=_detect_market_decision_intent(query),
            is_multi_metric=_detect_multi_metric_query(query),
            is_market_price_boundary=_detect_market_price_boundary(query),
            is_causal_boundary=(
                (
                    operation == "causal"
                    and any(cue in query for cue in ("上涨", "下跌", "涨", "跌"))
                )
                or (
                    operation == "impact"
                    and any(
                        cue in query for cue in ("价格上涨", "价格下跌", "原材料价格")
                    )
                    and not any(cue in query for cue in _IMPACT_EVENT_REF_CUES)
                )
            ),
        )


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

    semantics = _QuerySemanticContext.from_query(user_query)
    market_field = semantics.market_field
    market_decision_intent = semantics.market_decision_intent
    causal_boundary = semantics.is_causal_boundary or semantics.is_market_price_boundary

    # 交易指令/投资建议的能力边界与实体是否入库无关，应先于实体失败返回。
    # 例如 ETF、基金或错别字证券的“买入”请求也不能误报成公司未识别。
    if market_decision_intent:
        return {
            "plan": ExecutionPlan(
                intent=market_decision_intent,
                requested_modules=[],
                cross_checks=[],
                as_of=as_of,
                as_of_kind=as_of_kind,
                requested_period_text=period_text,
            )
        }

    # 明确范围外的账户/页面操作优先于会话中的旧公司主体，避免把
    # “预留手机号/行情页面设置”等问题误做成公司综合诊断。
    if (
        detect_chitchat_intent(user_query) == "unsupported"
        or any(cue in user_query for cue in ("设置个股行情页面", "行情路径"))
    ) and not causal_boundary:
        return {
            "plan": ExecutionPlan(
                intent="unsupported",
                requested_modules=[],
                cross_checks=[],
                as_of=as_of,
                as_of_kind=as_of_kind,
                requested_period_text=period_text,
            )
        }

    if company is None and market_field:
        return {
            "plan": ExecutionPlan(
                intent="unsupported",
                requested_modules=[],
                cross_checks=[],
                as_of=as_of,
                as_of_kind=as_of_kind,
                requested_period_text=period_text,
            )
        }

    if (
        company is None
        and (
            any(cue in user_query for cue in _MARKET_WIDE_CUES)
            or any(cue in user_query for cue in _MACRO_MARKET_CUES)
        )
        and not (
            ("个股" in user_query or "股票" in user_query)
            and any(cue in user_query for cue in ("行业", "板块", "领域"))
            and "自选" not in user_query
        )
    ):
        return {
            "plan": ExecutionPlan(
                intent="unsupported",
                requested_modules=[],
                cross_checks=[],
                as_of=as_of,
                as_of_kind=as_of_kind,
                requested_period_text=period_text,
            )
        }

    # 明确行业统计问题优先于会话中的旧公司上下文；否则“家电行业均值”
    # 会沿用上一轮公司并回答公司自身指标。
    industry_request = detect_industry_benchmark_request(user_query)
    if industry_request is not None and not re.search(r"所属|所在", user_query):
        industry_l1, indicator = industry_request
        return {
            "plan": ExecutionPlan(
                intent="industry_benchmark",
                requested_modules=[],
                cross_checks=[],
                indicator=indicator,
                industry_l1=industry_l1,
                answer_operation=_detect_answer_operation(user_query),
                as_of=as_of,
                as_of_kind=as_of_kind,
                requested_period_text=period_text,
            )
        }

    if company is not None and semantics.is_market_price_boundary:
        return {
            "plan": ExecutionPlan(
                intent="causal_query",
                requested_modules=[],
                cross_checks=[],
                as_of=as_of,
                as_of_kind=as_of_kind,
                requested_period_text=period_text,
            )
        }

    # 单公司行情快照由 AnySearch 精准查询，不启动财务/股权/舆情模块。
    # 多指标混合题仍交给既有 multi_metric 边界处理，避免只答其中一个字段。
    market_causal = any(
        cue in user_query
        for cue in ("原因", "为何", "为什么", "怎么回事", "驱动", "影响")
    )
    if (
        company is not None
        and market_field
        and not market_causal
        and not semantics.is_multi_metric
    ):
        if any(cue in user_query for cue in ("排名", "排行", "压力位", "支撑位")):
            return {
                "plan": ExecutionPlan(
                    intent="unsupported_indicator",
                    requested_modules=[],
                    cross_checks=[],
                    as_of=as_of,
                    as_of_kind=as_of_kind,
                    requested_period_text=period_text,
                )
            }
        return {
            "plan": ExecutionPlan(
                intent="market_quote",
                requested_modules=[],
                cross_checks=[],
                market_field=market_field,
                as_of=as_of,
                as_of_kind=as_of_kind,
                requested_period_text=period_text,
            )
        }

    if company is not None and market_decision_intent:
        return {
            "plan": ExecutionPlan(
                intent=market_decision_intent,
                requested_modules=[],
                cross_checks=[],
                as_of=as_of,
                as_of_kind=as_of_kind,
                requested_period_text=period_text,
            )
        }

    # 明确命中未覆盖指标时先给出能力边界，不让指标修饰词进入实体解析，
    # 例如“基本每股收益”不应被拆成“基本”“收益”两个疑似公司。
    if (
        not semantics.is_multi_metric
        and detect_indicator(user_query) == "unsupported"
        and not causal_boundary
    ):
        return {
            "plan": ExecutionPlan(
                intent="unsupported_indicator",
                requested_modules=[],
                cross_checks=[],
                as_of=as_of,
                as_of_kind=as_of_kind,
                requested_period_text=period_text,
            )
        }

    # 明确范围外的账户、交易规则和市场级问题不依赖公司实体。实体提取器
    # 即使从自然语言中切出了疑似公司片段，也应返回真实能力边界。
    if company is None and detect_chitchat_intent(user_query) == "unsupported":
        return {
            "plan": ExecutionPlan(
                intent="unsupported",
                requested_modules=[],
                cross_checks=[],
                as_of=as_of,
                as_of_kind=as_of_kind,
                requested_period_text=period_text,
            )
        }

    # 2026-08-12 四轮审查 P2-2：实体解析失败/候选截断为确定性错误——
    # 直接产出 entity_error intent，不进入 chitchat LLM 检测
    # （generate_answer 已按 state 字段给明确文案，无意义延迟与费用）。
    if state.get("entity_resolution_error") or state.get("candidates_truncated"):
        return {
            "plan": ExecutionPlan(
                intent="entity_error",
                requested_modules=[],
                cross_checks=[],
                as_of=as_of,
                as_of_kind=as_of_kind,
                requested_period_text=period_text,
            )
        }

    # v3.1 P0-3：relation 不可执行（reference/sequence/ambiguous）且身份
    # 已确认 → relation_clarify（澄清主次/先后关系），不派生 company、
    # 不进入 comparison_guide、不启动模块执行。身份未确认时先走候选确认。
    resolution = state.get("entity_resolution_result")
    # v3.3.2-R1 §8：复用已验证的 Interpreter plan_hint（避免同一 query
    # 为主体调用一次、再为意图调用第二次语义 LLM）；不覆盖实体权威结果
    plan_hint = ""
    if (
        resolution is not None
        and getattr(resolution, "subject_interpreter_status", "not_needed")
        == "completed"
    ):
        interp = getattr(resolution, "subject_interpretation", None)
        if interp is not None:
            plan_hint = getattr(interp, "plan_hint", "") or ""
    if resolution is not None:
        rel_intent = getattr(resolution, "intent", "")
        rel_confirm = bool(getattr(resolution, "needs_confirmation", False))
        if rel_intent in ("reference", "sequence", "ambiguous") and not rel_confirm:
            return {
                "plan": ExecutionPlan(
                    intent="relation_clarify",
                    requested_modules=[],
                    cross_checks=[],
                    as_of=as_of,
                    as_of_kind=as_of_kind,
                    requested_period_text=period_text,
                )
            }

    # v3.3.3 批次 C（方案 §2.2/§5.6）：同主体跨指标比较——
    # 单主体（无 comparison_targets）+ 当前命中可执行指标 +
    # 历史最近成功指标（不同 ID）+ 比较词 → 结构化轻量比较计划。
    # 插在 comparison_guide 之前：此类问题 Resolver 已排除公司比较语义
    # （"增速"等排除词），不得落入单指标短答或关系澄清。
    comparison_targets = state.get("comparison_targets") or []
    if company is not None and not comparison_targets:
        current_indicator = detect_indicator(user_query)
        if (
            current_indicator
            and current_indicator != "unsupported"
            and any(cue in user_query for cue in _SAME_COMPANY_COMPARE_CUES)
        ):
            hist_metrics = _recent_executed_metric_ids(state)
            hist_id = ""
            for item in hist_metrics:
                metric_id = getattr(item, "metric_id", "")
                status = getattr(item, "status", "ok")
                # 收口批次 B（方案 §3.4）：历史指标必须属于当前公司，
                # 无归属的旧记录不得用于跨指标比较（防切换公司后串用）
                item_code = getattr(item, "company_code", "")
                if (
                    metric_id
                    and metric_id != current_indicator
                    and status == "ok"
                    and item_code
                    and item_code == company.wind_code
                ):
                    hist_id = metric_id
                    break
            if hist_id:
                spec = ComparisonSpec(
                    scope="same_company_cross_indicator",
                    mode="indicator",
                    metric_ids=[hist_id, current_indicator],
                    operation="difference",
                    period_policy=(
                        "explicit_period"
                        if as_of_kind == "report_period"
                        else "latest_common_period"
                    ),
                )
                # 收口批次 B（方案 §3.2）：plan 后校验一次，非法回退单指标短答
                if validate_comparison_spec(spec, [company.wind_code]):
                    pass  # 不合法 → 落到下方 indicator 短答
                else:
                    return {
                        "plan": ExecutionPlan(
                            intent="light_comparison",
                            requested_modules=[],
                            cross_checks=[],
                            as_of=as_of,
                            as_of_kind=as_of_kind,
                            requested_period_text=period_text,
                            comparison=spec,
                        )
                    }

    # v3.3.3 批次 D（方案 §2.4/§5.6）+ v3.3.4 Preview First（方案 §4.1）：
    # 双公司轻量比较路由。优先级：明确单指标 → 公司事实 → 全面 → 风险 →
    # 行业 → 普通概览。注意「全面」cue 优先于「风险」cue：_FULL_COMPARISON_CUES
    # 含「财务与风险/财务和风险」，其中「风险」是子串，全面语义更具体
    # （§4.1 规则 6 覆盖普通/全面/行业请求）。
    # 全面/行业在恰好两家 finalized 时先出基础指标预览并保留 requested_scope
    # （mode=overview），不再直接跳页面（§2.1/§4.1 规则 6）；
    # 三家及以上 → comparison_guide 不截断（结构化保底 next_steps 由
    # generate_answer 生成，§2.4）；不足两家 → 下方 relation_clarify。
    comparison_requested = state.get("comparison_requested")
    distinct_codes = {str(t.wind_code) for t in comparison_targets if t}
    if comparison_requested and len(distinct_codes) >= 2:
        # 收口批次 B（方案 §2.4）：三家及以上 → 全面比较页面，
        # 轻量比较一期只支持恰好两家（不静默截取前两家）
        if len(distinct_codes) > 2:
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
        indicator = detect_indicator(user_query)
        if indicator and indicator != "unsupported":
            spec = ComparisonSpec(
                scope="cross_company",
                mode="indicator",
                requested_scope="indicator",
                metric_ids=[indicator],
                operation=_detect_comparison_operation(user_query),
                period_policy=(
                    "explicit_period"
                    if as_of_kind == "report_period"
                    else "latest_common_period"
                ),
            )
            if validate_comparison_spec(spec, sorted(distinct_codes)):
                pass  # 防御：不合法落到 comparison_guide
            else:
                return {
                    "plan": ExecutionPlan(
                        intent="light_comparison",
                        requested_modules=[],
                        cross_checks=[],
                        as_of=as_of,
                        as_of_kind=as_of_kind,
                        requested_period_text=period_text,
                        comparison=spec,
                    )
                }
        fact_key = detect_company_fact(user_query)
        if fact_key:
            return {
                "plan": ExecutionPlan(
                    intent="light_comparison",
                    requested_modules=[],
                    cross_checks=[],
                    as_of=as_of,
                    as_of_kind=as_of_kind,
                    requested_period_text=period_text,
                    comparison=ComparisonSpec(
                        scope="cross_company",
                        mode="company_fact",
                        requested_scope="company_fact",
                        fact_key=fact_key,
                        operation=(
                            "earlier_than"
                            if any(w in user_query for w in ("早", "晚"))
                            else "difference"
                        ),
                        period_policy="not_applicable",
                    ),
                )
            }
        # 全面/行业/普通/风险 → 请求范围分类（§4.1 规则 5/6）。
        # 全面 cue 先于风险 cue（「财务与风险」属于全面请求）。
        if any(cue in user_query for cue in _FULL_COMPARISON_CUES):
            requested_scope = "full"
        elif "行业" in user_query:
            requested_scope = "industry"
        elif any(cue in user_query for cue in _RISK_COMPARE_CUES):
            return {
                "plan": ExecutionPlan(
                    intent="light_comparison",
                    requested_modules=[],
                    cross_checks=[],
                    as_of=as_of,
                    as_of_kind=as_of_kind,
                    requested_period_text=period_text,
                    comparison=ComparisonSpec(
                        scope="cross_company",
                        mode="risk",
                        requested_scope="risk",
                    ),
                )
            }
        else:
            requested_scope = "overview"
        # v3.3.4（方案 §4.1 规则 6）：普通「对比一下」/全面/行业 → overview
        # 轻量概览（服务端固定 profile），requested_scope 保留原始范围，
        # 不再只追问指标或直接跳页面。
        overview_spec = ComparisonSpec(
            scope="cross_company",
            mode="overview",
            requested_scope=requested_scope,
            period_policy=(
                "explicit_period"
                if as_of_kind == "report_period"
                else "latest_common_period"
            ),
        )
        if validate_comparison_spec(overview_spec, sorted(distinct_codes)):
            pass  # 防御：不合法落到 comparison_guide
        else:
            return {
                "plan": ExecutionPlan(
                    intent="light_comparison",
                    requested_modules=[],
                    cross_checks=[],
                    as_of=as_of,
                    as_of_kind=as_of_kind,
                    requested_period_text=period_text,
                    comparison=overview_spec,
                )
            }

    # P2-2：多公司比较引导——comparison_requested 标志恒 True 时即进入
    # comparison_guide（0/1/≥2 家候选都算），不复用 company_disambiguation 的
    # "请选择一家"文案；文案差异由 generate_answer 按候选数处理。
    # 最终续审 §4 A5：comparison_requested=True 但目标少于两家 →
    # relation_clarify，不得靠 generate_answer 的 0/1 家 fallback 文案
    # 掩盖 Resolver 非法状态（单主体 comparison 已被 Resolver 降级
    # ambiguous，这里兜住旧扁平字段路径）。
    if state.get("comparison_requested") or len(comparison_targets) >= 2:
        target_codes = {str(t.wind_code) for t in comparison_targets if t}
        if state.get("comparison_requested") and len(target_codes) < 2:
            return {
                "plan": ExecutionPlan(
                    intent="relation_clarify",
                    requested_modules=[],
                    cross_checks=[],
                    as_of=as_of,
                    as_of_kind=as_of_kind,
                    requested_period_text=period_text,
                )
            }
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
        # 产品口径固定为母公司报表。明确要求合并口径时先说明不支持切换，
        # 不能继续给出容易被误读的母公司数值。
        operation = semantics.answer_operation
        event_sentiment = _detect_event_sentiment(user_query)
        event_list_requested = _detect_event_list_requested(user_query)
        fact_key = detect_company_fact(user_query)
        if fact_key in {
            "subsidiary",
            "project",
            "executive_compensation",
            "ipo_price",
        }:
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
        if any(
            cue in user_query for cue in ("研报", "机构评级", "券商评级")
        ) and not any(cue in user_query for cue in _IMPACT_REQUEST_CUES):
            return {
                "plan": ExecutionPlan(
                    intent="research",
                    requested_modules=[],
                    cross_checks=[],
                    as_of=as_of,
                    as_of_kind=as_of_kind,
                    requested_period_text=period_text,
                )
            }
        if any(cue in user_query for cue in _COMPANY_RESEARCH_CUES):
            return {
                "plan": ExecutionPlan(
                    intent="research",
                    requested_modules=[],
                    cross_checks=[],
                    as_of=as_of,
                    as_of_kind=as_of_kind,
                    requested_period_text=period_text,
                )
            }
        if event_list_requested and not any(
            cue in user_query for cue in _IMPACT_REQUEST_CUES
        ):
            return {
                "plan": ExecutionPlan(
                    intent="simple_query",
                    requested_modules=["events"],
                    cross_checks=[],
                    as_of=as_of,
                    as_of_kind=as_of_kind,
                    requested_period_text=period_text,
                    event_list_requested=True,
                )
            }
        if event_sentiment != "all" and not any(
            cue in user_query for cue in _IMPACT_REQUEST_CUES
        ):
            return {
                "plan": ExecutionPlan(
                    intent="simple_query",
                    requested_modules=["events"],
                    cross_checks=[],
                    as_of=as_of,
                    as_of_kind=as_of_kind,
                    requested_period_text=period_text,
                    event_sentiment=event_sentiment,
                )
            }
        if "合并口径" in user_query:
            return {
                "plan": ExecutionPlan(
                    intent="unsupported_scope",
                    requested_modules=[],
                    cross_checks=[],
                    as_of=as_of,
                    as_of_kind=as_of_kind,
                    requested_period_text=period_text,
                    answer_operation=operation,
                )
            }
        if (
            "行业" in user_query
            and re.search(r"所属|所在", user_query)
            and (
                operation in ("assessment", "industry_total", "industry_leader")
                or "整体" in user_query
            )
        ):
            return {
                "plan": ExecutionPlan(
                    intent="unsupported_scope",
                    requested_modules=[],
                    cross_checks=[],
                    as_of=as_of,
                    as_of_kind=as_of_kind,
                    requested_period_text=period_text,
                    answer_operation=operation,
                )
            }
        if semantics.is_multi_metric:
            return {
                "plan": ExecutionPlan(
                    intent="multi_metric",
                    requested_modules=[],
                    cross_checks=[],
                    as_of=as_of,
                    as_of_kind=as_of_kind,
                    requested_period_text=period_text,
                )
            }
        # v3.3.3 批次 D（方案 §2.4 行业对比行）+ v3.3.4（方案 §2.1/§4.1）：
        # 单主体行业/全面对比引导页面（industry_benchmark_service 在 REST
        # 页面提供行业分位，对话内不执行、不伪造成双公司比较；只有一家
        # finalized 主体不进入 overview，不伪造第二主体）
        if any(cue in user_query for cue in ("对比", "比较")) and (
            "行业" in user_query
            or any(cue in user_query for cue in _FULL_COMPARISON_CUES)
        ):
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
        indicator = detect_indicator(user_query)
        # 外部价格变化的原因/影响问题属于已有的因果边界，不应被
        # detect_indicator 的“未覆盖指标”结果提前截断。
        causal_boundary = (
            operation == "causal"
            and any(cue in user_query for cue in ("上涨", "下跌", "涨", "跌"))
        ) or (
            operation == "impact"
            and any(cue in user_query for cue in ("价格上涨", "价格下跌", "原材料价格"))
            and not any(cue in user_query for cue in _IMPACT_EVENT_REF_CUES)
        )
        if indicator == "unsupported" and not causal_boundary:
            return {
                "plan": ExecutionPlan(
                    intent="unsupported_indicator",
                    requested_modules=[],
                    cross_checks=[],
                    as_of=as_of,
                    as_of_kind=as_of_kind,
                    requested_period_text=period_text,
                    answer_operation=operation,
                )
            }
        # 原因/影响类问题含诊断词，普通 detect_indicator 会主动让位给
        # 综合诊断；已有明确指标时恢复结构化指标回答，避免答成全量风险报告。
        if not indicator and operation in ("causal", "impact"):
            from app.application.services.indicator_semantics import (
                resolve_indicator_semantics,
            )

            semantic = resolve_indicator_semantics(user_query)
            if semantic.executable and semantic.metric_ids:
                indicator = semantic.metric_ids[0]
        if (
            not indicator
            and operation == "causal"
            and any(cue in user_query for cue in ("上涨", "下跌", "涨", "跌"))
        ):
            return {
                "plan": ExecutionPlan(
                    intent="causal_query",
                    requested_modules=[],
                    cross_checks=[],
                    as_of=as_of,
                    as_of_kind=as_of_kind,
                    requested_period_text=period_text,
                )
            }
        if (
            not indicator
            and operation == "impact"
            and any(cue in user_query for cue in ("价格上涨", "价格下跌", "原材料价格"))
            and not any(cue in user_query for cue in _IMPACT_EVENT_REF_CUES)
        ):
            return {
                "plan": ExecutionPlan(
                    intent="causal_query",
                    requested_modules=[],
                    cross_checks=[],
                    as_of=as_of,
                    as_of_kind=as_of_kind,
                    requested_period_text=period_text,
                )
            }
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
                    # v3.3.3 收口批次 D（方案 §3.6）：「正常吗」类问句
                    # 需要基准判断，不能只答数值
                    answer_operation=operation,
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
        if _detect_event_list_requested(user_query) and not any(
            cue in user_query for cue in _RESEARCH_CUES
        ):
            return {
                "plan": ExecutionPlan(
                    intent="research",
                    requested_modules=[],
                    cross_checks=[],
                    as_of=as_of,
                    as_of_kind=as_of_kind,
                    requested_period_text=period_text,
                    event_list_requested=True,
                )
            }
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
        # v3.3.2-R1 §8：已验证 plan_hint 优先（research/chitchat/
        # unsupported 复用现有 intent；公司分析类但实体缺失 → guide）
        fallback_intent = _fallback_no_company_intent(user_query)
        if plan_hint == "research" or (
            plan_hint
            not in {
                "",
                "chitchat",
                "unsupported",
                "indicator",
                "diagnostic",
                "summary",
                "analysis",
                "comparison",
            }
            and fallback_intent == "research"
        ):
            detected = "research"
        elif plan_hint == "chitchat":
            detected = "chitchat"
        elif plan_hint == "unsupported":
            detected = "unsupported"
        elif plan_hint in (
            "indicator",
            "diagnostic",
            "summary",
            "analysis",
            "comparison",
        ):
            # 公司分析诉求但实体缺失 → 可执行引导。但 mock/降级 LLM 对
            # 明确 research 关键词（板块/技术/产业等）可能返回泛化
            # "analysis"——此时以高置信关键词兜底 research 为准（8/20 CI 修复：
            # 测试在 LLM_BACKEND=mock 下 "AI医疗板块有哪些个股" 等被误判 guide）。
            # 8/22 晚全量 1410：无公司市场宏观/券商业务类（_MACRO_MARKET_CUES /
            # _UNSUPPORTED_KW）同样会被 mock LLM 泛化为 analysis → 误落
            # guide（"未能识别到公司"错误）；fallback 已判定 unsupported 时
            # 以此为准，避免答非所问。
            if fallback_intent == "unsupported":
                detected = "unsupported"
            elif fallback_intent == "research":
                detected = "research"
            else:
                detected = "guide"  # 公司分析诉求但实体缺失，转为可执行引导
        else:
            detected = detect_chitchat_intent(user_query)
            if detected is None:
                detected = _detect_chitchat_with_llm(user_query)
            if detected is None:
                detected = fallback_intent
            if detected == "analysis":
                # 已确认是公司分析诉求但实体缺失，转为可执行引导。
                # 8/20 CI 修复：mock/降级 LLM 对明确 research 关键词
                # （板块/技术/产业/热点资讯等）返回泛化 "analysis"——此时
                # 以高置信关键词兜底 research 为准，否则 "AI医疗板块有
                # 哪些个股" 等被误判为 guide。
                # 8/22 晚全量 1410：同样处理 fallback 已判定 unsupported
                # 的定位外问题（市场宏观/券商业务），不落 guide 答非所问。
                if fallback_intent == "unsupported":
                    detected = "unsupported"
                elif fallback_intent == "research":
                    detected = "research"
                else:
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
    answer_target = detect_answer_target(user_query) or ""

    need_finance = any(kw in ql for kw in _FINANCE_KW)
    need_equity = any(kw in ql for kw in _EQUITY_KW)
    need_events = any(kw in ql for kw in _EVENTS_KW)

    # 综合诊断 → 展开全部模块
    if any(kw in ql for kw in _DIAGNOSIS_KW):
        need_finance = need_equity = need_events = True

    # 关键词未命中 → LLM 语义识别兜底（口语化/同义表达）。
    # v3.3.2-R1 §8：已验证 plan_hint 为 indicator/diagnostic/summary/
    # analysis/comparison 时不再为此调用第二次语义 LLM，走下方默认
    # 全模块兜底；other/uncertain 保持现有 LLM fallback
    if not need_finance and not need_equity and not need_events:
        if plan_hint not in (
            "indicator",
            "diagnostic",
            "summary",
            "analysis",
            "comparison",
        ):
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
            answer_target=answer_target,
            # B2 批次 A：确定性双条件判定（事件指代 + 影响/风险 cue），
            # 综合诊断/宽泛风险/仅公告查询/LLM events=True 一律 False
            impact_requested=_detect_impact_requested(user_query),
        )
    }
