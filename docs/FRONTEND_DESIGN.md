# 前端设计文档 — V12 Baseline

> **版本**: 2.0 | **基线**: V12 (2026-07-15)
> 设计依据: `TruthNet_综合设计方案_V12(2).md` §4-5 前端设计

---

## 技术栈

| 层级 | 技术 | 状态 |
|------|------|:---:|
| 框架 | React 18 + Vite 6 + TypeScript 5.6 | ✅ 已初始化 |
| UI 组件 | shadcn/ui + Tailwind CSS | 🔸 待接入 |
| 图表 | Recharts | 🔸 待接入 |
| 图谱 | D3.js（必要时封装 Canvas/SVG 层）| 🔸 待接入 |
| HTTP | fetch / axios | ✅ |
| WebSocket | 原生 WebSocket API | ✅ |

---

## 页面路由

| 路由 | 页面 | 优先级 |
|------|------|:---:|
| `/` | 对话主页 | P0 |
| `/company/:code` | 企业画像页 | P0 |
| `/compare?codes=...` | 跨公司对比页 | P1 |
| `/reports/:reportId` | 报告任务页 | P1 |
| `/settings` | 本地展示设置 | P2 |

---

## 对话主页布局

```text
┌────────────┬──────────────────────────────┬──────────────────┐
│ 会话侧边栏  │          对话区              │    分析面板      │
│  240px     │         flex-1               │  360–440px       │
│            │                              │                  │
│ [+新建会话] │ [消息列表 + 流式输出]        │ [风险等级]       │
│ 会话列表    │                              │ [模块状态]       │
│ 搜索/删除  │ [输入框 + 发送]              │ [规则触发清单]   │
│            │                              │ [事件时间线]     │
│            │                              │ [证据链]        │
└────────────┴──────────────────────────────┴──────────────────┘
```

## 企业画像页

板块: 基本信息 + 风险标签 → 财务异常 (7条规则+趋势图) → 股权穿透图 (D3) → 关联方风险 → 舆情时间线 → 证据引用 → 行业对比入口

## 响应式断点

| 断点 | 布局 |
|------|------|
| ≥1920px | 三栏；侧栏 240px；面板 ~420px |
| 1200–1919px | 三栏；面板可折叠 |
| 768–1199px | 会话栏 + 对话区；面板为右侧抽屉 |
| <768px | 单栏；会话栏顶部抽屉；面板底部 Sheet |

---

## 核心组件

### 基础组件 (shadcn/ui)

Button, Badge, Card, Collapsible/Accordion, ScrollArea, Dialog/AlertDialog, Sheet/Drawer, Toast, Skeleton, Progress, Tabs, Tooltip, Table

### 业务组件

| 组件 | 文件 | 职责 |
|------|------|------|
| SessionSidebar | `layout/SessionSidebar.tsx` | 会话新建/切换/删除/搜索 |
| ChatInterface | `chat/ChatInterface.tsx` | 消息列表、输入和流式状态 |
| ModuleProgress | `chat/ModuleProgress.tsx` | 公开执行步骤 |
| CandidateSelector | `chat/CandidateSelector.tsx` | 公司候选确认 |
| AnalysisPanel | `analysis/AnalysisPanel.tsx` | 四类核心摘要 |
| RuleCard | `analysis/RuleCard.tsx` | 规则状态、趋势和证据入口 |
| EquityGraph | `company/EquityGraph.tsx` | D3 图谱 + 列表替代视图 |
| RelatedPartyTable | `company/RelatedPartyTable.tsx` | 关联方风险表 |
| RiskTimeline | `company/RiskTimeline.tsx` | 事件时间线 |
| EvidenceChain | `company/EvidenceChain.tsx` | Claim–Evidence 展示 |
| ComparePage | `compare/ComparePage.tsx` | 多公司比较 |
| ReportStatusPage | `report/ReportStatusPage.tsx` | 长任务状态和下载 |

---

## 风险视觉规范

| 等级 | 语义 | 视觉 |
|:---:|------|------|
| red | 高风险 | 红色 + 警示图标 + "高风险"文字 |
| orange | 中高风险 | 橙色 + 文字 |
| yellow | 中等关注 | 黄色 + 文字 |
| blue | 低风险/轻度关注 | 蓝色 + 文字 |
| green | 当前未见明显异常 | 绿色 + 文字 |
| unknown | 数据不足或无法评估 | 灰色 + 问号图标 + 解释 |

不能仅凭颜色表达风险；所有颜色同时伴随文字或图标。

---

## 前端核心类型 (TypeScript)

```typescript
type RiskLevel = 'red' | 'orange' | 'yellow' | 'blue' | 'green' | 'unknown'
type ModuleState = 'pending' | 'running' | 'success' | 'partial' | 'failed' | 'skipped' | 'cancelled'

interface ApiMeta {
  requestId: string; traceId: string; schemaVersion: string
  generatedAt: string; dataAsOf?: string
  datasetVersion?: string; ruleSetVersion?: string; graphVersion?: string
}

interface ApiResponse<T> { data: T; meta: ApiMeta; warnings: WarningItem[] }

interface WSMessage<T = unknown> {
  schemaVersion: string; eventId: string; eventType: string
  sessionId: string; turnId: string; sequence: number
  timestamp: string; traceId: string; payload: T
}
```

TypeScript 类型优先由 OpenAPI/事件 schema 生成，手写类型只用于前端 ViewModel。

---

## WebSocket Reducer

```text
turn.accepted       → 创建 activeTurn
company.candidates  → 打开候选卡片
module.started      → 模块状态 running
module.completed    → success/partial/failed
answer.delta        → 追加 Assistant 文本
artifact.upsert     → 按 artifact_id + revision 更新面板
turn.completed      → 写入最终状态和追问建议
turn.failed         → 显示错误并保留已有部分结果
heartbeat           → 更新连接健康时间
```

未知事件只记录日志并忽略，不中断客户端。

---

## 无障碍设计

目标 WCAG 2.2 AA: 键盘操作、焦点管理、风险不只依赖颜色、图表提供表格替代、尊重 `prefers-reduced-motion`、触控目标 ≥44px。
