"""行业分类补全 — 常量、枚举与版本化口径（档案 v1.1 §2）。

本模块只放静态口径，不 import 任何业务依赖，保证测试可隔离。
"""

from __future__ import annotations

from enum import Enum

# ── 口径版本 ──────────────────────────────────────────────
# 申万二级→一级静态映射表版本；表内容变更必须递增版本号并在报告记录。
# v2（2026-08-14）：并入官方 sw_index_second_info() 131 条（与迁移表零冲突，共 133 条）。
L2_TO_L1_MAPPING_VERSION = "sw-l2-to-l1-v2"
# 行业来源值（与库内历史值对齐：单数 research_report，见档案 v1.1 §2.1）
SOURCE_RESEARCH_REPORT = "research_report"
SOURCE_AKSHARE = "akshare"
SOURCE_NAME_INFERENCE_PREFIX = "name_inference:"
# provider 名
PROVIDER_AKSHARE = "akshare"

# 默认 staging/cache 根目录（相对代码仓库根）
DEFAULT_CACHE_DIR = "data/processed/industry_fill_runs"

# 进度打印间隔（档案 §6.2）
PROGRESS_EVERY = 200

# 单代码最小请求间隔（秒，防限流；provider 内实现）
DEFAULT_RATE_LIMIT_SLEEP = 0.05

# 自适应节流硬边界：provider 并发被钳制在此范围（throttle.RateController 引用）
MIN_CONCURRENCY = 1
MAX_CONCURRENCY = 8

# 允许重试的异常类别（档案 §6.3）
RETRYABLE_EXC_TYPES = (TimeoutError, ConnectionError, OSError)


class QueryStatus(str, Enum):
    """staging 记录 query_status 唯一取值（档案 §2.2）。"""

    SUCCESS = "success"
    EMPTY = "empty"
    UNMAPPED = "unmapped"
    ERROR = "error"
    SKIPPED = "skipped"


# 申万一级行业允许集合（31 个，2021 版申万一级行业）。
# 来源：①项目 V12 方案与研报数据实测值域（2026-08-14 只读核对 31 个合法值）；
# ②申万 2021 版一级行业清单。行业允许集合不得从本次返回值动态扩展（档案 §5.2）。
SW_L1_ALLOWED: frozenset[str] = frozenset(
    {
        "农林牧渔",
        "基础化工",
        "钢铁",
        "有色金属",
        "电子",
        "汽车",
        "家用电器",
        "食品饮料",
        "纺织服饰",
        "轻工制造",
        "医药生物",
        "公用事业",
        "交通运输",
        "房地产",
        "商贸零售",
        "社会服务",
        "银行",
        "非银金融",
        "综合",
        "建筑材料",
        "建筑装饰",
        "电力设备",
        "国防军工",
        "计算机",
        "传媒",
        "通信",
        "煤炭",
        "石油石化",
        "环保",
        "美容护理",
        "机械设备",
    }
)
