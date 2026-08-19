"""应用配置（基于 pydantic-settings）· V12 baseline."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings

# 仓库根目录下的 .env（绝对路径，与进程工作目录无关）
_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILE = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    """TruthNet 应用配置。

    所有配置项可从环境变量或 .env 文件读取。
    V12 新增：TRUTHNET_PROFILE, SQL_BACKEND, GRAPH_BACKEND, VECTOR_BACKEND, LLM_BACKEND,
    MySQL/Neo4j 连接配置, DeepSeek/Qwen Provider 配置, 数据版本字段。
    """

    # ===== Profile =====
    TRUTHNET_PROFILE: str = "lite"  # lite | full

    # ===== 应用 =====
    APP_NAME: str = "TruthNet"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # ===== 服务 =====
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    # ===== 数据库后端 =====
    SQL_BACKEND: str = "sqlite"  # sqlite | mysql
    SQLITE_PATH: str = "data/truthnet.db"

    # MySQL（仅 full profile）
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_DATABASE: str = "truthnet"
    MYSQL_USER: str = "truthnet"
    MYSQL_PASSWORD: str = ""

    # MySQL 测试库（external 测试强制隔离）
    # 默认全空：mysql 模式跑 pytest 必须显式指定三件套，否则 fail-fast 拒绝
    # （测试不得直连演示库；守卫见 backend/tests/conftest.py）
    MYSQL_TEST_DATABASE: str = ""
    MYSQL_TEST_USER: str = ""
    MYSQL_TEST_PASSWORD: str = ""

    # ===== 图数据库后端 =====
    GRAPH_BACKEND: str = "networkx"  # networkx | neo4j

    # Neo4j（仅 full profile）
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""

    # ===== 向量数据库 =====
    VECTOR_BACKEND: str = "chroma"
    CHROMA_PERSIST_DIR: str = "data/chroma_db"

    # ===== LLM Provider =====
    LLM_BACKEND: str = "mock"  # mock | deepseek | qwen

    # DeepSeek
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # Qwen
    QWEN_API_KEY: str = ""
    QWEN_BASE_URL: str = ""
    QWEN_MODEL: str = "qwen-max"

    # LLM 回退与重试
    LLM_FALLBACK_BACKEND: str = ""  # 空 = 无回退；"qwen" | "mock"
    LLM_RETRY_MAX_ATTEMPTS: int = 2  # 共 2 次尝试 = 1 次重试
    LLM_RETRY_MIN_WAIT: float = 1.0  # 秒
    LLM_RETRY_MAX_WAIT: float = 5.0  # 秒
    LLM_REQUEST_TIMEOUT: int = (
        60  # 秒 — read 超时（长文本生成 20-60s）；connect 超时固定 10s 快速失败
    )
    LLM_MAX_CONCURRENCY: int = 4
    LLM_QUEUE_TIMEOUT_SECONDS: float = 5.0

    # ===== Web Search Provider（Phase E 会5 B1 联网搜索）=====
    # off（默认）= 关闭，行为与现状完全一致；mock = 本地测试/演示；
    # bocha = 博查真实联网（中文通用搜索，未拍板保持 off）；
    # anysearch = AnySearch A 股垂类（finance 垂直域：行情/公告/三表，
    #   8/19 接入，队长拍板只做垂类不做通用；免费注册 Key 见
    #   `竞赛管理/docs/reference/AnySearch-API规范.md` §2.4）。
    WEB_SEARCH_BACKEND: str = "off"  # off | mock | bocha | anysearch
    WEB_SEARCH_API_KEY: str = ""  # bocha/通用 Key（Bearer）
    # AnySearch 专用 Key（as_sk_*，独立于 bocha；匿名可用但限流低）
    ANYSEARCH_API_KEY: str = ""
    WEB_SEARCH_BASE_URL: str = "https://api.bochaai.com/v1/web-search"
    WEB_SEARCH_TIMEOUT_SECONDS: float = 10.0  # 单次联网墙钟预算（秒）
    WEB_SEARCH_MAX_RESULTS: int = 5  # 每 query 最多返回命中数
    WEB_SEARCH_RATE_LIMIT_RPM: int = 30  # 限流：每分钟最多请求数（fail-fast）

    # ===== 舆情影响分析（B2 批次 C）=====
    # 有界执行器 worker 数 + 有界信号量在途数上限。在途数（信号量）满时
    # 快速返回 impacts=[] + IMPACT_BUSY，不无限排队、不占用全局唯一 worker。
    EVENT_IMPACT_MAX_WORKERS: int = 3
    EVENT_IMPACT_MAX_INFLIGHT: int = 8

    # ===== 实体解析（v3.1 冻结方案）=====
    # 唯一命中自动锁定策略：exact_only | safe_reverse_contains | confirm_all_heuristic
    ENTITY_UNIQUE_MATCH_POLICY: str = "safe_reverse_contains"
    # 语义选择发布模式：off（确定性，生产默认）| suggest（演示/答辩：
    # mentionness 非公司判定生效 + selector LLM 推荐不自动绑定）| auto（自动绑定，仅离线）
    # v3.3.1 §9.1：Literal 校验 + lifespan 校验（main._validate_release_mode：
    # off/suggest 允许启动，auto 拒绝全局启动；离线 runner 显式构造 selector）
    ENTITY_SEMANTIC_SELECTION_MODE: Literal["off", "suggest", "auto"] = "off"
    # v3.3 批次 C：首次裁决 + repair 重试共享的总墙钟预算（离线 suggest/
    # auto 评测；生产在线 auto 必须另行按 P95 设置，不直接复用）。
    # v3.3.1 §9.4：单次调用不再被 5s 默认截断——timeout 直接取剩余预算
    ENTITY_SEMANTIC_SELECTION_TOTAL_BUDGET_SECONDS: float = 20.0
    ENTITY_SEMANTIC_SELECTION_MAX_SEMANTIC_ATTEMPTS: int = 2
    # v3.3.2-R1 §7.4：低置信 query 主体语义解析发布模式
    # off=零调用（生产默认）| shadow=调用并记录权威不变 | fallback=应用
    ENTITY_QUERY_INTERPRETER_MODE: Literal["off", "shadow", "fallback"] = "off"
    # 单次硬预算（§7.4：不 repair、不重试；禁止为真机通过放宽到 20s）
    ENTITY_QUERY_INTERPRETER_BUDGET_SECONDS: float = 5.0

    # ===== 轻量比较（v3.3.4 Preview First，方案 §2.4）=====
    # 前端多主体对比页是否可用：False（默认，前端尚未集成）→ 三家及以上
    # 只发 choose_comparison_pair（选两家）；前端实现多主体页后置 True，
    # 改为发 open_multi_company_comparison（携带全部去重代码）。
    COMPARISON_MULTI_PAGE_ENABLED: bool = False

    # ===== 嵌入模型（兼容旧字段）=====
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = ""
    # ===== API 版本控制 =====
    API_V1_ENABLED: bool = True
    LEGACY_API_ENABLED: bool = True

    # ===== 数据流水线 =====
    DATA_ROOT: str = "data/raw"
    PROCESSED_DATA_DIR: str = "data/processed"

    # ===== 嵌入模型 =====
    EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"
    EMBEDDING_CACHE_DIR: str = "data/model_cache"

    # ===== 数据版本 =====
    DEFAULT_AS_OF: str = ""
    DATASET_VERSION: str = "mock-v12"
    RULE_SET_VERSION: str = "finance-rules-1.0.0"
    GRAPH_VERSION: str = "equity-mock-v12"

    # ===== WS 事件缓冲（Phase D #6 断线恢复）=====
    WS_EVENT_BUFFER_MAX_EVENTS: int = 2000  # 每会话事件缓冲上限（内存受限）
    WS_EVENT_BUFFER_TTL_SECONDS: int = 3600  # 事件 TTL（秒），过期被 expire 清除
    WS_SESSION_IDLE_TTL_SECONDS: int = 7200  # 会话空闲回收 TTL（秒）
    WS_CANCEL_ACK_TIMEOUT_SECONDS: float = 2.0  # turn.cancel 确认时限（验收 ≤2s）
    WS_JANITOR_INTERVAL_SECONDS: int = 300  # WS janitor 周期（缓冲 TTL + 空闲会话回收）

    # ===== 回答生成（#7 确定性输出优先）=====
    ANSWER_POLISH_ENABLED: bool = (
        False  # REST LLM 润色开关（默认关闭；开启时仍有事实校验回退）
    )

    # ===== 远期记忆提炼（Phase D #15）=====
    MEMORY_RECENT_TURNS: int = 10  # 近期 N 轮全量加载；更早进入摘要
    MEMORY_SUMMARY_MAX_CHARS: int = 2000  # 摘要最大字符数
    MEMORY_SUMMARY_MAX_SOURCE_TURNS: int = 50  # 摘要最多引用来源轮次数
    MEMORY_SUMMARY_VERSION: str = "memory-v1"  # 摘要结构版本
    MEMORY_STRATEGY: str = (
        "summary_plus_recent"  # none | recent_only | summary_plus_recent
    )

    # ===== PDF 报告（Phase D #8）=====
    REPORT_ROOT_DIR: str = "data/reports"  # 报告文件根目录（相对项目根解析）
    REPORT_MAX_CONCURRENCY: int = 2  # 并发报告生成数
    REPORT_JOB_STALE_SECONDS: int = 1800  # running 超过该时长视为卡死（重启恢复）

    # ===== 深度数值冲突检测（Phase D #2）=====
    CV_NUM_01_CF_TO_PROFIT_THRESHOLD: float = 0.5  # 现金流/净利润比值阈值
    CV_NUM_01_MIN_PERIODS: int = 3  # 至少需连续观察的有效期数
    CV_NUM_02_OWNERSHIP_TOLERANCE: float = (
        1.0  # MySQL 股东表与 Neo4j 边比例允许误差（pp）
    )

    # ===== 日志 =====
    LOG_LEVEL: str = "INFO"

    model_config = {
        # 绝对路径：无论从哪个工作目录启动都指向仓库根目录 .env；
        # .env 不存在时退化为 None（纯默认值 + 环境变量），不报错
        "env_file": _ENV_FILE if _ENV_FILE.exists() else None,
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
