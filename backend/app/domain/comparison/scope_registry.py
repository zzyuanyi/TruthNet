"""比较语义范围词注册表 — v3.3.4 收口复核审查 P2a（单一来源）。

实体层 comparison operator 忽略（company_entity_resolver）与计划层
requested_scope=full 判定（plan_modules）共用本注册表，禁止在两处
各自维护词表造成漂移（历史缺陷：实体层 全面/综合/全方位/整体 与
计划层 全面/综合/多维/全方位/财务与风险/财务和风险 不一致）。

语义约定：
- COMPARISON_FULL_SCOPE_WORDS：出现在「对比/比较」语境中的结构化
  范围词，语义均为「请求完整对比范围」（requested_scope=full）。
  实体层：仅在比较 cue 紧邻且 Repository 确认无候选（not_found）时
  按 operator 忽略（合法公司名不受影响）；
  计划层：命中任一范围词 → overview 预览 + requested_scope=full。
- COMPARISON_FULL_COMPOSITE_CUES：双维度复合词，仅计划层作为 full
  cue（实体 span 不会被提取为多字财务词，不进入实体层 operator 集合）。
"""

COMPARISON_FULL_SCOPE_WORDS: frozenset[str] = frozenset(
    {"全面", "综合", "多维", "全方位", "整体"}
)

COMPARISON_FULL_COMPOSITE_CUES: tuple[str, ...] = ("财务与风险", "财务和风险")
