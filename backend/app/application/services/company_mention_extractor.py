"""CompanyMentionExtractor — 只提出原文 span（v3.1 冻结方案 P0-2/P1-4）.

职责边界（组件冻结）：
- 从**原始 query** 提取候选 span（text/start/end/mention_id）；
- **不接收 protected_names、不查询数据库、不做候选驱动递归切分**；
- 复合片段（"茅台和协和的营收"）作为一个 span 提出，分段方案由
  Resolver 处理。

偏移保持（P1-4）：对待删除字符做**等长 mask**（保留原文坐标），
在 mask 后文本上匹配，不再 replace() 后反推原位置；start/end 恒为
原始 query 偏移。时间词/请求词/终止符/分段规则平移自 v8 已验证规则，
年份正则修正为通用 (?:19|20)\\d{2}（不再硬编码 2024）。
"""

from __future__ import annotations

import logging
import re

from app.application.models.company_resolution import (
    EntityMention,
    MentionExtractionResult,
    make_mention_id,
)

logger = logging.getLogger(__name__)

# ── 分段（v8 _SEGMENT_RE 平移）─────────────────────────────
# 标点与多字连接词用 alternation 整体切分；不含单字 和/与/跟/及
# （"协和电子"不被切开；单字连接词由 Resolver 复合解析处理）。
_SEGMENT_RE = re.compile(r"[，。、；！？,]|vs|以及|并且|对比|比较")

# 请求动作词（单一来源，8/17 词表优化方向 3）：同时被
# _SUBJECT_CLEAN_WORDS（全局填充词 mask）与 _REQUEST_WORDS（段首
# 请求词删除）复用，避免两表各自维护同义词造成漂移。
_REQUEST_ACTION_WORDS: tuple[str, ...] = (
    "分析",
    "查看",
    "看看",
    "评估",
    "总结",
    "帮我",
    "帮忙",
    "请问",
    "说说",
    "介绍",
    "一下",
)

# 多字停用词（v8 _MULTI_CHAR_STOPWORDS 平移：填充词，整词标记删除）
_SUBJECT_CLEAN_WORDS: tuple[str, ...] = _REQUEST_ACTION_WORDS + (
    "看下",
    "查下",
    "评价",
    "给我",
    "怎么样",
    "如何",
    "多少",
    "什么",
    "是什么",
    "情况",
    "问题",
    "哪家",
    "哪个",
    "会不会",
    "是否",
    "为什么",
    "综合",
    "结论",
    "一个",
    "这家",
    "那家",
    "该公司",
    "上家",
    "刚才",
    "继续",
    "再看",
    "前面",
    "还高",
    "下降",
    "上升",
    "改善",
    "恶化",
    "表现",
    "波动",
    "差距",
    # v3.3.2 §5.1：回指短语整体 mask（最长优先排序保证先于"这家/
    # 那家/该公司"短词命中，避免残留"公司"被误召回库）
    "这家公司",
    "那家公司",
    "该家公司",
    "这家企业",
    "那家企业",
    "该企业",
    # v3.3.2 §5.3：句首历史回指框架（"刚才提到的…"整短语不生成
    # span；与"康美提到茅台"的"提到"连接语义区分）——批次 C 保留
    # （审查 P1-5：等长 mask 暂保留，fallback 稳定后再删）
    "刚才提到的",
    "前面提到的",
    "刚刚说的",
    "上面说的",
)

# 最终续审 §5 B1：回指短语 / 句首回指框架的语义子集标记（词本身
# 已在 _SUBJECT_CLEAN_WORDS 中被 mask，这里只用于结构化元数据，
# 不新增第二套词表）
_ANAPHORA_PHRASE_MARKERS: tuple[str, ...] = (
    "这家公司",
    "那家公司",
    "该家公司",
    "这家企业",
    "那家企业",
    "该企业",
)
_BACK_REFERENCE_MARKERS: tuple[str, ...] = (
    "刚才提到的",
    "前面提到的",
    "刚刚说的",
    "上面说的",
)


# 请求词（v8 _REQUEST_WORDS 平移：只删主语区域开头，固定点、最长优先）
# 8/17 词表优化方向 3：动作部分复用 _REQUEST_ACTION_WORDS（与
# _SUBJECT_CLEAN_WORDS 同源），此处只保留请求词独有项。
_REQUEST_WORDS: tuple[str, ...] = _REQUEST_ACTION_WORDS + (
    "你认为",
    "你觉得",
    "麻烦",
    "能否",
    "可以",
    "请",
    "看",
    "查",
    "下",
)

# 时间词（v8 _TIME_MODIFIER_RE 平移；年份修正为通用 (?:19|20)\\d{2}）
_TIME_MODIFIER_RE = re.compile(
    r"(?:"
    r"近三年|过去三年|最近三年"
    r"|(?:(?:19|20)\d{2})年(?:第一季度|上半年|下半年|年度|的)?"
    r"|截至(?:(?:19|20)\d{2})年|截止(?:(?:19|20)\d{2})年"
    r"|去年(?:的)?|今年|前年|最近(?:的)?|现在"
    r"|上半年|下半年|第一季度|一季度|Q1"
    r"|同比|环比"
    r")"
)

# 主语槽终止符（v8 _SUBJECT_TERMINATORS 平移）：最早终止符之前才是
# 疑似实体区域；**不含时间词及裸"年"**（时间词为主语区域内可删表达）。
# 8/17 词表优化方向 4：按语义分三类（财务科目词/事件舆情词/动词边界），
# 最终展平为同一终止符集合——使用处取"最早终止符位置"（min 语义），
# 分组不改行为，仅提升可维护性。
_SUBJECT_TERMINATORS_FINANCE: tuple[str, ...] = (
    "什么时候上市",
    "哪一年上市",
    "上市日期",
    "上市时间",
    "何时上市",
    "哪天上市",
    "上市",
    "资产负债率",
    "应收账款",
    "经营活动现金流",
    "经营现金流",
    "营业收入",
    "总资产",
    "总负债",
    "净利润",
    "存货",
    "财务",
    "财报",
    "营收",
    "负债率",
    "现金流",
    "营业",
    "收入",
    "利润",
    "应收",
    "应付",
    "负债",
    "资产",
    "股权",
    "股东",
    "增长",
    "增速",
    "变化",
    "趋势",
    "余额",
    "周转",
    "毛利率",
    "净利率",
    "成本",
    "费用",
    "分红",
    "回购",
    "业绩",
    "经营",
    "现金",
    "风险",
    "异常",
    "造假",
    "舞弊",
    "诊断",
    "有问题",
    "原因",
    # v3.2.1 批次 2：公司事实问法边界（"小米属于什么行业"→"小米"）。
    # 注意：单字"的"不得加入（会破坏"美的"等名称内部字符）。
    "属于",
)
# 事件舆情词：与财务科目词同为"主语槽终止符"，但语义属于事件/公告域
_SUBJECT_TERMINATORS_EVENTS: tuple[str, ...] = (
    "公告",
    "舆情",
    "评级",
)
_SUBJECT_TERMINATORS: tuple[str, ...] = (
    _SUBJECT_TERMINATORS_FINANCE + _SUBJECT_TERMINATORS_EVENTS
)

# 前导指代/动作（v8 _SINGLE_CHAR_PREFIX_RE 平移：段开头连续字符）。
# v3.3.2 §5.2："那"作为句首对照标记剥离——仅段首、连续、后续须有
# ≥2 字片段且获得公司候选（由 Resolver 召回验证），非全局删除
# 前导指代/动作（v8 _SINGLE_CHAR_PREFIX_RE 平移：段开头连续字符）。
# 批次 C 保留（审查 P1-5：等长 mask 暂保留，fallback 稳定后再删）
_SINGLE_CHAR_PREFIX_RE = re.compile(r"^(?:看|查|给|它|他|她|其|都|那)+")

# v3.3.2 §5.2：显式切换前缀（封闭集合，仅段首固定点剥离）——
# "回到康美"→"康美"（原文坐标），动作语义由 Resolver 判定 switch。
# 批次 C 保留（审查 P1-5：等长 mask 暂保留，fallback 稳定后再删）
_SWITCH_PREFIXES: tuple[str, ...] = ("再回到", "回到", "换回")

# v3.3 批次 B（P1-4）：显式 Wind Code 块（6 位数字 ± 后缀，
# lookaround 防前后粘连数字；与 resolver 同一模式）
_WIND_CODE_RE = re.compile(
    r"(?<!\d)(\d{6}(?:\.(?:S[HZ]|BJ|XSHG|XSHE))?)(?!\d)", re.IGNORECASE
)


def _is_cn(ch: str) -> bool:
    return "一" <= ch <= "龥"


def _mask_out(mask: list[bool], start: int, end: int) -> None:
    """等长 mask：把 [start, end) 标记为删除（保留原文坐标）。"""
    for i in range(start, min(end, len(mask))):
        mask[i] = False


def _mask_all_occurrences(mask: list[bool], text: str, needle: str) -> None:
    """全局删除 needle 的所有出现（填充词等）。"""
    idx = text.find(needle)
    while idx >= 0:
        _mask_out(mask, idx, idx + len(needle))
        idx = text.find(needle, idx + len(needle))


def _mask_time_modifiers(mask: list[bool], text: str) -> None:
    """全局删除时间词（正则整体匹配，年份通配）。"""
    for m in _TIME_MODIFIER_RE.finditer(text):
        _mask_out(mask, m.start(), m.end())


def _subject_slot_start(seg_text: str, seg_start: int) -> int:
    """主语槽：段内最早终止符的绝对位置（终止符及其后标记删除）。"""
    positions = [(seg_text.find(t), t) for t in _SUBJECT_TERMINATORS if t in seg_text]
    if not positions:
        return seg_start + len(seg_text)
    pos, _ = min(positions)
    return seg_start + pos


def _strip_request_prefix_at(
    mask: list[bool], text: str, seg_start: int, seg_end: int
) -> None:
    """只删段开头的请求词（固定点循环、最长优先）。"""
    pos = seg_start
    changed = True
    while changed and pos < seg_end:
        changed = False
        for w in sorted(_REQUEST_WORDS, key=len, reverse=True):
            if text.startswith(w, pos) and pos + len(w) <= seg_end:
                _mask_out(mask, pos, pos + len(w))
                pos += len(w)
                changed = True
                break


def extract_company_mention_result(
    query: str | None,
) -> MentionExtractionResult:
    """最终续审 §5 B1：从原始 query 提取候选 span 与结构化元数据
    （纯函数，不查库）。

    Returns:
        MentionExtractionResult — mentions 的 mention_id/text/start/end
        已填充，candidates 为空（由 Resolver 查询填充）；元数据字段
        来自本函数已执行的匹配/掩码过程。
    """
    result = MentionExtractionResult()
    q = (query or "").strip()
    if not q:
        return result
    n = len(q)
    mask = [True] * n

    # 1. 全局删除：时间词、填充词；同时记录回指短语/回指框架命中
    _mask_time_modifiers(mask, q)
    for word in sorted(_SUBJECT_CLEAN_WORDS, key=len, reverse=True):
        if word in q:
            if word in _ANAPHORA_PHRASE_MARKERS:
                result.explicit_anaphora = True
            if word in _BACK_REFERENCE_MARKERS:
                result.back_reference = True
            _mask_all_occurrences(mask, q, word)

    # 2. 分段边界（分隔符位置本身不提取）
    seg_bounds: list[tuple[int, int]] = []
    last = 0
    for m in _SEGMENT_RE.finditer(q):
        if m.start() > last:
            seg_bounds.append((last, m.start()))
        last = m.end()
    if last < n:
        seg_bounds.append((last, n))

    # 3. 每段：主语槽截断 + 段开头请求词/切换前缀 + 前导指代
    for seg_start, seg_end in seg_bounds:
        slot_end = _subject_slot_start(q[seg_start:seg_end], seg_start)
        if slot_end < seg_end:
            result.had_subject_terminator = True
        _mask_out(mask, slot_end, seg_end)
        _strip_request_prefix_at(mask, q, seg_start, slot_end)
        # v3.3.2 §5.2：显式切换前缀（段首固定点、最长优先）——只剥
        # 前缀本身，公司 span 坐标保持原文位置（Resolver 侧检测 marker）
        pos = seg_start
        changed = True
        while changed and pos < slot_end:
            changed = False
            for w in sorted(_SWITCH_PREFIXES, key=len, reverse=True):
                if q.startswith(w, pos) and pos + len(w) <= slot_end:
                    _mask_out(mask, pos, pos + len(w))
                    pos += len(w)
                    changed = True
                    result.explicit_switch = True
                    break
        # 前导指代：作用于段开头剩余有效字符（等价 v8 锚定正则）
        m = _SINGLE_CHAR_PREFIX_RE.match(q[seg_start:slot_end])
        if m:
            _mask_out(mask, seg_start, seg_start + m.end())

    # 4. 按分段边界扫描 mask 保留的连续中文块（≥2 字，上限 16 覆盖
    #    双公司复合；超限块由 Resolver 判为无法解析，不静默截断）。
    #    分隔符（标点/多字连接词）位置不在任何分段内 → 中断连续性。
    mentions: list[EntityMention] = []
    for seg_start, seg_end in seg_bounds:
        # v3.3 批次 B（P1-4）：识别全部显式 Wind Code（finditer 语义，
        # 不再是 query 级只取第一个）——代码 span 与名称 span 进入同一
        # mention 集合，由 Resolver 统一查候选与关系判定
        for cm in _WIND_CODE_RE.finditer(q, seg_start, seg_end):
            code_text = cm.group(1)
            mentions.append(
                EntityMention(
                    mention_id=make_mention_id(cm.start(), cm.end(), code_text),
                    text=code_text,
                    start=cm.start(),
                    end=cm.end(),
                )
            )
            # 代码位置从中文扫描中剔除，避免重复提取
            _mask_out(mask, cm.start(), cm.end())
        i = seg_start
        while i < seg_end:
            if not mask[i] or not _is_cn(q[i]):
                i += 1
                continue
            j = i
            while j < seg_end and mask[j] and _is_cn(q[j]):
                j += 1
            text = q[i:j]
            # 剥离尾部语法字符（P1-2 条件 2 允许；保留 ≥2 字），span 收缩
            # 到原文子区间——"康美药业的"→"康美药业"，直接命中即可锁定，
            # 不必走变体确认路径
            end = j
            while end - i > 2 and text[end - i - 1] in "的呢吗了是":
                end -= 1
            text = q[i:end]
            if 2 <= end - i <= 16 and text.strip("的呢吗了是"):
                mentions.append(
                    EntityMention(
                        mention_id=make_mention_id(i, end, text),
                        text=text,
                        start=i,
                        end=end,
                    )
                )
            i = max(j, i + 1)

    # 5. 残余文本：mask 中残留但未成为 mention 的中文块（供 Resolver
    #    判断"是否还有未解释的疑似新公司证据"）
    mention_ranges = [(m.start, m.end) for m in mentions if m.start is not None]
    residual_parts: list[str] = []
    i = 0
    while i < n:
        if mask[i] and _is_cn(q[i]) and not any(s <= i < e for s, e in mention_ranges):
            j = i
            while (
                j < n
                and mask[j]
                and _is_cn(q[j])
                and not any(s <= j < e for s, e in mention_ranges)
            ):
                j += 1
            residual_parts.append(q[i:j])
            i = j
        else:
            i += 1
    result.residual_text = "".join(residual_parts)
    result.mentions = mentions
    return result


def extract_company_mentions(query: str | None) -> list[EntityMention]:
    """兼容 wrapper（最终续审 §5 B1：迁移完成后可删除）。"""
    return extract_company_mention_result(query).mentions
