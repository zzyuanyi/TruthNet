# Adapter 边界报告 — V12 Alignment

> 生成时间：2026-07-17

## 1. 哪些 Port 已定义？

| Port | 文件 | 用途 |
|------|------|------|
| `CompanyRepository` | `application/ports/company_repository.py` | 公司数据访问（search/get_by_code/list_all） |
| `FinanceRepository` | `application/ports/finance_repository.py` | 财务数据访问（get_items/get_warnings） |
| `EquityGraphPort` | `application/ports/equity_graph.py` | 股权图谱分析（get_graph/get_control_chains/check_connection） |
| `VectorStorePort` | `application/ports/vector_store.py` | 向量检索（search/add_documents/check_connection） |
| `LLMProvider` | `application/ports/llm_provider.py` | LLM 对话（chat/chat_stream/check_connection/provider_name） |

所有 Port 定义为 `typing.Protocol`（`@runtime_checkable`），不依赖 FastAPI 或具体数据库驱动。

## 2. 哪些 Adapter 可运行？

| Adapter | Profile | 状态 | 说明 |
|---------|---------|------|------|
| `SQLiteCompanyRepository` | lite | ✅ 可运行 | Mock 数据，内存搜索 |
| `SQLiteFinanceRepository` | lite | ✅ 可运行 | Mock 财务数据 |
| `NetworkXEquityGraph` | lite | ✅ 可运行 | 内存图分析，含 mock 数据 |
| `ChromaVectorStore` | lite/full | ✅ 可运行 | Mock 搜索，返回预设结果 |
| `MockLLMProvider` | lite | ✅ 可运行 | 返回模板 mock 回答 |

## 3. 哪些 Adapter 只是占位？

| Adapter | Profile | 状态 | 说明 |
|---------|---------|------|------|
| `MySQLCompanyRepository` | full | 🔸 骨架 | 空实现，`check_connection()` 可检测连接 |
| `Neo4jEquityGraph` | full | 🔸 骨架 | 空实现，`check_connection()` 可检测连接 |
| `DeepSeekProvider` | full | 🔸 骨架 | 空实现，`check_connection()` 检查 API key |
| `QwenProvider` | full | 🔸 骨架 | 空实现，`check_connection()` 检查 API key |

## 4. lite profile 使用哪些 Adapter？

- CompanyRepository → `SQLiteCompanyRepository`
- FinanceRepository → `SQLiteFinanceRepository`
- EquityGraphPort → `NetworkXEquityGraph`
- VectorStorePort → `ChromaVectorStore`
- LLMProvider → `MockLLMProvider`

## 5. full profile 使用哪些 Adapter？

- CompanyRepository → `MySQLCompanyRepository`
- FinanceRepository → `MySQLCompanyRepository`（或独立 MySQL finance adapter）
- EquityGraphPort → `Neo4jEquityGraph`
- VectorStorePort → `ChromaVectorStore`（持久化模式）
- LLMProvider → `DeepSeekProvider` 或 `QwenProvider`

## 6. 外部服务不可用时如何降级？

- `check_connection()` 返回 `False` 时，Adapting layer 应：
  1. 记录 warning 日志
  2. 在响应 `meta.warnings` 中注明降级
  3. 回退到 lite adapter（如果可用）
  4. 不导致请求失败（graceful degradation）

当前所有 full adapter 骨架在 `check_connection()` 失败时返回 `False`，不会抛出异常。
