# 集成测试报告

## 默认测试（无需外部服务）

| Test | Result |
|------|--------|
| test_chroma_persistent_write_read | PASS |
| test_chroma_persistent_small_data | PASS |
| test_readyz_returns_200 | PASS |
| test_readyz_has_required_fields | PASS |
| test_readyz_lite_profile_ready | PASS |
| test_readyz_full_profile_deps | PASS |

## 外部服务测试（需要 TRUTHNET_RUN_EXTERNAL_TESTS=1）

| Test | Status |
|------|--------|
| test_pymysql_import | skipped |
| test_sqlalchemy_import | skipped |
| test_mysql_connection_select_1 | skipped |
| test_mysql_write_smoke | skipped |
| test_neo4j_driver_import | skipped |
| test_neo4j_connectivity | skipped |
| test_neo4j_return_1 | skipped |
| test_neo4j_write_smoke | skipped |

## 如何启用外部测试

```bash
# Bash
export TRUTHNET_RUN_EXTERNAL_TESTS=1
conda run -n truthnet python -m pytest backend/tests/integration -v -m "integration and external"

# PowerShell
$env:TRUTHNET_RUN_EXTERNAL_TESTS="1"
conda run -n truthnet python -m pytest backend/tests/integration -v -m "integration and external"
```
