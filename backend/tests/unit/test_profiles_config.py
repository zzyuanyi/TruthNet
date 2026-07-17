"""Profile 配置测试."""

from app.core.enums import Profile, BackendType


class TestProfileEnums:
    """枚举值测试（不需要读取 .env）."""

    def test_enum_profile_values(self):
        assert Profile.LITE == "lite"
        assert Profile.FULL == "full"

    def test_enum_backend_values(self):
        assert BackendType.SQLITE == "sqlite"
        assert BackendType.MYSQL == "mysql"
        assert BackendType.NETWORKX == "networkx"
        assert BackendType.NEO4J == "neo4j"
        assert BackendType.MOCK == "mock"
        assert BackendType.DEEPSEEK == "deepseek"
        assert BackendType.QWEN == "qwen"

    def test_enum_module_status(self):
        from app.core.enums import ModuleStatus

        assert ModuleStatus.COMPLETED == "completed"
        assert ModuleStatus.FAILED == "failed"

    def test_enum_risk_level(self):
        from app.core.enums import RiskLevel

        assert RiskLevel.LOW == "low"
        assert RiskLevel.HIGH == "high"
