"""应用配置（基于 pydantic-settings）· V12 baseline."""

from pydantic_settings import BaseSettings


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

    # ===== 嵌入模型（兼容旧字段）=====
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = ""
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_BASE_URL: str = ""
    EMBEDDING_MODEL: str = ""

    # ===== API 版本控制 =====
    API_V1_ENABLED: bool = True
    LEGACY_API_ENABLED: bool = True

    # ===== 数据版本 =====
    DEFAULT_AS_OF: str = ""
    DATASET_VERSION: str = "mock-v12"
    RULE_SET_VERSION: str = "finance-rules-1.0.0"
    GRAPH_VERSION: str = "equity-mock-v12"

    # ===== 日志 =====
    LOG_LEVEL: str = "INFO"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
