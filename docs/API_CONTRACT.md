# API 接口契约

> **接口先行原则**：后端必须先定 Pydantic schema → 更新本文档 → 提供 mock JSON → 再写实现。
> 前端依据此文档和 mock JSON 独立并行开发。

---

## 基础信息

- 基础 URL：`http://localhost:8000`
- 统一响应格式：

```json
{
  "code": 0,
  "data": {},
  "message": "ok",
  "trace_id": "uuid-string"
}
```

- 所有接口前缀：`/api/v1/`

---

## 接口列表

### 1. 健康检查

**`GET /health`**

状态：✅ 稳定

#### 响应示例

```json
{
  "code": 0,
  "data": {
    "status": "healthy",
    "version": "0.1.0"
  },
  "message": "ok",
  "trace_id": "abc123"
}
```

---

### 2. 对话接口（REST）

**`POST /api/v1/chat`**

状态：🔶 MVP（字段可能追加，不删除不重命名）

#### 请求

```json
{
  "question": "请分析贵州茅台2023年营收与现金流量表的勾稽关系",
  "session_id": "sess_abc123",
  "context": {
    "company_code": "300838.SZ",
    "fiscal_year": 2023
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `question` | string | ✅ | 用户问题 |
| `session_id` | string | 否 | 会话 ID，用于多轮对话 |
| `context` | object | 否 | 附加上下文（公司代码、年份等） |

#### 响应

```json
{
  "code": 0,
  "data": {
    "answer": "贵州茅台2023年营收为1505.60亿元，销售商品提供劳务收到的现金为1652.35亿元，收现比约109.74%...",
    "evidence": [
      {"source": "利润表", "field": "营业收入", "value": "1505.60亿"},
      {"source": "现金流量表", "field": "销售商品收到的现金", "value": "1652.35亿"}
    ],
    "graph": {
      "nodes": [{"id": "600519", "label": "贵州茅台", "type": "company"}],
      "edges": [{"source": "600519", "target": "sub_1", "relation": "子公司"}]
    },
    "timeline": [
      {"date": "2023-03-31", "event": "发布2022年报", "source": "公告"},
      {"date": "2023-08-02", "event": "发布2023半年报", "source": "公告"}
    ],
    "risk_score": {
      "overall": 0.15,
      "financial": 0.10,
      "ownership": 0.20,
      "sentiment": 0.05
    },
    "warnings": [],
    "missing_modules": [],
    "trace_id": "trace_abc123"
  },
  "message": "ok",
  "trace_id": "trace_abc123"
}
```

#### 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `answer` | string | Markdown 格式的主回答 |
| `evidence` | list | 证据列表，每项标注来源 |
| `graph` | object | 股权/关联关系图谱（nodes + edges） |
| `timeline` | list | 相关事件时间线 |
| `risk_score` | object | 风险评分对象（Prompt4 冻结） |
| `risk_score.overall` | float | 综合风险评分 0-1 |
| `risk_score.financial` | float | 财务风险评分 0-1 |
| `risk_score.ownership` | float | 股权风险评分 0-1 |
| `risk_score.sentiment` | float | 舆情风险评分 0-1 |
| `warnings` | list | 财务预警点列表 |
| `missing_modules` | list | 暂缺的模块（不影响主流程） |
| `trace_id` | string | 本次请求追踪 ID |

---

### 3. 对话接口（WebSocket）

**`WS /api/v1/chat/ws`**

状态：🔶 MVP（已实现最小 mock 端点，Prompt3）

#### 连接

```
ws://localhost:8000/api/v1/chat/ws
```

无需查询参数。`trace_id` 由服务端在连接时生成。

#### 客户端发送

```json
{
  "type": "question",
  "data": {
    "question": "请分析贵州茅台2023年营收",
    "context": {"company_code": "600519"}
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | ✅ | 消息类型，目前固定为 `"question"` |
| `data.question` | string | ✅ | 用户问题 |
| `data.context` | object | 否 | 附加上下文 |

#### 服务端推送消息类型

| 类型 | 说明 | 何时发送 |
|------|------|----------|
| `status` | 处理状态更新 | 收到问题后首先发送 |
| `partial_answer` | 流式部分回答 | 模拟流式输出过程中发送 |
| `final_answer` | 完整回答（格式同 REST 响应 data） | 回答结束时发送 |
| `error` | 错误信息 | JSON 解析失败或缺少必填字段时发送 |

#### 消息示例

```json
// status — 处理状态
{
  "type": "status",
  "data": {
    "message": "正在分析: 请分析贵州茅台2023年营收...",
    "trace_id": "trace_abc"
  }
}

// partial_answer — 流式部分回答
{
  "type": "partial_answer",
  "data": {
    "text": "Mock 回答：关于「请分析贵州茅台2023年营收...」的分析正在开发中",
    "sequence": 1,
    "trace_id": "trace_abc"
  }
}

// final_answer — 完整回答（data 结构与 REST 响应 data 一致）
{
  "type": "final_answer",
  "data": {
    "answer": "Mock 回答完整文本...",
    "evidence": [],
    "graph": {"nodes": [], "edges": []},
    "timeline": [],
    "risk_score": {
      "overall": 0.15,
      "financial": 0.10,
      "ownership": 0.20,
      "sentiment": 0.05
    },
    "warnings": [],
    "missing_modules": ["编排Agent", "财务勾稽Agent", "股权穿透Skill", "舆情事件Skill"],
    "trace_id": "trace_abc"
  }
}

// error — 错误响应
{
  "type": "error",
  "data": {
    "code": 400,
    "message": "question 字段为必填项",
    "trace_id": "trace_abc"
  }
}
```

---

### 4. 文件上传

**`POST /api/v1/files/upload`**

状态：🔶 MVP

#### 请求

- Content-Type: `multipart/form-data`
- 字段：`file` (PDF / Excel / 图片)

#### 响应

```json
{
  "code": 0,
  "data": {
    "file_id": "file_abc123",
    "filename": "2023年报.pdf",
    "size": 2048000,
    "status": "processing"
  },
  "message": "文件上传成功",
  "trace_id": "trace_abc"
}
```

---

### 5. 公司风险查询

**`GET /api/v1/companies/{company_id}/risk`**

状态：🔶 MVP

#### 路径参数

| 参数 | 说明 |
|------|------|
| `company_id` | 公司唯一标识（Wind 代码，如 "300838.SZ"） |

#### 响应

```json
{
  "code": 0,
  "data": {
    "company_id": "600519",
    "company_name": "贵州茅台酒股份有限公司",
    "risk_score": 0.15,
    "risk_factors": [
      {"category": "营收勾稽", "level": "low", "detail": "营收与现金流入匹配"},
      {"category": "关联交易", "level": "medium", "detail": "关联交易占比超过行业平均"}
    ],
    "last_updated": "2024-01-15T10:30:00Z"
  },
  "message": "ok",
  "trace_id": "trace_abc"
}
```

---

### 6. 公司股权穿透

**`GET /api/v1/companies/{company_id}/ownership`**

状态：🔶 MVP

#### 查询参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `depth` | int | 否 | 穿透深度（默认 3，最大 5） |
| `direction` | string | 否 | `upstream`（向上） / `downstream`（向下） |

#### 响应

```json
{
  "code": 0,
  "data": {
    "company_id": "600519",
    "company_name": "贵州茅台酒股份有限公司",
    "ownership_graph": {
      "nodes": [
        {"id": "600519", "label": "贵州茅台", "type": "target"},
        {"id": "gzw_gz", "label": "贵州省国资委", "type": "controller", "depth": 2}
      ],
      "edges": [
        {"source": "gzw_gz", "target": "mt_group", "relation": "100%控股"},
        {"source": "mt_group", "target": "600519", "relation": "54%控股"}
      ]
    },
    "control_chains": [
      {"path": ["贵州省国资委", "茅台集团", "贵州茅台"], "total_stake": 0.54, "depth": 2}
    ]
  },
  "message": "ok",
  "trace_id": "trace_abc"
}
```

---

### 7. 公司事件时间线

**`GET /api/v1/companies/{company_id}/timeline`**

状态：🔶 MVP

#### 查询参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `from_date` | string | 起始日期（YYYY-MM-DD） |
| `to_date` | string | 结束日期（YYYY-MM-DD） |
| `limit` | int | 最多返回条数（默认 50） |

#### 响应

```json
{
  "code": 0,
  "data": {
    "company_id": "600519",
    "events": [
      {
        "date": "2024-03-01",
        "title": "发布2023年度报告",
        "category": "公告",
        "summary": "公司发布2023年年度报告，营收同比增长12%",
        "sentiment": "neutral",
        "sources": ["上交所公告", "财经媒体转载"]
      }
    ],
    "clusters": [
      {"topic": "产品涨价", "event_count": 5, "date_range": "2023-06 至 2023-12"}
    ]
  },
  "message": "ok",
  "trace_id": "trace_abc"
}
```

---

## 错误响应格式

所有错误响应遵循统一格式：

```json
{
  "code": 400,
  "data": null,
  "message": "question 字段为必填项",
  "trace_id": "trace_abc"
}
```

### 错误码

| code | 含义 |
|------|------|
| 0 | 成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 422 | 参数校验失败 |
| 500 | 服务器内部错误 |
| 503 | 服务暂时不可用 |

---

## 接口稳定性约定

- **稳定**（✅）：不计划修改。如果必须修改，需走完整变更流程。
- **MVP**（🔶）：核心字段稳定，可能追加新字段，不删除/重命名已有字段。
- **草案**（🔸）：仍在设计中，可能大幅调整。

### 接口变更规则

1. 新字段只能追加，不删除已有字段
2. 破坏性修改必须在 `docs/INTERFACE_CHANGELOG.md` 中记录
3. 破坏性修改需要项目负责人审阅
4. 破坏性修改需要提供兼容层或迁移方案
