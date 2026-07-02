# 完整工作栈 Smoke 测试报告

> 测试时间：2026-07-02
> Python：3.11.15 (truthnet conda env)

## 测试结果汇总

| Layer    | Item                 | Status                | Evidence | Remaining Risk |
| -------- | -------------------- | --------------------- | -------- | -------------- |
| Backend  | HTTP /health         | passed                | 29/29 tests pass, doctor 39/39 | 无 |
| Backend  | POST /api/v1/chat    | passed                | test_api_contract_smoke.py PASS | mock 占位，非真实 Agent |
| Backend  | WebSocket            | passed                | test_websocket_smoke.py 7/7 PASS | mock 占位，非真实 Agent |
| Backend  | 编码/路径策略        | passed                | test_encoding_path_policy.py 9/9 PASS | — |
| Data     | SQLite               | passed                | test_stack_smoke.py PASS | 内存数据库，非持久化 |
| Data     | NetworkX             | passed                | test_stack_smoke.py PASS | 小规模图，非大规模 |
| Data     | ChromaDB             | passed                | test_stack_smoke.py PASS | 临时目录，非持久化 |
| Data     | pandas/numpy/sklearn | passed                | test_stack_smoke.py PASS | — |
| Agent    | LangGraph mini graph | passed                | test_stack_smoke.py PASS | 单节点图，非多 Agent |
| Script   | doctor.py            | passed                | 39/39 PASS | — |
| Script   | encoding_path_audit  | passed_with_warnings  | 8 项 WARNING 均为已知假阳性 | 正则审计有固有假阳性 |
| Script   | git_safety_check     | passed_with_warnings  | main 分支 WARN（预期） | 当前在 main 执行规范硬化 |
| Script   | env_bootstrap        | passed                | truthnet 3.11.15 就绪 | — |
| Script   | pre-commit           | passed                | 6/6 hooks PASS | ruff 需要 staged files |
| Frontend | package install      | not_run               | pnpm 未安装 | 需用户确认安装 pnpm |
| Frontend | build                | not_run               | pnpm 未安装，前端未初始化 | 需用户确认后初始化 |
| CI       | workflow exists      | passed                | .github/workflows/ci.yml 已更新 | — |
| CI       | actual remote run    | not_run               | 尚未 push 到 GitHub | 需 push 后触发 |

## 后端详细结果

### HTTP /health (PASS)
```
GET /health → 200
{ "code": 0, "data": { "status": "healthy", "version": "0.1.0" }, ... }
```

### POST /api/v1/chat (PASS)
```
POST /api/v1/chat → 200
{ "code": 0, "data": { "answer": "Mock...", "risk_score": 0.0, ... }, ... }
```

### WebSocket /api/v1/chat/ws (PASS — 新实现)
```
WS /api/v1/chat/ws → 101 Switching Protocols
→ status: "正在分析: ..."
→ partial_answer x N (模拟流式)
→ final_answer: { "answer": "...", "risk_score": 0.0, ... }
→ error (invalid JSON / missing question)
```

### 技术栈 14/14 Smoke (PASS)
FastAPI, Pydantic, SQLite, NetworkX (4-hop chain), ChromaDB, LangGraph, pandas/numpy/sklearn, dotenv, pydantic-settings, ruff, pre-commit — 全部通过。

## 前端状态

### 路径 B：不初始化前端

**原因**：
- Node.js v26.1.0 可用
- pnpm **未安装**
- 根据 Prompt3 规范："仅在 Node 和 pnpm 可用时执行"
- 不强制安装 pnpm（需用户确认）

**当前状态**：
- `frontend/README.md` 已有技术栈和初始化说明
- 更新为标注 "待 pnpm 安装后初始化"
- 后端 HTTP/WebSocket 已可测
- 前端初始化待用户确认后执行

### 前端初始化命令（待用户执行）

```bash
npm install -g pnpm
cd frontend
pnpm create vite . --template react-ts
pnpm install
pnpm dev
```

## CI 状态

- `.github/workflows/ci.yml` 已更新：3 平台 × 3.11 + 可选 frontend job
- 新增步骤：`encoding_path_audit`, `git_safety_check`, `env_bootstrap`
- CI 尚未在远程实际运行（not_run，未 push）

## 结论

完整工作栈最小闭环已验证。后端 29/29 测试全过，doctor 39/39 PASS。WebSocket 最小 mock 端点已实现并通过测试。前端因 pnpm 不可用而未初始化，明确标注 not_run 及原因。

**状态：PASSED（前端 not_run 有合理原因）**
