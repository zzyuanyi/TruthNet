"""Profile 配置测试."""

from pathlib import Path

from app.core.enums import Profile, BackendType

_REPO_ROOT = Path(__file__).resolve().parents[3]


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


class TestEnvFileResolution:
    """env_file 必须与进程工作目录无关（P2 回归：cwd 绑定降级）。

    不依赖本机 .env 的具体内容（不读密钥/密码）。
    """

    def test_env_file_is_absolute_or_none(self):
        """env_file 要么指向仓库根目录 .env，要么为 None（文件不存在时）。"""
        from app.core.config import Settings

        env_file = Settings.model_config["env_file"]
        if env_file is not None:
            assert Path(env_file).is_absolute(), "env_file 必须是绝对路径"

    def test_env_file_points_to_repo_root_env(self):
        """env_file 指向仓库根目录的 .env（与 cwd 无关）。"""
        from app.core.config import Settings

        env_file = Settings.model_config["env_file"]
        assert env_file is None or Path(env_file) == _REPO_ROOT / ".env"

    def test_env_file_disabled_explicitly(self, monkeypatch):
        """Settings(_env_file='') 明确禁用 .env，保证 CI 单测隔离。

        注意：其他测试 import app.main 时其 load_dotenv 会把 .env 内容写入
        os.environ（dotenv 默认行为），而 pydantic-settings 的环境变量优先级
        高于 env_file。因此需先清除相关环境变量再验证文件禁用。
        """
        from app.core.config import Settings

        monkeypatch.delenv("TRUTHNET_PROFILE", raising=False)
        monkeypatch.delenv("SQL_BACKEND", raising=False)
        s = Settings(_env_file="")
        assert s.TRUTHNET_PROFILE == "lite"
        assert s.SQL_BACKEND == "sqlite"
