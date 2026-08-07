"""应用配置（基于 pydantic-settings）· V12 baseline."""

from pathlib import Path

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
