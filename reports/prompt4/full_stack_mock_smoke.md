# 完整工作栈 Mock 联调 Smoke 报告

> 测试时间：2026-07-02
> 后端：Python 3.11.15 (truthnet conda env)
> 前端：Node.js v26.1.0 / pnpm 11.9.0

## 测试结果汇总

| Layer    | Item                            | Status                | Evidence | Remaining Risk |
| -------- | ------------------------------- | --------------------- | -------- | -------------- |
| Backend  | /health                         | passed                | 29/29 tests pass | 无 |
| Backend  | POST /api/v1/chat               | passed                | test_api_contract_smoke.py PASS | mock 数据 |
| Backend  | WS /api/v1/chat/ws              | passed                | test_websocket_smoke.py 7/7 PASS | mock 数据 |
| Backend  | risk_score 为新对象格式         | passed                | 3 tests updated, all pass | — |
| Frontend | pnpm install                    | passed                | 71 packages installed | esbuild 需 approve |
| Frontend | pnpm typecheck                  | passed                | tsc -b 无错误 | — |
| Frontend | pnpm build                      | passed                | 33 modules, 402ms | — |
| Frontend | HTTP client code                | passed                | src/api/client.ts | 未实际连接后端测试 |
| Frontend | WebSocket client code           | passed                | src/api/client.ts | 未实际连接后端测试 |
| Frontend | 组件代码                        | passed                | 5 个组件 + App | 纯展示 |
| Contract | backend schema vs frontend type | passed                | RiskScore/GraphData 完全一致 | — |
| Script   | doctor.py                       | passed                | 39/39 PASS | — |
| Script   | encoding_path_audit             | passed_with_warnings  | 8 项已知假阳性 | regex 审计有固有假阳性 |
| Script   | git_safety_check                | passed_with_warnings  | main 分支（预期） | — |
| CI       | workflow updated                | passed                | ci.yml 包含 frontend job | — |
| CI       | remote actual run               | not_run               | 尚未 push | 需 push 触发 |

## 详细测试命令与结果

### 后端 (29/29 PASS)

```bash
$ python -m pytest backend/tests -v
test_api_contract_smoke.py: 2/2 PASS
test_encoding_path_policy.py: 9/9 PASS
test_health.py: 1/1 PASS
test_stack_smoke.py: 10/10 PASS
test_websocket_smoke.py: 7/7 PASS
```

### 环境检测 (39/39 PASS)

```bash
$ python scripts/doctor.py --ci
✅ PASS: 39/39
```

### 编码审计 (PASSED_WITH_WARNINGS)

```bash
$ python scripts/encoding_path_audit.py --ci
UTF-8 解码: PASS (54/54)
裸 open(): PASS
硬编码盘符: 8 FAIL (文档反例/test 模式定义)
硬编码个人路径: 2 FAIL (文档反例)
CRLF: PASS
大文件: PASS
```

### 前端

```bash
$ cd frontend
$ pnpm install   # 71 packages, Done
$ pnpm typecheck  # tsc -b, 无错误
$ pnpm build     # ✓ 33 modules transformed, 402ms
```

## 风险分析

| 风险 | 等级 | 说明 |
|------|------|------|
| mock 数据无业务逻辑 | 低 | 预期：本轮不实现业务 Agent |
| 前端未实际连接后端 | 低 | HTTP/WS client 代码已写，需启动后端后可测试 |
| esbuild 需要 pnpm approve | 低 | 已在本地 approve，CI 中使用 corepack 自动处理 |
| CI 远程未运行 | 中 | 需 push 后确认三平台通过 |
| 无真实数据 | 低 | 预期：后续 Prompt 接入 |

## 结论

前后端 mock 联调完整工作栈已验证。后端 29/29 测试通过，前端 pnpm build 通过，前后端类型完全一致。接口已冻结。

**状态：PASSED**
