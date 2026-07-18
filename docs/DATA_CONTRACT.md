# 数据契约 — V12 Baseline

> **版本**: 2.0 | **基线**: V12 (2026-07-15)
> 设计依据: `TruthNet_综合设计方案_V12(2).md` §10 数据架构

---

## 数据分层 (V12)

```text
raw_*        原始数据，追加写，不覆盖
canonical_*  字段、代码、日期、单位和口径统一
normalized_* 实体对齐、去重和质量标记
derived_*    增速、分位、规则结果、风险快照
serving_*    面向 API 和前端的聚合缓存
```

## 公共系统字段

所有业务记录建议包含:

```text
id, source_record_id, source_file, source_row, source_type,
dataset_version, revision_no, is_latest,
ingested_at, updated_at, quality_flags, checksum
```

---

## 存储架构

| 层级 | lite profile | full profile | 用途 |
|------|-------------|-------------|------|
| 关系数据 | SQLite | MySQL 8.0 | 公司、财务、会话、报告 |
| 图数据 | NetworkX | Neo4j | 股权穿透、关联方分析 |
| 向量数据 | ChromaDB local | ChromaDB persistent | 公告/研报语义检索、会话记忆 |
| LLM | Mock | DeepSeek / Qwen | 对话生成 |
| ORM | SQLAlchemy (SQLite) | SQLAlchemy (MySQL) | 统一数据访问 |
| Migration | Alembic (SQLite) | Alembic (MySQL) | Schema 版本管理 |

---

## MySQL 核心表 (V12)

### companies

| 字段 | 类型 | 说明 |
|------|------|------|
| `entity_id` | VARCHAR PK | 内部稳定实体 ID |
| `wind_code` | VARCHAR UNIQUE | 如 `600519.SH` |
| `sec_name` | VARCHAR | 证券简称 |
| `aliases` | JSON/TEXT | 曾用名和别名 |
| `exchange_code` | VARCHAR | XSHG/XSHE |
| `industry_l1` | VARCHAR | 申万一级行业 |
| `industry_l2` | VARCHAR | 申万二级行业 |
| `listing_date` | DATE | 上市日期 |
| `industry_source` | VARCHAR | 行业来源 |
| `industry_as_of` | DATE | 行业分类有效日期 |

### 财务报表 (balance_sheet / income_statement / cash_flow)

唯一约束: `(wind_code, report_period, statement_type, ann_dt, revision_no)`

不要只用 `(wind_code, report_period)`，因为同一报告期可能存在更正和重述。

### top_shareholders

```text
wind_code, ann_dt, s_holder_enddate, s_holder_name,
s_holder_pct, s_holder_quantity, s_holder_holdercategory,
report_period, holder_entity_id, entity_match_confidence
```

### announcements / research_reports

公告和研报表，含 `sentiment`, `rating_change`, `source_uri`, `content_hash`。

### 派生与运行表

```text
rule_definitions, rule_evaluations, risk_policies, risk_assessments,
event_clusters, event_relations, claims, evidence_refs,
conversation_sessions, conversation_turns, module_executions,
report_jobs, data_quality_reports
```

---

## Neo4j 图数据

### 节点

```text
Entity (entity_id, entity_type, canonical_name, aliases[], wind_code?)
标签: ListedCompany, Company, Person, Plan
```

### 关系类型

```text
HOLDS, CONTROLS, ACTS_IN_CONCERT_WITH, RELATED_TO, GUARANTEES
```

公共属性: `pct, quantity, effective_from, effective_to, report_period, source_id, source_type, confidence, verification_status, graph_version`

### LLM 候选关系

```text
verification_status=pending, extraction_method=llm, confidence=<score>
```

结构化数据、多源一致或规则验证通过后，才升级为 verified。

---

## ChromaDB Collections

| Collection | 内容 | 状态 |
|------|------|:---:|
| `announcement_chunks` | 公告标题/摘要/正文块 | 🔸 |
| `research_report_chunks` | 研报摘要分块 | 🔸 |
| `evidence_text_chunks` | 可定位原文片段 | 🔸 |
| `conversation_memory` | 长期可检索事实 | 🔸 |

Metadata: `chunk_index, chunker_version, embedding_model, text_hash, dataset_version, language`

---

## EvidenceRef / Claim 数据契约

### EvidenceRef

```python
class EvidenceRef(BaseModel):
    evidence_id: str
    source_type: str          # financial_statement / ownership_record / news_article / regulation
    source_record_id: str
    company_code: str | None
    field_path: str | None
    period: str | None
    value: Decimal | str | None
    unit: str | None
    statement_scope: str | None  # parent_company / consolidated
    source_title: str
    source_uri: str | None
    source_excerpt: str | None
    dataset_version: str
    checksum: str | None
    retrieved_at: datetime
```

### Claim

```python
class Claim(BaseModel):
    claim_id: str
    text: str
    claim_type: str
    severity: RiskLevel
    confidence: Confidence | None
    rule_id: str | None
    rule_version: str | None
    evidence_ids: list[str]
    verification_status: str
    limitations: list[str]
```

规则:
- 事实型 Claim 至少一个 Evidence
- LLM 只能引用已提供的 `evidence_id`
- 无证据内容只能作为解释、假设或追问建议
- 证据失效或被新修订替代时，旧分析仍可重现

---

## 禁止事项

- 禁止提交 `.db` / `.sqlite` / `.env` / 真实密钥
- 禁止提交 ChromaDB/Neo4j/MySQL 数据目录
- 禁止在 `data/raw/` 和 `data/processed/` 提交大文件
- 前端不得私自修改后端定义的字段名和类型
- MySQL 不使用 ENUM，使用 VARCHAR + CHECK 或字典表
