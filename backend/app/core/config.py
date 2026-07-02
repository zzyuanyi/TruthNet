"""应用配置（基于 pydantic-settings）。"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """TruthNet 应用配置。

    所有配置项可从环境变量或 .env 文件读取。
    """

    # 应用
    APP_NAME: str = "TruthNet"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # 服务
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    # LLM
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = ""

    # 嵌入模型
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_BASE_URL: str = ""
    EMBEDDING_MODEL: str = ""

    # 数据库
    SQLITE_PATH: str = "data/truthnet.db"

    # ChromaDB
    CHROMA_PERSIST_DIR: str = "data/chroma_db"

    # 日志
    LOG_LEVEL: str = "INFO"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
