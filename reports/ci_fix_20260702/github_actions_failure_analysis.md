# GitHub Actions 失败分析

## 失败 run 信息

| Item | Value |
| --- | --- |
| run_id | 28571655027 |
| job_id | 84710590951 |
| failed_platform | windows-latest |
| failed_step | Ruff check |
| tests_before_failure | 29 passed (pytest 全过) |
| root_cause | Ruff lint violations (67 errors) |
| dependency_issue | no |
| platform_issue | no (同一代码其他平台也会失败；Windows 先跑完 ruff 步骤) |
| action | 修复所有 lint violations，本地 ruff check + format 通过后重新 push |

## 失败分布

```
F541 f-string-missing-placeholders: 49
F401 unused-import:                  9
E741 ambiguous-variable-name:        5
F841 unused-variable:                4
Total:                              67
```

## 影响文件

| 文件 | 错误数 | 主要问题 |
|------|--------|----------|
| scripts/env_bootstrap.py | ~20 | F541 f-string without placeholders |
| scripts/git_safety_check.py | ~6 | E741+F541 |
| scripts/end_session.py | ~4 | E741+F541 |
| scripts/start_session.py | ~2 | F541 |
| scripts/doctor.py | 1 | F841 |
| backend/app/main.py | 1 | F841 |
| backend/tests/test_encoding_path_policy.py | 4 | F401 |
| backend/tests/test_websocket_smoke.py | 5 | F401+F841 |
| backend/tests/test_stack_smoke.py | 1 | F401 |
| scripts/encoding_path_audit.py | 1 | F541 |

## 修复策略

1. F541 (f-string without placeholders): 批量 `ruff check --fix` → `ruff format`
2. F401 (unused import): 批量 `ruff check --fix`
3. E741 (ambiguous variable `l`): 手动重命名为 `sl`/`ln`/`line`
4. F841 (unused variable): 手动删除未使用的赋值

所有修复均未改变业务逻辑。无 `# noqa` 注释被添加。
