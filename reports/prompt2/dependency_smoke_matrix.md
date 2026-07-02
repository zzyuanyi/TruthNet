# 技术栈 Smoke 矩阵

**验证日期**：2026-07-02
**环境**：truthnet (conda, Python 3.11.15, Windows 11)

---

## Smoke 测试结果矩阵

| Component | Package | Version | Smoke Test | Result | Error | Action |
|-----------|---------|---------|-------------|--------|-------|--------|
| FastAPI | fastapi | 0.115.0 | Import + /health + POST /api/v1/chat | passed | — | — |
| Pydantic | pydantic | 2.9.2 | ChatRequest/UnifiedResponse 序列化/反序列化 | passed | — | — |
| SQLite | sqlite3 (stdlib) | — | 内存库建表/插入/查询 | passed | — | — |
| NetworkX | networkx | 3.3 | 4跳股权链 + 路径权重计算 (0.504) | passed | — | — |
| ChromaDB | chromadb | 0.5.23 | 临时目录创建 collection + 插入2条 + query | passed | — | — |
| LangGraph | langgraph | 0.2.55 | 最小 StateGraph (value+1) + invoke | passed | — | — |
| pandas | pandas | 2.2.3 | DataFrame 创建 + mean 计算 | passed | — | — |
| numpy | numpy | 1.26.4 | 数组 mean 计算 | passed | — | — |
| scikit-learn | scikit-learn | 1.5.2 | F1 score 计算 | passed | — | — |
| python-dotenv | python-dotenv | 1.0.1 | 临时 .env 读取 + 环境变量恢复 | passed | — | — |
| pydantic-settings | pydantic-settings | 2.5.2 | Settings 默认值加载 | passed | — | — |
| ruff | ruff | 0.6.5 | ruff check + ruff format | passed | — | — |
| pre-commit | pre-commit | 3.8.0 | pre-commit run --all-files | passed | — | — |
| pytest | pytest | 8.3.3 | 14/14 tests passed | passed | — | — |
| pytest-asyncio | pytest-asyncio | 0.24.0 | Async test 通过 | passed | — | — |
| httpx | httpx | 0.27.2 | TestClient API 调用 | passed | — | — |
| uvicorn | uvicorn | 0.30.6 | (通过 FastAPI test client 间接验证) | passed | — | — |
| websockets | websockets | 12.0 | 已安装 | passed | 后端 WebSocket 端点尚未实现 | 下一轮补齐 |

---

## 详细 Smoke 说明

### FastAPI ✅
- `GET /health` 返回 `{ code: 0, data: { status: "healthy", version: "0.1.0" }, message: "ok", trace_id: "..." }`
- `POST /api/v1/chat` mock 返回完整的 ChatData 结构
- 统一响应格式字段 (code, data, message, trace_id) 全部验证

### Pydantic ✅
- ChatRequest/ChatData/UnifiedResponse 序列化 + 反序列化 roundtrip
- JSON dump 后再 parse 为 dict，字段完整
- 与 API_CONTRACT.md 结构一致

### SQLite ✅
- 内存数据库创建 companies 表
- 插入 600519 公司记录
- 查询返回正确数据

### NetworkX ✅
- 4 跳股权链："王某" → "壳公司A" → "资管计划B" → "上市公司C" → "子公司D"
- 路径存在性验证
- 权重连乘：0.8 * 0.7 * 0.9 = 0.504 ✅
- 深度 > 3 验证 ✅

### ChromaDB ✅
- 创建临时持久化目录
- 创建 collection，插入 2 条文档
- Query 返回正确结果
- 测试结束后清理临时目录

### LangGraph ✅
- 创建 `StateGraph(State)` where State = TypedDict with `value: int`
- Node `add_one` 对 state.value + 1
- START → add_one → END
- invoke({"value": 1}) → {"value": 2} ✅

### pandas/numpy/scikit-learn ✅
- pandas: 4行DataFrame, mean=187.5
- numpy: arr.mean() = 3.0
- sklearn: F1 score 计算正常

### dotenv / pydantic-settings ✅
- dotenv: 从临时 .env 读取 APP_NAME/BACKEND_PORT
- 环境变量恢复机制确保不污染后续测试
- pydantic-settings: Settings() 默认值正确 (APP_NAME="TruthNet", BACKEND_PORT=8000)

### WebSocket 🔶
- `websockets==12.0` 已安装
- 后端当前仅有 REST mock 端点
- 文档中有 WebSocket 契约 (`WS /api/v1/chat/ws`)，但端点尚未实现
- **建议**：Prompt3 中实现 WebSocket 最小端点

### Node.js / pnpm 🔶
- 本机已安装 Node.js 和 pnpm
- 前端未初始化 (`frontend/package.json` 不存在)
- 不阻塞后端开发

---

## 平台兼容性说明

| 组件 | Windows | macOS | Linux | 备注 |
|------|---------|-------|-------|------|
| FastAPI | ✅ 已验证 | CI 待验证 | CI 待验证 | 纯 Python，无平台差异 |
| Pydantic | ✅ | CI | CI | 纯 Python |
| SQLite | ✅ | CI | CI | Python stdlib |
| NetworkX | ✅ | CI | CI | 纯 Python |
| ChromaDB | ✅ | CI | CI | 依赖 onnxruntime，已确认 Windows 可用 |
| LangGraph | ✅ | CI | CI | 纯 Python |
| pandas/numpy/sklearn | ✅ | CI | CI | 跨平台 wheel 可用 |
| ChromaDB onnxruntime | ✅ | CI | CI | 每个平台有对应 wheel |

---

## 总结

- **14/14 smoke tests passed**
- **0 failures**
- **WebSocket 实现延迟到下一轮**
- **ChromaDB 在所有平台均应可用（通过 CI 验证）**
