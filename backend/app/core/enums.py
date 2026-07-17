"""V12 核心枚举定义."""

from enum import Enum


class RiskLevel(str, Enum):
    """风险等级."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ModuleStatus(str, Enum):
    """模块执行状态."""

    NOT_STARTED = "not_started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DEGRADED = "degraded"
    SKIPPED = "skipped"


class Profile(str, Enum):
    """运行 Profile."""

    LITE = "lite"
    FULL = "full"


class BackendType(str, Enum):
    """存储后端类型."""

    SQLITE = "sqlite"
    MYSQL = "mysql"
    NETWORKX = "networkx"
    NEO4J = "neo4j"
    CHROMA = "chroma"
    MOCK = "mock"
    DEEPSEEK = "deepseek"
    QWEN = "qwen"
