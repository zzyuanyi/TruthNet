# Ruff 修复报告

> 修复时间：2026-07-02
> 修复方式：`ruff check --fix` + 手动修复

## 修复清单

| File | Ruff Code | Count | Problem | Fix |
| ---- | --------- | ----- | ------- | --- |
| backend/app/main.py | F841 | 1 | `msg_type` unused | 删除该赋值行 |
| backend/tests/test_encoding_path_policy.py | F401 | 4 | `ast`, `sys` unused imports | 删除 import 行 |
| backend/tests/test_websocket_smoke.py | F401 | 5 | unused imports (`httpx`, `asyncio`) | 删除 import 行 |
| backend/tests/test_websocket_smoke.py | F841 | 2 | `client` unused | 删除赋值行 |
| scripts/doctor.py | F841 | 1 | `stderr_ok` unused | 删除该赋值行 |
| scripts/end_session.py | E741 | 2 | ambiguous variable `l` | 重命名为 `sl` |
| scripts/end_session.py | F541 | 1 | f-string without placeholders | 移除 `f` 前缀 |
| scripts/env_bootstrap.py | F541 | ~13 | f-strings without placeholders | 移除 `f` 前缀 |
| scripts/git_safety_check.py | E741 | 3 | ambiguous variable `l` | 重命名为 `ln` |
| scripts/git_safety_check.py | F541 | 1 | f-string without placeholders | 移除 `f` 前缀 |
| scripts/start_session.py | F541 | 1 | f-string without placeholders | 移除 `f` 前缀 |
| scripts/encoding_path_audit.py | F541 | 1 | f-string without placeholders | 移除 `f` 前缀 |

## 修复统计

- 自动修复: 58 errors (`ruff check --fix`)
- 手动修复: 9 errors (E741 重命名 + F841 删除 + F401 删除)
- `ruff format .`: 10 files reformatted
- 总计修复: 67 errors → 0

## 验证

```bash
$ ruff check .
All checks passed!

$ ruff format --check .
25 files already formatted

$ python -m pytest backend/tests -v
29 passed in 4.20s
```

## 未使用 `# noqa`

本次修复未添加任何 `# noqa` 注释。所有问题均通过代码修改解决。

## 未改变的业务语义

所有修复均为：
- 删除未使用的 import / 变量
- 修复变量命名
- 移除多余的 f-string 前缀

没有修改任何函数的输入输出、控制流或返回值。
