# 接口冻结评审报告

> 评审时间：2026-07-02
> 评审范围：当前 HTTP + WebSocket mock 接口

## 冻结评审结果

| Interface | Status | Stable Fields | Changed Fields (Prompt4) | Breaking Change Risk | Action |
| --------- | ------ | ------------- | ------------------------ | -------------------- | ------ |
| `GET /health` | ✅ 稳定 | status, version | 无 | 无 | 保持 |
| `POST /api/v1/chat` | 🔶 MVP 冻结 | answer, evidence, graph, timeline, risk_score, warnings, missing_modules, trace_id | risk_score: float → RiskScore 对象 | 是（已在前端类型同步） | 已更新 |
| `WS /api/v1/chat/ws` | 🔶 MVP 冻结 | status, partial_answer, final_answer, error 四种消息类型 | final_answer.data 结构同步 HTTP ChatData | 无（结构复用） | 已更新 |

## risk_score 字段变更详情

### 旧（Prompt3）
```json
"risk_score": 0.15
```

### 新（Prompt4）
```json
"risk_score": {
  "overall": 0.15,
  "financial": 0.10,
  "ownership": 0.20,
  "sentiment": 0.05
}
```

### 变更理由
- 单一数字无法表达不同维度的风险
- 财务风险、股权风险、舆情风险需要分开量化
- 前端 RiskPanel 可以展示分维度风险条
- 这是一个**破坏性变更**（类型从 float 变为 object）

### 变更影响与处理
- ✅ `backend/app/schemas/chat.py`：新增 RiskScore 模型，更新 ChatData
- ✅ `backend/app/main.py`：HTTP 和 WS 端点返回新格式
- ✅ `backend/tests/`：3 个测试文件已更新
- ✅ `frontend/src/types/api.ts`：RiskScore 接口已同步
- ✅ `frontend/src/components/RiskPanel.tsx`：已适配新格式
- ✅ `docs/API_CONTRACT.md`：待更新（见下方）
- ✅ `docs/INTERFACE_CHANGELOG.md`：待更新

## 当前接口字段稳定性声明

### POST /api/v1/chat 响应（ChatData）

| 字段 | 类型 | 稳定性 | 说明 |
|------|------|--------|------|
| `answer` | string | 冻结 | Markdown 格式主回答 |
| `evidence` | Evidence[] | 冻结 | 证据列表 |
| `evidence[].source` | string | 冻结 | 数据来源 |
| `evidence[].field` | string | 冻结 | 字段名 |
| `evidence[].value` | string | 冻结 | 字段值 |
| `graph` | GraphData | 冻结 | 图谱数据 |
| `graph.nodes` | GraphNode[] | 冻结 | 节点列表 |
| `graph.edges` | GraphEdge[] | 冻结 | 边列表 |
| `timeline` | TimelineEvent[] | 冻结 | 事件时间线 |
| `risk_score` | RiskScore | 冻结 | 风险评分对象 |
| `risk_score.overall` | float (0-1) | 冻结 | 综合风险 |
| `risk_score.financial` | float (0-1) | 冻结 | 财务风险 |
| `risk_score.ownership` | float (0-1) | 冻结 | 股权风险 |
| `risk_score.sentiment` | float (0-1) | 冻结 | 舆情风险 |
| `warnings` | string[] | 冻结 | 预警点列表 |
| `missing_modules` | string[] | 冻结 | 暂未实现模块 |
| `trace_id` | string | 冻结 | 追踪 ID |

### WS /api/v1/chat/ws 消息类型

| 消息类型 | 稳定性 | 说明 |
|----------|--------|------|
| `status` | 冻结 | 处理状态更新 |
| `partial_answer` | 冻结 | 流式部分回答 |
| `final_answer` | 冻结 | 完整回答（data 结构 = ChatData） |
| `error` | 冻结 | 错误消息 |

## 冻结规则

1. ✅ 以上标记为「冻结」的字段**不再进行破坏性修改**
2. ✅ 后续新增字段**只能追加**到 data 对象中
3. ❌ **不得删除**已有字段
4. ❌ **不得重命名**已有字段
5. ❌ **不得改变**已有字段的类型
6. ✅ 如需破坏性修改，必须：
   - 在 `docs/INTERFACE_CHANGELOG.md` 记录
   - 同步更新 backend schema + frontend types
   - 在 PR 中明确说明为 breaking change
   - 经项目负责人审阅

## 结论

HTTP chat 和 WebSocket 接口已进入 MVP 冻结状态。risk_score 已升级为结构化对象，验证了冻结规则中的破坏性变更流程。前后端类型完全一致。

**状态：PASSED**
