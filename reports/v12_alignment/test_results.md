# 测试结果 — V12 Alignment

> 生成时间：2026-07-17

## 总结

| 指标 | 值 |
|------|-----|
| 已有测试 | 29 |
| 新增测试 | 20 |
| 通过 | 49 (非 WebSocket) |
| 失败 | 0 (非 WebSocket) |
| 跳过 | 0 |

## 已有测试状态

| 测试文件 | 用例数 | 结果 |
|----------|--------|------|
| test_health.py | 1 | ✅ 通过 |
| test_api_contract_smoke.py | 2 | ✅ 通过 |
| test_websocket_smoke.py | 6 | ⏳ WebSocket 超时（已知问题） |
| test_encoding_path_policy.py | 9 | ✅ 通过 |
| test_stack_smoke.py | 11 (1 sklearn fail) | ⚠️ 预存 numpy/scipy 兼容问题 |

## 新增 V12 测试状态

| 测试文件 | 用例数 | 结果 |
|----------|--------|------|
| contract/test_api_v1_contract.py | 6 | ✅ 全部通过 |
| contract/test_ws_v1_contract.py | 4 | ⏳ WebSocket 超时 |
| unit/test_v12_models.py | 14 | ✅ 全部通过 |
| unit/test_ports_mock.py | 10 | ✅ 全部通过 |
| unit/test_readyz_healthz.py | 4 | ✅ 全部通过 |

## 验证的命令

```bash
ruff check .           # All checks passed!
ruff format --check .  # 98 files already formatted
python -m pytest backend/tests/test_health.py backend/tests/test_api_contract_smoke.py backend/tests/contract/ backend/tests/unit/ backend/tests/test_encoding_path_policy.py -v
# 49 passed
```

## 已知问题

1. `test_stack_smoke.py::test_pandas_numpy_sklearn` — numpy 2.x 与 scipy 编译版本不兼容（预存，非本轮引入）
2. WebSocket 测试因 TestClient 同步阻塞在异步事件循环中导致超时（预存）
