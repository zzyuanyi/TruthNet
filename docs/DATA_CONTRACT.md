# 数据契约 — V12 Baseline

> **版本**: 2.0
> **基线**: V12 (2026-07-17)

---

## 存储架构 (V12)

| 层级 | lite profile | full profile | 用途 |
|------|-------------|-------------|------|
| 关系数据 | SQLite | MySQL 8.0 | 公司信息、财务数据 |
| 图数据 | NetworkX | Neo4j | 股权穿透、关联方分析 |
| 向量数据 | ChromaDB (local) | ChromaDB (persistent) | 财报语义搜索 |
| LLM | Mock | DeepSeek / Qwen | 对话生成 |
| ORM | SQLAlchemy (SQLite) | SQLAlchemy (MySQL) | 统一数据访问 |
| Migration | Alembic (SQLite) | Alembic (MySQL) | Schema 版本管理 |

## SQLite（lite 默认）

**路径**：`data/truthnet.db`（不提交到 Git）

草案表结构（SQLAlchemy ORM 定义在 `backend/app/infrastructure/persistence/`）：

```text
companies          — 公司基本信息
financial_items    — 财务报表科目
ownership_relations — 股权关系
conversations      — 对话记录
```

## MySQL（full 目标）

**配置**：见 `.env.example`
**ORM**：SQLAlchemy 2.0+
**Migration**：Alembic
**Driver**：PyMySQL（纯 Python，Windows 兼容）

## NetworkX（lite 默认）

内存图分析，无需外部服务。

- 节点类型: company, person, entity, controller
- 边类型: holds, controls, related

## Neo4j（full 目标）

**配置**：见 `.env.example`
**Driver**：neo4j Python driver 5.26+
**URI**：`bolt://localhost:7687`

## ChromaDB（lite/full 共用）

**lite**：本地文件持久化（`data/chroma_db`）
**full**：可扩展为 ChromaDB Server

Collection 草案：

| Collection | 用途 |
|------------|------|
| `financial_reports` | 财报文本片段 |
| `news_events` | 舆情新闻 |
| `regulations` | 会计准则、法规 |

## EvidenceRef / Claim 数据契约

V12 核心证据模型：

```json
{
  "id": "ev_001",
  "type": "financial_statement",
  "source": "2023年报 利润表",
  "field": "营业收入",
  "value": "1505.60亿",
  "page": "第45页",
  "retrieval_score": 0.95
}
```

```json
{
  "id": "cl_001",
  "statement": "营业收入与现金流匹配良好",
  "confidence": "high",
  "evidence": ["ev_001", "ev_002"],
  "counter_evidence": [],
  "generated_at": "2026-07-15T10:00:00"
}
```

## 禁止事项

- 禁止提交 `.db` / `.sqlite` 文件
- 禁止提交 ChromaDB 持久化数据
- 禁止在 `data/raw/` 和 `data/processed/` 提交大文件
- 前端不得私自修改后端定义的字段名和类型
