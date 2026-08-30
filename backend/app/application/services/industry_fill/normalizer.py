"""行业字段标准化与申万层级映射（档案 v1.1 §5.2 / §8）。

口径：
- industry_l1 只能是 SW_L1_ALLOWED 中的申万一级名称；
- industry_l2 只能来自 L2_TO_L1 静态映射表或显式别名表；
- 未知二级一律返回 unmapped，禁止运行时自动扩展映射表（P1-4）。
"""

from __future__ import annotations

import unicodedata

from app.application.services.industry_fill.constants import (
    L2_TO_L1_MAPPING_VERSION,
    SW_L1_ALLOWED,
)


def normalize_optional_text(value: object) -> str | None:
    """统一空值清洗（档案 §8）：None/nan/none/null/空白 → None，其余返回原文去空白。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    return text


def _normalize_halfwidth(text: str) -> str:
    """NFKC 归一（全角→半角、兼容字符），再去除内部空白。"""
    return "".join(unicodedata.normalize("NFKC", text).split())


# 申万二级 → 申万一级 静态映射表（133 条）。
# 来源（2026-08-14 人工审核固化，映射版本 v2）：
#   ① 申万二级行业指数信息表 sw_index_second_info()（akshare 1.18.91，131 条，
#      上级行业列为官方一级归属）——与迁移表零冲突；
#   ② 迁移自历史 scripts/task5_industry_fill.py:100-141 的硬编码表
#      （PR #9-#11 决策矩阵 accept_with_rework 保留部分，约 38 条，全部被①覆盖或兼容）。
# 禁止任何运行时"学习"或动态扩展（档案 v1.1 P1-4）。
L2_TO_L1: dict[str, str] = {
    "IT服务Ⅱ": "计算机",
    "一般零售": "商贸零售",
    "专业工程": "建筑装饰",
    "专业服务": "社会服务",
    "专业连锁Ⅱ": "商贸零售",
    "专用设备": "机械设备",
    "个护用品": "美容护理",
    "中药Ⅱ": "医药生物",
    "乘用车": "汽车",
    "互联网电商": "商贸零售",
    "休闲食品": "食品饮料",
    "体育Ⅱ": "社会服务",
    "保险Ⅱ": "非银金融",
    "元件": "电子",
    "光伏设备": "电力设备",
    "光学光电子": "电子",
    "其他家电Ⅱ": "家用电器",
    "其他电子Ⅱ": "电子",
    "其他电源设备Ⅱ": "电力设备",
    "养殖业": "农林牧渔",
    "军工电子Ⅱ": "国防军工",
    "农业综合Ⅱ": "农林牧渔",
    "农产品加工": "农林牧渔",
    "农化制品": "基础化工",
    "农商行Ⅱ": "银行",
    "冶钢原料": "钢铁",
    "出版": "传媒",
    "动物保健Ⅱ": "农林牧渔",
    "包装印刷": "轻工制造",
    "化妆品": "美容护理",
    "化学制品": "基础化工",
    "化学制药": "医药生物",
    "化学原料": "基础化工",
    "化学纤维": "基础化工",
    "医疗器械": "医药生物",
    "医疗服务": "医药生物",
    "医疗美容": "美容护理",
    "医药商业": "医药生物",
    "半导体": "电子",
    "厨卫电器": "家用电器",
    "商用车": "汽车",
    "国有大型银行Ⅱ": "银行",
    "地面兵装Ⅱ": "国防军工",
    "城商行Ⅱ": "银行",
    "基础建设": "建筑装饰",
    "塑料": "基础化工",
    "多元金融": "非银金融",
    "家居用品": "轻工制造",
    "家电零部件Ⅱ": "家用电器",
    "小家电": "家用电器",
    "小金属": "有色金属",
    "工业金属": "有色金属",
    "工程咨询服务Ⅱ": "建筑装饰",
    "工程机械": "机械设备",
    "广告营销": "传媒",
    "影视院线": "传媒",
    "房地产开发": "房地产",
    "房地产服务": "房地产",
    "房屋建设Ⅱ": "建筑装饰",
    "摩托车及其他": "汽车",
    "教育": "社会服务",
    "数字媒体": "传媒",
    "文娱用品": "轻工制造",
    "旅游及景区": "社会服务",
    "旅游零售Ⅱ": "商贸零售",
    "普钢": "钢铁",
    "服装家纺": "纺织服饰",
    "林业Ⅱ": "农林牧渔",
    "橡胶": "基础化工",
    "水泥": "建筑材料",
    "汽车服务": "汽车",
    "汽车零部件": "汽车",
    "油服工程": "石油石化",
    "油气开采Ⅱ": "石油石化",
    "消费电子": "电子",
    "渔业": "农林牧渔",
    "游戏Ⅱ": "传媒",
    "炼化及贸易": "石油石化",
    "焦炭Ⅱ": "煤炭",
    "煤炭开采": "煤炭",
    "照明设备Ⅱ": "家用电器",
    "燃气Ⅱ": "公用事业",
    "物流": "交通运输",
    "特钢Ⅱ": "钢铁",
    "环保设备Ⅱ": "环保",
    "环境治理": "环保",
    "玻璃玻纤": "建筑材料",
    "生物制品": "医药生物",
    "电力": "公用事业",
    "电子化学品Ⅱ": "电子",
    "电机Ⅱ": "电力设备",
    "电池": "电力设备",
    "电网设备": "电力设备",
    "电视广播Ⅱ": "传媒",
    "白色家电": "家用电器",
    "白酒Ⅱ": "食品饮料",
    "种植业": "农林牧渔",
    "纺织制造": "纺织服饰",
    "综合Ⅱ": "综合",
    "股份制银行Ⅱ": "银行",
    "能源金属": "有色金属",
    "自动化设备": "机械设备",
    "航天装备Ⅱ": "国防军工",
    "航海装备Ⅱ": "国防军工",
    "航空机场": "交通运输",
    "航空装备Ⅱ": "国防军工",
    "航运港口": "交通运输",
    "装修建材": "建筑材料",
    "装修装饰Ⅱ": "建筑装饰",
    "计算机设备": "计算机",
    "证券Ⅱ": "非银金融",
    "调味发酵品Ⅱ": "食品饮料",
    "贵金属": "有色金属",
    "贸易Ⅱ": "商贸零售",
    "轨交设备Ⅱ": "机械设备",
    "软件开发": "计算机",
    "通信服务": "通信",
    "通信设备": "通信",
    "通用设备": "机械设备",
    "造纸": "轻工制造",
    "酒店餐饮": "社会服务",
    "金属新材料": "有色金属",
    "钢铁": "钢铁",
    "铁路公路": "交通运输",
    "银行Ⅱ": "银行",
    "非白酒": "食品饮料",
    "非金属材料Ⅱ": "基础化工",
    "风电设备": "电力设备",
    "食品加工": "食品饮料",
    "饮料乳品": "食品饮料",
    "饰品": "纺织服饰",
    "饲料": "农林牧渔",
    "黑色家电": "家用电器",
}

# 显式别名表（东财行业名 → 申万二级名，人工审核的 curated 条目，非运行时学习）。
# 档案 v1.1 §5.2：东财名与申万二级名差异（如"白酒" vs "白酒Ⅱ"）。
_L2_ALIASES: dict[str, str] = {
    "白酒": "白酒Ⅱ",
    "中药": "中药Ⅱ",
    "银行": "银行Ⅱ",
    "证券": "证券Ⅱ",
    "保险": "保险Ⅱ",
    "综合": "综合Ⅱ",
    "IT服务": "IT服务Ⅱ",
    "轨交设备": "轨交设备Ⅱ",
}

# 模块导入时校验映射表口径（硬编码表 L1 必须全部在允许集合内，fail loudly）
_INVALID = sorted({v for v in L2_TO_L1.values()} - SW_L1_ALLOWED)
if _INVALID:  # pragma: no cover - 配置错误防御
    raise AssertionError(f"L2_TO_L1 含非法一级行业: {_INVALID}")


def normalize_l1(value: object) -> str | None:
    """申万一级校验：清洗后必须命中允许集合，否则 None（视为 unmapped）。"""
    text = normalize_optional_text(value)
    if text is None:
        return None
    half = _normalize_halfwidth(text)
    for allowed in SW_L1_ALLOWED:
        if _normalize_halfwidth(allowed) == half:
            return allowed
    return None


def normalize_l2(value: object) -> str | None:
    """申万二级清洗：去空白、NFKC 归一；不校验是否在映射表（映射在 l2_to_l1 做）。"""
    return normalize_optional_text(value)


def map_l2_to_l1(l2_raw: object) -> tuple[str | None, str | None]:
    """二级→一级映射。

    返回 (industry_l1, industry_l2)；映射失败返回 (None, 归一化后的二级值)，
    由调用方标记 unmapped。禁止对未知二级做任何猜测。
    """
    l2 = normalize_l2(l2_raw)
    if not l2:
        return None, None
    key = _normalize_halfwidth(l2)
    # 1) 显式别名（curated）
    for alias, target in _L2_ALIASES.items():
        if _normalize_halfwidth(alias) == key:
            return L2_TO_L1[target], target
    # 2) 精确命中映射表（NFKC 归一后比较）
    for candidate, l1 in L2_TO_L1.items():
        if _normalize_halfwidth(candidate) == key:
            return l1, candidate
    return None, l2


def mapping_version() -> str:
    return L2_TO_L1_MAPPING_VERSION
