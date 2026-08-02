# 事件簇数据交接契约（EVENT_CLUSTER_DATA_CONTRACT）

> Phase C 任务 15：数据组 → 后端的正式交接结构。
> 本契约是唯一事实来源；`docs/schemas/event_cluster.schema.json` 为 JSON Schema 版本。

## 1. 目的和适用范围

数据组将公告/研报/新闻/监管的事件聚类结果按本契约产出 JSONL；后端 `scripts/import_event_clusters.py`
校验并入库，REST/Agent 按本结构消费。适用于 Phase C 及以后所有事件簇交付。

## 2. JSONL 交付格式

- 每行一条 `EventClusterRecord`（UTF-8，LF 换行）；
- 文件名建议 `event_clusters_<dataset_version>.jsonl`；
- 行内不得包含换行符；空行忽略。

## 3. 字段定义

| 字段 | 类型 | 说明 |
|------|------|------|
| `event_cluster_id` | string | 事件簇唯一 ID（见 §7） |
| `entity_id` | string | 公司 entity_id（与 MySQL `companies.entity_id` 对齐） |
| `wind_code` | string | Wind 代码，如 `600518.SH` |
| `topic` | string | 事件簇主题 |
| `summary` | string | 事件簇摘要 |
| `start_date` | date | 起始日期 |
| `end_date` | date | 结束日期 |
| `event_count` | int | 事件数量 |
| `sentiment` | enum | positive/negative/neutral/mixed/unknown |
| `sentiment_score` | float\|null | 情感得分 [-1,1] |
| `sources` | array | 来源列表（见 §10） |
| `evidence_ids` | array | 关联 Evidence ID 列表（见 §11） |
| `cluster_method` | string | 聚类方法标识 |
| `cluster_version` | string | 聚类版本 |
| `dataset_version` | string | 数据集版本 |
| `quality_flags` | array | 质量标记（默认空） |
| `created_at` | datetime | 创建时间 (ISO-8601 UTC) |
| `updated_at` | datetime\|null | 更新时间 |

## 4. 必填/可选

必填：`event_cluster_id, entity_id, wind_code, topic, start_date, end_date,
event_count, sentiment, sources, evidence_ids, cluster_method, cluster_version,
dataset_version, created_at`。
可选：`summary`（默认空）、`sentiment_score`、`quality_flags`、`updated_at`、来源内
`published_at/source_uri/content_hash/fcode`。

## 5. 数据类型

JSON 原生类型 + ISO-8601 日期/时间字符串（见 §8）。

## 6. 枚举

- `sentiment`: `positive | negative | neutral | mixed | unknown`
- `source_type`: `announcement | research_report | news | regulation`

## 7. ID 生成规则

`event_cluster_id` 必须确定性生成，格式：

```
evtcl_<sha256(wind_code | normalized_topic | start_date | end_date |
              sorted_source_record_ids | cluster_version)[:24]>
```

禁止使用 `cluster_<中文主题>`：中文/特殊字符不适合 ID，跨公司/跨期间会冲突，重跑不幂等。

## 8. 日期和时区

- `start_date/end_date/published_at`：`YYYY-MM-DD`；
- `created_at/updated_at`：ISO-8601 带时区（推荐 UTC，如 `2026-08-02T12:00:00Z`）；
- 后端入库统一按 UTC 归一化。

## 9. sentiment 范围

`sentiment_score` 固定范围 `[-1, 1]`；越界视为校验失败。缺省为 `null`。

## 10. source 定义

每条 source 必须可追溯到具体底层记录（公告 `object_id` / 研报 `report_id` / 新闻 / 监管文件）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `source_id` | string | 本文件内唯一 ID |
| `source_type` | enum | 见 §6 |
| `source_record_id` | string | 底层来源记录 ID |
| `title` | string | 标题 |
| `published_at` | date\|null | 发布日期 |
| `source_uri` | string\|null | 来源 URI |
| `content_hash` | string\|null | 内容哈希 |
| `fcode` | string\|null | 公告类型代码 |

约束：同一簇内 `(source_type, source_record_id)` 不得重复。

## 11. evidence ID 规则

`evidence_ids` 必须可解析：每个 ID 指向一条真实 Evidence（`evidence_refs`），来源可为
公告/研报/新闻/监管记录；**不得指向事件簇自身**（避免循环证明）。
建议格式：`ev_<source_namespace>_<digest>`（见任务 16 ID 工厂）。

## 12. 空值政策

- `sources` 不得为空；`evidence_ids` 不得为空；
- `event_count` ≥ 1 且与去重后 sources 数量一致；
- `sentiment_score` 为空表示未评分；`source_uri` 为空表示无外部链接。

## 13. 版本管理

- `cluster_version`：聚类算法版本；
- `dataset_version`：本次交付的数据集版本（如 `phase-c-202608`）；
- `event_cluster_id` 已含 `cluster_version` 与 `dataset_version` 语义，升级聚类必须生成新 ID。

## 14. 幂等规则

- 同 `event_cluster_id` + 同内容 → 重跑 `skipped`（不重复插入）；
- 同 `event_cluster_id` + 不同内容 → `conflicted`（拒绝，不静默覆盖）；
- 导入工具支持 `--validate-only / --dry-run` 预检。

## 15. 错误样例

```json
{"event_cluster_id": "cluster_负面公告", "start_date": "2025-04-01", "end_date": "2025-03-01", "event_count": 0, "sources": [], "evidence_ids": []}
```

错误点：ID 非 `evtcl_` 前缀、日期反转、event_count=0、sources 空、evidence_ids 空。

## 16. 正确样例

```json
{
  "event_cluster_id": "evtcl_0123456789abcdef01234567",
  "entity_id": "company_600518_SH",
  "wind_code": "600518.SH",
  "topic": "重大合同与经营进展",
  "summary": "公司在本时间范围内连续披露相关经营公告。",
  "start_date": "2025-01-01",
  "end_date": "2025-03-31",
  "event_count": 3,
  "sentiment": "neutral",
  "sentiment_score": 0.0,
  "sources": [
    {
      "source_id": "ann_001",
      "source_type": "announcement",
      "source_record_id": "ann_600518_20250115_001",
      "title": "关于签订重大合同的公告",
      "published_at": "2025-01-15",
      "source_uri": null,
      "content_hash": "deadbeef001"
    }
  ],
  "evidence_ids": ["ev_ann_0123456789abcdef01234567"],
  "cluster_method": "llm_semantic_v1",
  "cluster_version": "1.0.0",
  "dataset_version": "phase-c-202608",
  "quality_flags": [],
  "created_at": "2026-08-02T12:00:00Z"
}
```

## 17. 后端导入命令

```bash
python scripts/import_event_clusters.py --input <path> --validate-only
python scripts/import_event_clusters.py --input <path> --dry-run
python scripts/import_event_clusters.py --input <path>
```

## 18. 后端消费方式

- REST：`GET /api/v1/companies/{code}/events` → `event_cluster_id`、结构化 `sources`、`evidence_ids`；
- Agent：`agents/nodes/events.py` 优先读取 `event_clusters` 表，不重新生成 ID；
- 无事件簇数据 → warning `EVENT_CLUSTER_DATA_NOT_READY`；无公告 → `NO_ANNOUNCEMENT_DATA`。

## 19. 数据质量 Gate

- 单行校验失败即整体不导入（不全量写入）；
- 冲突行报错并计入 `conflicted`；
- `evidence_ids` 中每个 ID 必须可解析，否则该簇标记 `quality_flags` 含 `dangling_evidence`。

## 20. 兼容性政策

- 领域层、数据库、导入合同、内部代码统一使用 `event_cluster_id`；
- 旧前端若使用 `cluster_id`，仅在 API 兼容层提供 alias，两个字段不得分别存不同值；
- 本仓库不提供 `cluster_id` 作为领域层正式字段。

## 相关文件

- JSON Schema：`docs/schemas/event_cluster.schema.json`
- 领域模型：`backend/app/domain/events/contracts.py`
- 导入工具：`scripts/import_event_clusters.py`
- 样例 fixture：`backend/tests/fixtures/event_clusters_sample.jsonl`
