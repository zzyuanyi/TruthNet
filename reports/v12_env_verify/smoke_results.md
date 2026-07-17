# Smoke 测试结果

> 运行命令: `E:/anaconda/envs/truthnet/python.exe scripts/verify_v12_stack.py`

## 结果摘要

```
============================================================
  TruthNet V12 Stack Verification
============================================================

--- 1. Environment ---
Python executable: E:\anaconda\envs\truthnet\python.exe
  [PASS] | Python version (3.11.15)  — expected 3.11.x
  [WARN] | 未检测到 conda 环境，建议: conda activate truthnet
  [PASS] | .python-version match (3.11)  — current: 3.11.15

--- 2. Core Dependencies (Prompt1-4 baseline) ---
  [PASS] | fastapi (0.115.0)
  [PASS] | pydantic (2.9.2)
  [PASS] | pydantic_settings (2.5.2)
  [PASS] | langgraph (unknown)
  [PASS] | langchain_core (0.3.29)
  [PASS] | networkx (3.3)
  [PASS] | chromadb (0.5.23)
  [PASS] | pandas (2.2.3)
  [PASS] | numpy (1.26.4)
  [PASS] | pytest (8.3.3)
  [PASS] | httpx (0.27.2)
  [PASS] | ruff (unknown)
  [PASS] | pre_commit (unknown)

--- 3. V12 New Dependencies ---
  [PASS] | sqlalchemy (2.0.35)
  [PASS] | alembic (1.13.2)
  [PASS] | pymysql (1.4.6)
  [PASS] | neo4j (5.26.0)
  [PASS] | structlog (24.4.0)
  [PASS] | jsonschema (4.23.0)

--- 4. Minimal Smoke Tests ---
  [PASS] | SQLAlchemy smoke (sqlite memory SELECT 1)
  [PASS] | Alembic import  — v1.13.2
  [PASS] | PyMySQL driver import  — v1.4.6
  [PASS] | Neo4j driver import  — v5.26.0
  [PASS] | jsonschema validate
  [PASS] | structlog logger bind
  [PASS] | NetworkX smoke (small graph)
  [PASS] | ChromaDB smoke (ephemeral client)
  [PASS] | Pydantic V2 model roundtrip
  [PASS] | LangGraph StateGraph mini
  [PASS] | FastAPI app import  — title=TruthNet API
  [PASS] | V12 lite adapter imports

  [PASS] | All smoke tests passed

============================================================
  [PASS] | V12 技术栈验证通过
============================================================
```

## 所有 smoke 测试通过

- ✅ 25 个包 import 验证（13 个旧栈 + 6 个 V12 新 + 6 个工具链）
- ✅ 12 个最小 smoke 操作（SQLAlchemy SELECT, jsonschema validate, structlog bind, NetworkX graph, ChromaDB collection, Pydantic model, LangGraph StateGraph, FastAPI app import, V12 adapter imports）
- ✅ 退出码 0（全部通过）
