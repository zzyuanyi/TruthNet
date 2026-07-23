"""pytest 全局配置 — V12."""


def pytest_configure(config):
    """注册自定义 markers."""
    config.addinivalue_line(
        "markers", "integration: integration tests requiring external services"
    )
    config.addinivalue_line(
        "markers", "external: tests requiring external services (MySQL, Neo4j)"
    )
    config.addinivalue_line("markers", "mysql: MySQL integration tests")
    config.addinivalue_line("markers", "neo4j: Neo4j integration tests")
    config.addinivalue_line(
        "markers", "full_profile: tests requiring full profile (MySQL + Neo4j)"
    )
