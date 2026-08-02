# Claim/Evidence 全局追溯契约（PROVENANCE_CONTRACT）

> Phase C 任务 16：所有 `evidence_id` / `claim_id` 全局可追踪。

## 1. ID 生成（确定性、可重放）

统一工厂：`backend/app/domain/provenance/id_factory.py`

- **Evidence ID**：`ev_<source_namespace>_<sha256(...)[:16]>`
  digest 输入 = `source_type | source_record_id | field_path | period | dataset_version | company_code`
  同来源/字段/期间/公司重复生成 → 相同 ID。
- **Claim ID**：`clm_<sha256(...)[:16]>`
  digest 输入 = `turn_id | company_code | claim_type | rule_id | event_cluster_id | ordinal | 规范化文本 | rule_version`
  同一次 turn 重试 → 相同 ID；不同 turn / 不同公司不冲突。

命名空间：`fin`（财务）、`eq`（股权）、`ann`（公告）、`evt`（事件簇）。

## 2. 持久化表

- `claims`：声明主表（含 `turn_id / trace_id / company_code / module`，`confidence` FLOAT）
- `evidence_refs`：证据主表（含 `turn_id / trace_id / module / source_table`）
- `claim_evidence_links`：Claim↔Evidence 多对多关系表
  `UNIQUE(claim_id, evidence_id, relation_type)`，外键阻止悬空引用

`persist_turn.py` 在单事务内按外键顺序写入会话→轮次→证据→声明→关联；同 ID 同内容幂等，同 ID 不同内容冲突并回滚。

## 3. 底层来源定位

`backend/app/application/services/source_resolver.py` 按 EvidenceRef 定位：

| source_type | 定位方式 |
|---|---|
| `financial_statement` | 解析 `source_record_id`（code\|period\|stmt）→ 查 `balance_sheet/income_statement/cash_flow` |
| `announcement` | `announcements.object_id` |
| `neo4j_relationship` | Neo4j `relationship_id` |
| `event_cluster` | `event_clusters.event_cluster_id` |

## 4. Lookup API（V12 envelope）

- `GET /api/v1/evidence/{evidence_id}` → evidence + 关联 claims + 来源记录
- `GET /api/v1/claims/{claim_id}` → claim + 全部 evidence + turn 上下文
- `GET /api/v1/traces/{trace_id}/provenance` → 整轮 Claim/Evidence 图

不存在 → 404 Problem Details；非法 ID → 422；来源找不到 → `SOURCE_RECORD_NOT_FOUND` warning。

## 5. 质量 Gate

- 无悬空引用（`claim_evidence_links` 外键）；
- 无 `verified` Claim 缺证据；
- 无重复 claim_id/evidence_id；
- 服务重启后按 ID 仍可查询（持久化在 MySQL）。
